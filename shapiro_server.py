from abc import ABC, abstractmethod
import uvicorn
import asyncio
import argparse
from fastapi import FastAPI, Response, Request, status, Header
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse
import logging
import os
import sys
from rdflib import Graph
import pyshacl
import json
import copy
from urllib.parse import urlparse
from typing import List
from threading import Thread, Event
from datetime import datetime

MIME_HTML = "text/html"
MIME_JSONLD = "application/ld+json"
MIME_TTL = "text/turtle"
MIME_JSONSCHEMA = "application/json"
MIME_DEFAULT = MIME_TTL

SUFFIX_JSONLD = '.jsonld'
SUFFIX_TTL = '.ttl'
SUPPORTED_SUFFIXES = [ SUFFIX_JSONLD, SUFFIX_TTL ]

SUPPORTED_MIME_TYPES = [MIME_JSONLD, MIME_TTL]

IGNORE_NAMESPACES = []

CONTENT_DIR = './'
BAD_SCHEMAS = []
ROUTES = None
HOUSEKEEPERS = []


log = logging.getLogger("uvicorn")

app = FastAPI()

class BadSchemaException(Exception):

    def __init__(self):
        pass

class SchemaHousekeeping(Thread):
    """
    Separate thread that does housekeeping on schemas. This is required
    to keep the server in sync with the schemas when the server runs
    for long times while schemas get added/removed in the file system.
    """

    def __init__(self, sleep_seconds):
        Thread.__init__(self)
        self.sleep_seconds = sleep_seconds
        self.last_execution_time = None
        self.stopped = Event()

    def stop(self):
        self.stopped.set()

    def run(self):
        while not self.stopped.is_set():
            self.check_for_schema_updates()
            self.stopped.wait(self.sleep_seconds)

    def walk_schemas(self, content_dir:str, visit_schema):
        """
        Walk the hierarchy at content_dir and call the function specified under visit_schema.
        visit_schema is a function that takes four string parameters: path (the hierarchical name the schema sits under, without the actual schema name), 
        full_name (the fully qualified path to the file containing the schema), the schema path (the fully qualified name of the schema) and suffix (the suffix
        of the file containing the schema). 
        visit_schema must return either None or a value. If it returns a value that value is collected and the collection of values is returned as the result of this
        function (walk_schemas). 
        """
        result = []
        for dir in os.walk(content_dir):
            path = dir[0].replace('\\', '/').replace(os.path.sep, '/')
            for filename in dir[2]:
                suffix = filename[filename.rfind('.'):len(filename)]
                if path.endswith('/'):
                    full_name = path+filename
                else:
                    full_name = path + '/' + filename
                if suffix in SUPPORTED_SUFFIXES:   
                    schema_path = full_name[len(CONTENT_DIR):len(full_name)-len(suffix)]                                                                                                                      
                    visit_result = visit_schema(path, full_name, schema_path, suffix)
                    if visit_result is not None:
                        result.append(visit_result)
        return result

    def check_for_schema_updates(self):
        log.info("Housekeeping: Checking schema files for modifications.")
        schemas_to_check = self.walk_schemas(CONTENT_DIR, self.check_schema)
        log.info("Housekeeping detected {} modified schemas.".format(len(schemas_to_check)))
        self.last_execution_time = datetime.now()
        self.perform_housekeeping_on(schemas_to_check)
        
    def check_schema(self, path:str, full_name:str, schema_path:str, suffix:str):
        mod_time= datetime.fromtimestamp(os.stat(full_name).st_mtime)
        if self.last_execution_time is None or self.last_execution_time < mod_time:
            return full_name
        
    @abstractmethod
    def perform_housekeeping_on(self, schemas:List[str]):
        """
        Abstract method for concrete subclasses to actually perform their houskeeping on.

        Args:
            schemas (List[str]): List of schema files to perform housekeeping on.
        """
        pass
        
