import uvicorn
import asyncio
import argparse
from fastapi import FastAPI, Response, Request, status, Header
import logging
import os
import sys
from rdflib import Graph
from pyshacl import validate

MIME_HTML = "text/html"
MIME_JSONLD = "application/ld+json"
MIME_TTL = "text/turtle"
MIME_JSONSCHEMA = "application/json"
MIME_DEFAULT = MIME_TTL

SUFFIX_JSONLD = '.jsonld'
SUFFIX_TTL = '.ttl'
SUPPORTED_SUFFIXES = [ SUFFIX_JSONLD, SUFFIX_TTL ]

SUPPORTED_MIME_TYPES = [MIME_JSONLD, MIME_TTL]

CONTENT_DIR = './'
BAD_SCHEMAS = []

log = logging.getLogger("uvicorn")

app = FastAPI()

class BadSchemaException(Exception):

    def __init__(self):
        pass

@app.on_event("startup")
def init():
    log.info("Welcome to Shapiro.")
    log.info("Using '{}' as content dir.".format(CONTENT_DIR))
    log.info("Checking schema files.")
    global BAD_SCHEMAS
    BAD_SCHEMAS = check_schemas(CONTENT_DIR)

@app.get("/{schema_path:path}",  status_code=200)
async def get_schema(schema_path:str, request:Request, response:Response, accept_header=Header(None)):
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
            response.status_code=status.HTTP_404_NOT_FOUND
            err_msg = "Schema '{}' not found".format(schema_path)
            log.error(err_msg)
            return err_msg
        return Response(content=result['content'], media_type=result['mime_type'])
    except BadSchemaException:
        response.status_code=status.HTTP_406_NOT_ACCEPTABLE
        err_msg = "Schema '{}' is not syntactically correct or has other issues and cannot be served.".format(schema_path)
        log.error(err_msg)
        return err_msg

def check_schemas(content_dir:str):
    """
    Traverse the CONTENT_DIR to verify each schema file with one of the supported suffixes
    for syntactical correctness. This is to prevent issues at runtime.
    Returns an array of "bad files".
    """
    result = []
    for dir in os.walk(content_dir):
        path = dir[0]
        for filename in dir[2]:
            suffix = filename[filename.rfind('.'):len(filename)]
            full_name = path+os.path.sep+filename
            if suffix in SUPPORTED_SUFFIXES:
                try:
                    g = Graph()
                    g.parse(full_name)
                except Exception as x:
                    log.error("Cannot parse schema '{}':{}".format(full_name, x))
                    result.append(full_name)
    if len(result) > 0:
        log.error("Found {} bad files: {}.".format(len(result), result))
        log.error("Requests to serve these files will be reponded to with HTTP Status 406.")
    else:
        log.info("No bad schemas found.")
    return result

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
    full_path =  full_path[0:full_path.rfind(os.path.sep)]
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
    return parser.parse_args(args)

def get_server(host:str, port:int, content_dir:str, log_level:str, default_mime:str):
    global CONTENT_DIR
    CONTENT_DIR = content_dir
    if not CONTENT_DIR.endswith(os.path.sep):
        CONTENT_DIR += os.path.sep
    global MIME_DEFAULT
    MIME_DEFAULT = default_mime
    config = uvicorn.Config(app, host=host, port=port, log_level=log_level)
    server = uvicorn.Server(config)
    return server

async def start_server(host:str, port:int, content_dir:str, log_level:str, default_mime:str):
    await get_server(host, port, content_dir, log_level, default_mime).serve()

def main(args):
    args = get_args(args)
    asyncio.run(start_server(args.host, args.port, args.content_dir, args.log_level, args.default_mime))

if __name__ == "__main__":
    main(sys.argv[1:])