class BadSchemaHousekeeping(SchemaHousekeeping):
    """
    Regularly check for bad schemas.
    """

    def __init__(self, sleep_seconds:float = 60.0 * 30.0):
        super().__init__(sleep_seconds)

    def perform_housekeeping_on(self, schemas:List[str]):
        """
        Check the specified schema for syntactical correctness and matching IRI in the schema for this server. This is to prevent issues at runtime.
        Return the schema name if the schema contains an error, return None otherwise.
        """
        result = []
        for full_name in schemas:
            try:
                g = Graph()
                g.parse(full_name)
                found = False
                schema_path = full_name[len(CONTENT_DIR):len(full_name)-len(full_name[full_name.rfind('.'):len(full_name)])]
                for ( s, p, o) in g:
                    # want to be sure that the schema refers back to this server
                    # at least once in an RDF-triple
                    if found is False:
                        found = str(s).find(schema_path) > -1 or str(p).find(schema_path) > -1 or str(o).find(schema_path) > -1
                    if found is True:
                        break
                if found is False:
                    raise Exception("Schema '{}' doesn't seem to have any origin on this server.")
            except Exception as x:
                log.warn("Housekeeping: Detected issues with schema '{}':{}".format(full_name, x))
                result.append(full_name)
        global BAD_SCHEMAS
        BAD_SCHEMAS = result

@app.on_event("startup")
def init():
    log.info("Welcome to Shapiro.")
    log.info("Using '{}' as content dir.".format(CONTENT_DIR))
    log.info("Ignoring the following namespace for validation inference: {}".format(IGNORE_NAMESPACES))
    global HOUSEKEEPERS
    HOUSEKEEPERS.append(BadSchemaHousekeeping())
    for h in HOUSEKEEPERS:
        h.start()

@app.on_event("shutdown")
def shutdown():
    for h in HOUSEKEEPERS:
        h.stop()
        
@app.get("/{schema_path:path}",  status_code=200)
async def get_schema(schema_path:str, accept_header=Header(None)):
    """
    Serve the ontology/schema/model under the specified schema path in the mime type
    specified in the accept header.
    Currently supported mime types are 'application/ld+json', 'text/turtle'.
    """
    if accept_header is None:
        accept_header=''
    log.info("Retrieving schema '{}' with accept-headers '{}'".format(schema_path, accept_header))
    try:
        result = resolve(accept_header, schema_path)
        if result is None:
            err_msg = "Schema '{}' not found".format(schema_path)
            log.error(err_msg)
            return JSONResponse(content={'err_msg':err_msg}, status_code = status.HTTP_404_NOT_FOUND)
        return Response(content=result['content'], media_type=result['mime_type'])
    except BadSchemaException:
        err_msg = "Schema '{}' is not syntactically correct or has other issues and cannot be served.".format(schema_path)
        log.error(err_msg)
        return JSONResponse(content={'err_msg':err_msg}, status_code = status.HTTP_406_NOT_ACCEPTABLE)

@app.post("/validate/{schema_path:path}", status_code=200)
async def validate(schema_path:str, request:Request):
    """
    Validate the data provided in the body of the request against the schema at the specified path.
    Returns status 200 OK with a validation report in JSONLD format (http://www.w3.org/ns/shacl#ValidationReport),
    if processing succeeded and resulted in a validation report - note that the validation report
    can still indicate that the provided data did not validate against the specified schema.
    If processing failed due to issues obtaining/parsing the data or the schema, returns 422 UNPROCESSABLE ENTITY.
    
    If no schema_path is provided, then validate the data provided in the body of the request against one or more schemas inferred from the
    data (by context or prefix) - this will validate the data against any schema referenced by the data.
    Returns status 200 OK with a collection of validation reports in JSONLD format (http://www.w3.org/ns/shacl#ValidationReport) keyed by schema against validation was run.
    """
    try:
        content_type = request.headers.get("content-type", "")
        supported = [MIME_TTL, MIME_JSONLD]
        if content_type not in supported:
            err_msg = "Data must be supplied as content-type one of '{}', not '{}''".format(supported, content_type)
            log.error(err_msg)
            return JSONResponse(content={'err_msg':err_msg}, status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
        data_format = None
        if content_type == MIME_TTL:
            data_format = 'ttl'
        if content_type == MIME_JSONLD:
            data_format = 'json-ld'
        data = await request.body()
        data_graph= Graph()
        data_graph.parse(data, format=data_format)
        if schema_path is None or schema_path == '':
            log.info("No schema path provided for validate request - inferring model to validate against.")
            return await validate_infer_model(request, data_graph, data_format)
        log.info("Validating data (formatted as {}) against schema {}.".format(data_format, schema_path))
        elems = schema_path.split('/')
        url = urlparse(request.url._url)
        schema_graph = None
        alt_netloc = url.netloc
        if 'localhost' in url.netloc:
            alt_netloc = url.netloc.replace('localhost', '127.0.0.1')
        if '127.0.0.1' in url.netloc:
            alt_netloc = url.netloc.replace('127.0.0.1', 'localhost')
        if ('.' in elems[0] or ':' in elems[0] or 'localhost' in elems[0]) and not url.netloc in schema_path and not alt_netloc in schema_path: # last 2 predicates avoid doing remote calls to this server
            # this is the host name of some other server, so let pyshacl resolve the URI
            schema_graph = 'http://' + schema_path
            log.info("Resolving remote schema at '{}'".format(schema_graph))
            log.info("Request URL is '{}'".format(request.url._url))
        else:
            mod_schema_path = schema_path
            if url.netloc in schema_path:
                mod_schema_path = schema_path[schema_path.find(url.netloc)+len(url.netloc):len(schema_path)]
            elif alt_netloc in schema_path:
                mod_schema_path = schema_path[schema_path.find(alt_netloc)+len(alt_netloc):len(schema_path)]
            schema_response = await get_schema(mod_schema_path, MIME_TTL)
            if schema_response.status_code == status.HTTP_404_NOT_FOUND:
                raise Exception("Schema '{}' not found on this server - do you have the right schema name or is the feature to serve schemas switched off in this server?".format(schema_path))
            else:
                schema = schema_response.body
                schema_graph = Graph()
                schema_graph.parse(schema, format='ttl')
                log.info("Resolving local schema at '{}'".format(schema_path))
        result = pyshacl.validate( data_graph, shacl_graph=schema_graph, inference='rdfs', serialize_report_graph='json-ld')
        log.info("Successfully created validation report.")
        report = json.loads(result[1])
        return JSONResponse(content=report, media_type=MIME_JSONLD)
    except Exception as x:
        err_msg = "Could not validate provided data against schema {}. Error details: {}".format(schema_path, x)
        log.error(err_msg)
        return JSONResponse(content={'err_msg':err_msg}, status_code = status.HTTP_422_UNPROCESSABLE_ENTITY)

async def validate_infer_model(request:Request, data_graph:Graph, data_format:str):
    """
    Validate the data provided in the body of the request against one or more schemas inferred from the
    data (by context or prefix) - this will validate the data against any schema referenced by the data.
    Returns status 200 OK with a collection of validation reports in JSONLD format (http://www.w3.org/ns/shacl#ValidationReport) keyed by schema against validation was run,
    if processing succeeded and resulted in one or more validation reports (in case there were references to multiple schemas) - note that the validation report
    can still indicate that the provided data did not validate against the specified schema.
    If processing failed due to issues obtaining/parsing the data or the schema, returns 422 UNPROCESSABLE ENTITY.
    """
    # need to infer the schema graph(s) to validate against
    # we do this by extracting the schema prefixes and validating
    # the data against every prefix
    schema_graphs = []
    for (s, p, o) in data_graph:
        iri = extract_base(str(s))
        if iri is not None and iri not in schema_graphs:
            schema_graphs.append(iri)
        iri = extract_base(str(p))
        if iri is not None and iri not in schema_graphs:
            schema_graphs.append(iri)
        iri = extract_base(str(o))
        if iri is not None and iri not in schema_graphs:
            schema_graphs.append(iri)
    for i in IGNORE_NAMESPACES:
        for s in schema_graphs:
            if i in s:
                schema_graphs.remove(s)
    log.info("Validating data (formatted as {}) against {} schemas: {}".format(data_format, len(schema_graphs), schema_graphs))
    results = {}
    for s in schema_graphs:
        validation_response = await validate(s, request)
        results[s] = json.loads(validation_response.body)
    log.info("Successfully created {} validation reports.".format(len(results)))
    response = JSONResponse(content=jsonable_encoder(results), media_type=MIME_JSONLD, status_code=200)
    return response

def extract_base(iri:str):
    """
    If the IRI contains an anchor and a protocol, strip it away.
    """
    if iri.startswith('file://'): # some libraries mark non-iri id's as file-based iri's. we ignore these.
        return None
    pos = iri.find('#')
    if pos > 0:
        iri = iri[0:pos]
    pos = iri.find('://')
    if pos > 0:
        iri = iri[pos+3:len(iri)]
        return iri
    #plain string literal, not an iri, ignore
    return None

def resolve(accept_header:str, path:str):
    """
    Resolve the specified path to one of the mime types
    in the specified accept header.
    """
    mime_type = negotiate(accept_header)
    filename = map_filename(path)
    if filename is None:
        return None
    f = open(filename, 'r')
    content = f.read()
    f.close()
    return convert(filename, content, mime_type)

def convert(filename:str, content:str, mime_type:str):
    """
    Convert the content (from the specified filename) to the format
    according to the specified mime type.
    """
    if filename in BAD_SCHEMAS:
        raise BadSchemaException()
    if mime_type == MIME_JSONLD:
        if filename.endswith(SUFFIX_JSONLD):
            log.info("No conversion needed for '{}' and mime type '{}'".format(filename, mime_type))
            return  {
                        'content': content,
                        'mime_type': mime_type
                    }
        if filename.endswith(SUFFIX_TTL):
            log.info("Converting '{}' to mime type '{}'".format(filename, mime_type))
            g = Graph()
            g.parse(filename)
            return  {
                        'content': g.serialize(format='json-ld'),
                        'mime_type': mime_type
                    }
    if mime_type == MIME_TTL:
        if filename.endswith(SUFFIX_JSONLD):
            log.info("Converting '{}' to mime type '{}'".format(filename, mime_type))
            g = Graph()
            g.parse(filename)
            return  {
                        'content': g.serialize(format='ttl'),
                        'mime_type': mime_type
                    }
        if filename.endswith(SUFFIX_TTL):
            log.info("No conversion needed for '{}' and mime type '{}'".format(filename, mime_type))
            return  {
                        'content': content,
                        'mime_type': mime_type
                    }
    log.warn("No conversion possible for content path '{}' and mime type '{}'".format(filename, mime_type))
    return None

def map_filename(path:str):
    """
    Take the hierarchical path specified and identify the file with the ontology content that this
    path maps to.
    """
    # is last element of the path the name of a file with one of the supported suffixes?
    candidates = []
    full_path = CONTENT_DIR + path
    for s in SUPPORTED_SUFFIXES:
        current = full_path + s
        if os.path.isfile(current):
            candidates.append(current)
    # it is not, so assume that last element of the path is an element in the file
    full_path =  full_path[0:full_path.rfind('/')]
    for s in SUPPORTED_SUFFIXES:
        current = full_path + s
        if os.path.isfile(current):
            candidates.append(current)
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) == 0:
        log.error("Could not map '{}' to a schema file with one of the supported suffixes {}.".format(path, SUPPORTED_SUFFIXES))
    if len(candidates) > 0:
        log.error("Multiple candidates found trying to map '{}' to a schema file with one of the supported suffixes {}: {}".format(path, SUPPORTED_SUFFIXES, candidates))
    return None

def get_ranked_mime_types(accept_header:str):
    """
    Parse the accept header into an ordered array where the highest ranking
    mime type comes first. If multiple mime types have the same q-factor assigned,
    they will be taken in the order as specified in the accept header.
    """
    mime_types = accept_header.split(",")
    weights = []
    q_buckets = {}
    for mime_type in mime_types:
        if mime_type.split(";")[0] == mime_type:
            # no quality factor
            if 1.0 not in weights:
                weights.append(1.0)
            if '1.0' not in q_buckets.keys():
                q_buckets['1.0'] = []
            q_buckets['1.0'].append(mime_type)
        else:
            q = mime_type.split(";")[1].split("=")[1]
            if float(q) not in weights:
                weights.append(float(q))
            if q not in q_buckets.keys():
                q_buckets[q] = []
            q_buckets[q].append(mime_type.split(";")[0])
    result = []
    weights.sort(reverse=True)
    for w in weights:
        result = result + q_buckets[str(w)]
    return result

def find_preferred_mime(accept_header:str):
    """
    Match between the accept header from client and the supported mime types.
    """
    for m in get_ranked_mime_types(accept_header):
        if m.lower() in SUPPORTED_MIME_TYPES:
            return m
    return None

def negotiate(accept_header:str):
    """
    Negotiate a mime type with which the server should reply.
    """
    preferred = find_preferred_mime(accept_header)
    if preferred is None:
        log.warning("No supported mime type found in accept header - resorting to default ({})".format(MIME_DEFAULT))
        preferred = MIME_DEFAULT
    return preferred

def get_args(args):
    """
    Defines and parses the commandline parameters for running the server.
    """
    parser = argparse.ArgumentParser('Runs the Shapiro server.')
    parser.add_argument('--host', help='The host for uvicorn to use. Defaults to 127.0.0.1', type=str, default='127.0.0.1')
    parser.add_argument('--port', help='The port for the server to receive requests on. Defaults to 8000.', type=int, default=8000)
    parser.add_argument('--content_dir', help='The content directory to be used. Defaults to "./"', type=str, default='./')
    parser.add_argument('--log_level', help='The log level to run with. Defaults to "info"', type=str, default='info')
    parser.add_argument('--default_mime', help='The mime type to use for formatting served ontologies if the mimetype in the accept header is not available or usable. Defaults to "text/turtle"', type=str, default='text/turtle')
    parser.add_argument('--features', help="What features should be enabled in the API. Either 'serve' (for serving ontologies) or 'validate' (for validating data against ontologies) or 'all'. Default is 'all'.",
        type=str, default='all', choices = ['all', 'serve', 'validate'])
    parser.add_argument('--ignore_namespaces', help="A list of namespaces that wilkl be ignored when inferring schemas to validate data against. Specify as space-separated list of namespaces. Default is ['schema.org','w3.org','example.org']", nargs='*', default = ['schema.org', 'w3.org', 'example.org'])
    return parser.parse_args(args)

def get_server(host:str, port:int, content_dir:str, log_level:str, default_mime:str, ignore_namespaces:List[str]):
    global CONTENT_DIR
    CONTENT_DIR = content_dir
    if not CONTENT_DIR.endswith('/'):
        CONTENT_DIR += '/'
    global MIME_DEFAULT
    MIME_DEFAULT = default_mime
    global IGNORE_NAMESPACES
    IGNORE_NAMESPACES = ignore_namespaces
    config = uvicorn.Config(app, host=host, port=port, workers=5, log_level=log_level)
    server = uvicorn.Server(config)
    return server

def activate_routes(features:str):
    """
    Disable the routes according to the features spec ('serve' to onlky serve schemas, 'validate' to only validate schemas,
    'all' to both serve and validate).
    """
    global ROUTES
    if ROUTES is None:
        ROUTES = copy.copy(app.routes) # save original list of routes
    for r in ROUTES: # restore original list of routes
        if r not in app.routes:
            app.routes.append(r)
    for r in app.routes:
        if (features == 'validate' and r.name == 'get_schema') or (features == 'serve' and r.name == 'validate'):
            app.routes.remove(r)

async def start_server(host:str, port:int, content_dir:str, log_level:str, default_mime:str, features:str, ignore_namespaces:List[str]):
    activate_routes(features)
    server = await get_server(host, port, content_dir, log_level, default_mime, ignore_namespaces).serve()

def main(args):
    args = get_args(args)
    asyncio.run(start_server(args.host, args.port, args.content_dir, args.log_level, args.default_mime, args.features, args.ignore_namespaces))

if __name__ == "__main__":
    main(sys.argv[1:])
