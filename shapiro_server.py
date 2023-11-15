from abc import abstractmethod
import colorlog
import uvicorn
import asyncio
import argparse
from fastapi import FastAPI, Response, Request, status, Header
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, RedirectResponse
import logging
import os
from rdflib import Graph
import pyshacl
import json
import copy
from urllib.parse import urlparse, ParseResult
from typing import List
from threading import Thread, Event
from datetime import datetime
from whoosh.fields import Schema, TEXT, ID
from whoosh.analysis import StemmingAnalyzer
import whoosh.index as whoosh_index
from whoosh.qparser import MultifieldParser
from liquid import Environment
from liquid import Mode
from liquid import StrictUndefined
from liquid import FileSystemLoader
from shapiro_render import HtmlRenderer, JsonSchemaRenderer
from shapiro_util import BadSchemaException, NotFoundException, ConflictingPropertyException, get_logger
from multiprocessing import Process

MIME_HTML = "text/html"
MIME_JSONLD = "application/ld+json"
MIME_TTL = "text/turtle"
MIME_JSONSCHEMA = "application/schema+json"
MIME_JSON = "application/json"
MIME_DEFAULT = MIME_JSONSCHEMA

SUFFIX_JSONLD = ".jsonld"
SUFFIX_TTL = ".ttl"
SUPPORTED_SUFFIXES = [SUFFIX_JSONLD, SUFFIX_TTL]

SUPPORTED_MIME_TYPES = [
    MIME_JSONLD.lower(),
    MIME_TTL.lower(),
    MIME_HTML.lower(),
    MIME_JSONSCHEMA.lower(),
]

IGNORE_NAMESPACES = []

CONTENT_DIR = "./"
INDEX_DIR = "./fts_index"
BAD_SCHEMAS = {}
ROUTES = None
HOUSEKEEPERS = []

BASE_URL = None

EKG = None

HTML_RENDERER = HtmlRenderer()

JSONSCHEMA_RENDERER = JsonSchemaRenderer()

log = get_logger("SHAPIRO_SERVER")

app = FastAPI()

env = Environment(
    tolerance=Mode.STRICT,
    undefined=StrictUndefined,
    loader=FileSystemLoader("templates/"),
)


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

    def check_for_schema_updates(self):
        log.info("Housekeeping: Checking schema files for modifications.")
        schemas_to_check = walk_schemas(CONTENT_DIR, self.check_schema)
        log.info(
            "Housekeeping detected {} modified schemas.".format(len(schemas_to_check))
        )
        self.last_execution_time = datetime.now()
        self.perform_housekeeping_on(schemas_to_check)

    def check_schema(self, path: str, full_name: str, schema_path: str, suffix: str):
        mod_time = datetime.fromtimestamp(os.stat(full_name).st_mtime)
        if self.last_execution_time is None or self.last_execution_time < mod_time:
            return full_name

    @abstractmethod
    def perform_housekeeping_on(self, schemas: List[str]):
        """
        Abstract method for concrete subclasses to actually perform their houskeeping on.

        Args:
            schemas (List[str]): List of schema files to perform housekeeping on.
        """
        pass


class EKGHouseKeeping(SchemaHousekeeping):
    """
    Build/rebuild the Knowledge Graph of all schemas, so it
    can be queried in its entirety using SPARQL.
    """

    def __init__(self, sleep_seconds: float = 60.0 * 10.0):
        super().__init__(sleep_seconds)

    def perform_housekeeping_on(self, schemas: List[str]):
        """
        Build/rebuild the Knowledge Graph of all schemas, so it
        can be queried in its entirety using SPARQL.
        """
        global EKG
        if EKG is None or len(schemas) > 0:
            log.info("EKG Housekeeping: Rebuilding knowledge graph.")
            EKG = Graph()
            walk_schemas(CONTENT_DIR, self.add_schema)

    def add_schema(self, path: str, full_name: str, schema_path: str, suffix: str):
        if full_name not in BAD_SCHEMAS.keys():
            try:
                with open(full_name, "r") as f:
                    EKG.parse(file=f)
                log.info(
                    "EKG Housekeeping: Ingested '{}' into knowledge graph.".format(
                        full_name
                    )
                )
            except Exception as x:
                log.error(
                    "EKG Housekeeping: Could not ingest '{}' into knowledge graph: {}".format(
                        schema_path, x
                    )
                )


class BadSchemaHousekeeping(SchemaHousekeeping):
    """
    Regularly check for bad schemas.
    """

    def __init__(self, sleep_seconds: float = 60.0 * 10.0):
        super().__init__(sleep_seconds)

    def perform_housekeeping_on(self, schemas: List[str]):
        """
        Check the specified schema for syntactical correctness and matching IRI in the schema for this server.
        This is to prevent issues at runtime.
        Return the schema name if the schema contains an error, return None otherwise.
        """
        global BAD_SCHEMAS
        for full_name in schemas:
            try:
                g = Graph().parse(full_name)
                found = False
                schema_path = get_schema_path(full_name)
                if schema_path.startswith("/"):
                    path = (
                        BASE_URL + schema_path[1 : len(schema_path)]
                    )  # skip leading '/' of schema path
                else:
                    path = BASE_URL + schema_path
                for s, p, o in g:
                    # want to be sure that the schema refers back to this server
                    # at least once in an RDF-triple
                    if found is False:
                        found = (
                            str(s).lower().find(path.lower()) > -1
                            or str(p).lower().find(path.lower()) > -1
                            or str(o).lower().find(path.lower()) > -1
                        )
                    if found is True:
                        break
                if found is False:
                    raise Exception(
                        "Bad Schema Housekeeping: Schema '{}' doesn't seem to have any origin on this server or is not in the right directory on this server.".format(
                            path
                        )
                    )
                if full_name in BAD_SCHEMAS.keys():
                    del BAD_SCHEMAS[
                        full_name
                    ]  # it was a bad schema, but changed and now is a good schema
                    log.info(
                        "Bad Schema Housekeeping: Removed {} from list of bad schemas. BAD_SCHEMAS is now {}".format(
                            full_name, BAD_SCHEMAS.keys()
                        )
                    )
            except Exception as x:
                log.warning(
                    "Bad Schema Housekeeping: Detected issues with schema '{}':{}".format(
                        full_name, x
                    )
                )
                if full_name not in BAD_SCHEMAS.keys():
                    BAD_SCHEMAS[full_name] = str(x)
                    log.info(
                        "Bad Schema Housekeeping: Appended {} to list of bad schemas. BAD_SCHEMAS is now {}".format(
                            full_name, BAD_SCHEMAS.keys()
                        )
                    )
                else:
                    log.info(
                        "Bad Schema Housekeeping: {} already in list of bad schemas.".format(
                            full_name
                        )
                    )


class SearchIndexHousekeeping(SchemaHousekeeping):
    """
    Regularly index new or changed schemas in the search index for providing full text search in schemas.
    """

    def __init__(self, index_dir: str = INDEX_DIR, sleep_seconds: float = 60.0 * 10.0):
        super().__init__(sleep_seconds)
        schema = Schema(
            full_name=ID(stored=True), content=TEXT(analyzer=StemmingAnalyzer())
        )
        log.info(
            "Full-text Search Housekeeping: Using index directory '{}'".format(
                index_dir
            )
        )
        if os.path.exists(index_dir) == False:
            log.info("Housekeeping: Creating search index for schemas.")
            os.mkdir(index_dir)
            self.index = whoosh_index.create_in(index_dir, schema)
        else:
            log.info(
                "Full-text Search Housekeeping: Using existing search index for schemas."
            )
            try:
                self.index = whoosh_index.open_dir(index_dir)
            except:
                log.error(
                    "Full-text Search Houskeeping: Index directory does not contain index files."
                )

    def perform_housekeeping_on(self, schemas: List[str]):
        """
        Index the schemas in the specified list.
        """
        writer = self.index.writer()
        for s in schemas:
            if s not in BAD_SCHEMAS.keys():
                with open(s, "r") as f:
                    log.info("Full-text Search Housekeeping: Indexing {}".format(s))
                    writer.update_document(full_name=s, content=f.read())
        writer.commit()

def get_version():
    version = { 'version': '' }
    with open('version.txt', 'r') as f:
        version['version'] = f.read().replace('\n','')
    return version

@app.on_event("startup")
def init():
    log.info("Welcome to Shapiro.")
    log.info("Using '{}' as content dir.".format(CONTENT_DIR))
    log.info(
        "Ignoring the following namespace for validation inference: {}".format(
            IGNORE_NAMESPACES
        )
    )
    global HOUSEKEEPERS
    b = BadSchemaHousekeeping()
    b.check_for_schema_updates()  # run once synchronously so all other housekeepers can ignore quarantined schemas
    HOUSEKEEPERS.append(b)
    HOUSEKEEPERS.append(SearchIndexHousekeeping())
    HOUSEKEEPERS.append(EKGHouseKeeping())
    for h in HOUSEKEEPERS:
        h.start()


@app.on_event("shutdown")
def shutdown():
    for h in HOUSEKEEPERS:
        h.stop()


@app.get("/static/{name}", status_code=200)
async def get_static_resource(name: str):
    """
    Serve static artefacts for HTML views.
    """
    name = "static/" + name
    mime = "text/html"
    if name.endswith(".png"):
        mime = "image/png"
    if name.endswith(".js"):
        mime = "text/javascript"
    if name.endswith(".css"):
        mime = "text/css"
    if name.endswith(".ico"):
        mime = "image/x-icon"
    with open(name, "rb") as f:
        static_content = f.read()
        return Response(content=static_content, media_type=mime)


@app.get("/welcome/", status_code=200)
async def welcome(request: Request):
    """
    Render a welcome page.
    """
    welcome_page = env.get_template("main.html").render(url=BASE_URL, version=get_version()['version'])
    return HTMLResponse(content=welcome_page)

@app.get("/version/", status_code=200)
async def version(request: Request):
    """
    Return the version of Shapiro.
    """
    return JSONResponse(content=get_version())

@app.get("/schemas/", status_code=200)
async def get_schema_list(request: Request):
    """
    Return a list of the schemas hosted in this repository as JSON-data.
    """
    log.info("Retrieving list of schemas")
    result = walk_schemas(
        CONTENT_DIR,
        lambda path, full_name, schema_path, suffix: {
            "schema_path": schema_path,
            "full_name": full_name,
            "link": str(BASE_URL) + schema_path,
        }
        if full_name not in BAD_SCHEMAS.keys()
        else None,
    )
    return JSONResponse(content={"schemas": result})


@app.get("/badschemas/", status_code=200)
async def get_badschema_list(request: Request):
    """
    Return a list of the bad schemas JSON-data. The bad schemas have issues (either syntactially or they are not rooted
    on this server's BASE_URL), so Shapiro quanrantines them and does not serve them)
    """
    log.info("Retrieving list of bad schemas")
    result = {"badschemas": []}
    for k in BAD_SCHEMAS.keys():
        result["badschemas"].append({"name": k, "reason": BAD_SCHEMAS[k]})
    return JSONResponse(content=result)


@app.get("/search/", status_code=200)
async def search(query: str = None, request: Request = None):
    """
    Use the Whoosh full text search index for schemas to find the text specified in the query in the schema files
    served by this server. Returns hits in order of relevance.
    """
    if query is None or query == "":
        log.info("No search query specified, returning full schema list.")
        return await get_schema_list(request)
    log.info("Searching for '{}'".format(query))
    try:
        index = whoosh_index.open_dir(INDEX_DIR)
        qp = MultifieldParser(["content", "full_name"], schema=index.schema)
        q = qp.parse(query)
        hits = []
        with index.searcher() as searcher:
            result = searcher.search(q)
            log.info(result)
            for r in result:
                schema_path = get_schema_path(r["full_name"])
                hit = {
                    "schema_path": schema_path,
                    "full_name": r["full_name"],
                    "link": str(request.base_url) + schema_path,
                }
                if hit not in hits:
                    if r["full_name"] not in BAD_SCHEMAS.keys():
                        hits.append(hit)
        return JSONResponse(content={"schemas": hits})
    except Exception as x:
        log.error("Could not perform search: {}".format(x))
        return Response(content="Could not perform search.", status_code=500)


@app.get("/query/", status_code=200)
def query_page(request: Request):
    query_page = env.get_template("query.html").render(url=BASE_URL)
    return HTMLResponse(content=query_page)


@app.post("/query/", status_code=200)
async def query(request: Request):
    """
    Query the knowledge graph of all schemas with the SPARQL query
    specified in the request body and return the result.
    """
    query = await request.body()
    json = ""
    try:
        result = EKG.query(query)
        json = "["
        for r in result:
            if json[len(json) - 1] == "}":
                json += ","
            json += "{"
            for l in r.labels:
                if json[len(json) - 1] == '"':
                    json += ","
                json += '"' + l + '":' + '"' + str(r[l]) + '"'
            json += "}"
        json += "]"
        return JSONResponse(content=json, status_code=status.HTTP_200_OK)
    except Exception as x:
        log.error("Could not execute query: {}".format(x)+'\n'+json)
        return JSONResponse(
            content={"err_msg": str(x)},
            media_type="application/json",
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
        )


# usage of ":path"as per https://www.starlette.io/routing/#path-parameters
@app.get("/{schema_path:path}", status_code=200)
def get_schema(
    schema_path: str = None, accept_mime: str = None, request: Request = None
):
    """
    Serve the ontology/schema/model under the specified schema path in the mime type
    specified in the accept header.
    Currently supported mime types are 'application/ld+json', 'text/turtle'.
    """
    accept_header = accept_mime
    if accept_header == "" or accept_header is None:
        for k in request.headers.keys():
            if k.lower() == "accept":
                accept_header = request.headers.get("accept", "")
                break
    if schema_path is None or schema_path == "":
        log.info("No schema path specified - redirecting to welcome page.")
        return RedirectResponse("/welcome/")
    log.info(
        "Retrieving schema '{}' with accept-headers '{}'".format(
            schema_path, accept_header
        )
    )
    if schema_path.endswith("/"):
        schema_path = schema_path[0:len(schema_path)-1]
    try:
        result = resolve(accept_header, schema_path)
        if result is None:
            err_msg = "Schema '{}' not found".format(schema_path)
            log.error(err_msg)
            raise NotFoundException("Could not find schema {}".format(schema_path))
        return Response(content=result["content"], media_type=result["mime_type"])
    except BadSchemaException:
        err_msg = "Schema '{}' is not syntactically correct, does not have its origin on this server or has other issues and cannot be served.".format(
            schema_path
        )
        log.error(err_msg)
        if accept_header is None:
            accept_header = ""
        if MIME_HTML.lower() in accept_header.lower():
            return Response(
                env.get_template("error.html").render(url=BASE_URL, msg=err_msg),
                media_type="text/html",
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
            )
        else:
            return JSONResponse(
                content={"err_msg": err_msg}, status_code=status.HTTP_406_NOT_ACCEPTABLE
            )
    except NotFoundException as x:
        if MIME_HTML.lower() in accept_header.lower():
            return Response(
                env.get_template("error.html").render(url=BASE_URL, msg=x.content),
                media_type="text/html",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        else:
            return JSONResponse(
                content={"err_msg": x.content}, status_code=status.HTTP_404_NOT_FOUND
            )
    except ConflictingPropertyException as x:
        if MIME_HTML.lower() in accept_header.lower():
            return Response(
                env.get_template("error.html").render(url=BASE_URL, msg=str(x)),
                media_type="text/html",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        else:
            return JSONResponse(
                content={"err_msg": str(x)}, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
            )

def get_schema_graph(url:str, schema_path:str) -> Graph:
    schema_graph = None
    elems = schema_path.split("/")
    url_parsed = urlparse(url)
    alt_netloc = url_parsed.netloc
    if "localhost" in url_parsed.netloc:
        alt_netloc = url_parsed.netloc.replace("localhost", "127.0.0.1")
    if "127.0.0.1" in url_parsed.netloc:
        alt_netloc = url_parsed.netloc.replace("127.0.0.1", "localhost")
    if (
        ("." in elems[0] or ":" in elems[0] or "localhost" in elems[0])
        and url_parsed.netloc not in schema_path
        and alt_netloc not in schema_path
    ):  # last 2 predicates avoid doing remote calls to this server
        # this is the host name of some other server, so let pyshacl resolve the URI
        if BASE_URL.startswith("https://"):
            schema_graph = Graph().parse("https://" + schema_path)
        else:
            schema_graph = Graph().parse("http://" + schema_path)
        log.info("Resolving remote schema at '{}'".format(schema_path))
        log.info("Request URL is '{}'".format(url))
    else:
        mod_schema_path = schema_path
        if url_parsed.netloc in schema_path:
            mod_schema_path = schema_path[
                schema_path.find(url_parsed.netloc) + len(url_parsed.netloc) : len(schema_path)
            ]
        elif alt_netloc in schema_path:
            mod_schema_path = schema_path[
                schema_path.find(alt_netloc) + len(alt_netloc) : len(schema_path)
            ]
        schema_response = get_schema(mod_schema_path, MIME_TTL)
        if schema_response.status_code == status.HTTP_404_NOT_FOUND:
            raise Exception(
                """Schema '{}' not found on this server - do you have the right schema name or is the feature to
                serve schemas switched off in this server?""".format(
                    schema_path
                )
            )
        else:
            schema = schema_response.body
            schema_graph = Graph()
            schema_graph.parse(schema, format="ttl")
            log.info("Resolving local schema at '{}'".format(schema_path))
    return schema_graph

@app.post("/validate/{schema_path:path}", status_code=200)
async def validate(schema_path: str, request: Request):
    """
    Validate the data provided in the body of the request against the schema at the specified path.
    Returns status 200 OK with a validation report in JSONLD format (http://www.w3.org/ns/shacl#ValidationReport),
    if processing succeeded and resulted in a validation report - note that the validation report
    can still indicate that the provided data did not validate against the specified schema.
    If processing failed due to issues obtaining/parsing the data or the schema, returns 422 UNPROCESSABLE ENTITY.

    If no schema_path is provided, then validate the data provided in the body of the request against one or more
    schemas inferred from the data (by context or prefix) - this will validate the data against any schema referenced
    by the data.
    Returns status 200 OK with a of validation report in JSONLD format.
    """
    try:
        content_type = request.headers.get("content-type", "")
        supported = [MIME_TTL, MIME_JSONLD]
        if content_type not in supported:
            err_msg = (
                "Data must be supplied as content-type one of '{}', not '{}''".format(
                    supported, content_type
                )
            )
            log.error(err_msg)
            return JSONResponse(
                content={"err_msg": err_msg},
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            )
        data_format = None
        if content_type == MIME_TTL:
            data_format = "ttl"
        if content_type == MIME_JSONLD:
            data_format = "json-ld"
        data = await request.body()
        data_graph = Graph()
        data_graph.parse(data, format=data_format)
        if schema_path is None or schema_path == "":
            log.info(
                "No schema path provided for validate request - inferring model to validate against."
            )
            return await validate_infer_model(request, data_graph, data_format)
        log.info(
            "Validating data (formatted as {}) against schema {}.".format(
                data_format, schema_path
            )
        )
        schema_graph = get_schema_graph(request.url._url, schema_path)
        result = pyshacl.validate(
            data_graph
            + schema_graph,  # needed to ensure inheritance is picked up properly
            inference="rdfs",
            serialize_report_graph="json-ld",
        )
        log.info("Successfully created validation report.")
        report = json.loads(result[1])
        return JSONResponse(content=report, media_type=MIME_JSONLD)
    except Exception as x:
        err_msg = "Could not validate provided data against schema {}. Error details: {}".format(
            schema_path, x
        )
        log.error(err_msg)
        return JSONResponse(
            content={"err_msg": err_msg},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


async def validate_infer_model(request: Request, data_graph: Graph, data_format: str):
    """
    Validate the data provided in the body of the request against one or more schemas inferred from the
    data (by context or prefix) - this will validate the data against any schema referenced by the data.
    Returns status 200 OK with a collection of validation reports in JSONLD format
    (http://www.w3.org/ns/shacl#ValidationReport) keyed by schema against validation was run, if processing succeeded
    and resulted in one or more validation reports (in case there were references to multiple schemas) - note that the
    validation report can still indicate that the provided data did not validate against the specified schema.
    If processing failed due to issues obtaining/parsing the data or the schema, returns 422 UNPROCESSABLE ENTITY.
    """
    # need to infer the schema graph(s) to validate against
    # we do this by extracting the schema prefixes and validating
    # the data against every prefix
    schema_graphs = []
    for s, p, o in data_graph:
        iri = str(s)
        if iri is not None and iri.lower().startswith("http") and iri not in schema_graphs:
            schema_graphs.append(iri)
        iri = str(p)
        if iri is not None and iri.lower().startswith("http") and iri not in schema_graphs:
            schema_graphs.append(iri)
        iri = str(o)
        if iri is not None and iri.lower().startswith("http") and iri not in schema_graphs:
            schema_graphs.append(iri)
    for i in IGNORE_NAMESPACES:
        schema_graphs_copy = schema_graphs.copy()
        for s in schema_graphs_copy:
            if i in s:
                schema_graphs.remove(s)
    log.info(
        "Validating data (formatted as {}) against {} schemas: {}".format(
            data_format, len(schema_graphs), schema_graphs
        )
    )
    results = {}
    schema_graph = Graph()
    for s in schema_graphs:
        log.info("Getting schema graph {}".format(s))
        schema_graph += get_schema_graph(request.url._url, s)
    return await validate(s, request)  

def resolve(accept_header: str, path: str):
    """
    Resolve the specified path to one of the mime types
    in the specified accept header.
    """
    mime_type = negotiate(accept_header)
    filename = map_filename(path)
    if filename is None:
        return None
    f = open(filename, "r")
    content = f.read()
    f.close()
    result = convert(path, filename, content, mime_type)
    return result


def convert(path: str, filename: str, content: str, mime_type: str):
    """
    Convert the content (from the specified iri-path and filename) to the format
    according to the specified mime type.
    """
    if filename in BAD_SCHEMAS.keys():
        raise BadSchemaException()
    if mime_type == MIME_HTML:
        if filename[0 : filename.rfind(".")].endswith(path):
            return {
                "content": HTML_RENDERER.render_model(BASE_URL, BASE_URL + path),
                "mime_type": mime_type,
            }
        else:
            return {
                "content": HTML_RENDERER.render_model_element(
                    BASE_URL, BASE_URL + path
                ),
                "mime_type": mime_type,
            }
    if mime_type == MIME_JSONLD:
        if filename.endswith(SUFFIX_JSONLD):
            log.info(
                "No conversion needed for '{}' and mime type '{}'".format(
                    filename, mime_type
                )
            )
            return {"content": content, "mime_type": mime_type}
        if filename.endswith(SUFFIX_TTL):
            log.info("Converting '{}' to mime type '{}'".format(filename, mime_type))
            g = Graph()
            g.parse(filename)
            return {"content": g.serialize(format="json-ld"), "mime_type": mime_type}
    if mime_type == MIME_TTL:
        if filename.endswith(SUFFIX_JSONLD):
            log.info("Converting '{}' to mime type '{}'".format(filename, mime_type))
            g = Graph()
            g.parse(filename)
            return {"content": g.serialize(format="ttl"), "mime_type": mime_type}
        if filename.endswith(SUFFIX_TTL):
            log.info(
                "No conversion needed for '{}' and mime type '{}'".format(
                    filename, mime_type
                )
            )
            return {"content": content, "mime_type": mime_type}
    if mime_type == MIME_JSONSCHEMA or mime_type == MIME_JSON:
        log.info("Converting '{}' to mime type '{}'".format(filename, mime_type))
        return {
            "content": JSONSCHEMA_RENDERER.render_nodeshape(BASE_URL + path),
            "mime_type": mime_type,
        }
    log.warning(
        "No conversion possible for content path '{}' and mime type '{}'".format(
            filename, mime_type
        )
    )
    return None


def map_filename(path: str):
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
    pruned_path = full_path[0 : full_path.rfind("/")]
    for s in SUPPORTED_SUFFIXES:
        current = pruned_path + s
        if os.path.isfile(current):
            candidates.append(current)
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) == 0:
        log.error(
            "Could not map '{}' to a schema file with one of the supported suffixes {}.".format(
                path, SUPPORTED_SUFFIXES
            )
        )
    if len(candidates) > 0:
        log.error(
            """Multiple candidates found trying to map '{}' to a schema file
               with one of the supported suffixes {}: {}""".format(
                path, SUPPORTED_SUFFIXES, candidates
            )
        )
    return None


def get_ranked_mime_types(accept_header: str):
    """
    Parse the accept header into an ordered array where the highest ranking
    mime type comes first. If multiple mime types have the same q-factor assigned,
    they will be taken in the order as specified in the accept header.
    """
    if accept_header is None:
        accept_header = ""
    mime_types = accept_header.split(",")
    weights = []
    q_buckets = {}
    for mime_type in mime_types:
        mime_type = mime_type.strip()
        if mime_type.split(";")[0] == mime_type:
            # no quality factor
            if 1.0 not in weights:
                weights.append(1.0)
            if "1.0" not in q_buckets.keys():
                q_buckets["1.0"] = []
            q_buckets["1.0"].append(mime_type)
        else:
            for k in mime_type.split(";"):  # there is not only q factors
                key = k.split("=")[0]
                if key.lower() == "q":  # only process q-weights
                    q = k.split("=")[1]
                    q = float(q)
                    if q not in weights:
                        weights.append(q)
                    q = str(q)
                    if q not in q_buckets.keys():
                        q_buckets[q] = []
                    q_buckets[q].append(mime_type.split(";")[0])

    result = []
    weights.sort(reverse=True)
    for w in weights:
        result = result + q_buckets[str(w)]
    return result


def find_preferred_mime(accept_header: str):
    """
    Match between the accept header from client and the supported mime types.
    """
    for m in get_ranked_mime_types(accept_header):
        if m.lower() in SUPPORTED_MIME_TYPES:
            return m
    return None


def negotiate(accept_header: str):
    """
    Negotiate a mime type with which the server should reply.
    """
    preferred = find_preferred_mime(accept_header)
    if preferred is None:
        log.warning(
            "No supported mime type found in accept header - resorting to default ({})".format(
                MIME_DEFAULT
            )
        )
        preferred = MIME_DEFAULT
    return preferred


def get_suffix(full_name: str):
    """
    Extract the file suffix from the full name of a schema file.
    """
    return full_name[full_name.rfind(".") : len(full_name)]


def get_schema_path(full_name: str):
    """
    Extract the schema path from the full_name of a schema file.
    """
    return full_name[len(CONTENT_DIR) : len(full_name) - len(get_suffix(full_name))]


def walk_schemas(content_dir: str, visit_schema):
    """
    Walk the hierarchy at content_dir and call the function specified under visit_schema.
    visit_schema is a function that takes four string parameters: path (the hierarchical name the schema sits under,
    without the actual schema name), full_name (the fully qualified path to the file containing the schema), the schema
    path (the fully qualified name of the schema) and suffix (the suffix of the file containing the schema).
    visit_schema must return either None or a value. If it returns a value that value is collected and the collection of
    values is returned as the result of this function (walk_schemas).
    """
    result = []
    for dir in os.walk(content_dir):
        path = dir[0].replace("\\", "/").replace(os.path.sep, "/")
        for filename in dir[2]:
            suffix = get_suffix(filename)
            if path.endswith("/"):
                full_name = path + filename
            else:
                full_name = path + "/" + filename
            if suffix in SUPPORTED_SUFFIXES:
                schema_path = get_schema_path(full_name)
                visit_result = visit_schema(path, full_name, schema_path, suffix)
                if visit_result is not None:
                    result.append(visit_result)
    return result


def get_args(argv=[]):
    """
    Defines and parses the commandline parameters for running the server.
    """
    parser = argparse.ArgumentParser("Runs the Shapiro server.")
    parser.add_argument(
        "--host",
        help="The host for uvicorn to use. Defaults to 127.0.0.1",
        type=str,
        default="127.0.0.1",
    )
    parser.add_argument(
        "--port",
        help="The port for the server to receive requests on. Defaults to 8000.",
        type=int,
        default=8000,
    )
    parser.add_argument(
        "--domain",
        help="""The domain that Shapiro uses to build its BASE_URL. Defaults to '127.0.0.1:8000' and is typically set to the domain name
                under which you deploy Shapiro.
                This is what Shapiro uses to ensure schemas are rooted on its server, to build links in the HTML docs 
                and it's also the URL Shapiro uses to resolve static resources in HTML renderings. 
                Include the port if needed. Examples: --domain schemas.myorg.com, --domain schemas.myorg.com:1234""",
        type=str,
        default="127.0.0.1:8000",
    )
    parser.add_argument(
        "--content_dir",
        help='The content directory to be used. Defaults to "./"',
        type=str,
        default="./",
    )
    parser.add_argument(
        "--log_level",
        help='The log level to run with. Defaults to "info"',
        type=str,
        default="info",
    )
    parser.add_argument(
        "--default_mime",
        help="""The mime type to use for formatting served ontologies if the mimetype in the accept header is not 
                available or usable. Defaults to "text/turtle".""",
        type=str,
        default=MIME_DEFAULT,
    )
    parser.add_argument(
        "--features",
        help="""What features should be enabled in the API. Either 'serve' (for serving ontologies) or 'validate' 
                (for validating data against ontologies) or 'all'. Default is 'all'.""",
        type=str,
        default="all",
        choices=["all", "serve", "validate"],
    )
    parser.add_argument(
        "--ignore_namespaces",
        help="""A list of namespaces that wilkl be ignored when inferring schemas to validate data against.
                Specify as space-separated list of namespaces. Default is ['schema.org','w3.org','example.org']""",
        nargs="*",
        default=["schema.org", "w3.org", "example.org"],
    )
    parser.add_argument(
        "--index_dir",
        help="The directory where Shapiro stores the full-text-search indices. Default is ./fts_index",
        default="./fts_index/",
    )
    parser.add_argument("--ssl_keyfile", help="SSL key file")
    parser.add_argument("--ssl_certfile", help="SSL certificates file")
    parser.add_argument("--ssl_ca_certs", help="CA certificates file")
    return parser.parse_args(argv)


def build_base_url(domain: str, is_ssl: bool):
    global BASE_URL
    if is_ssl == True:
        BASE_URL = "https://"
    else:
        BASE_URL = "http://"
    BASE_URL += domain
    if not domain.endswith("/"):
        BASE_URL += "/"
    log.info("Using BASE_URL: {}".format(BASE_URL))


def get_server(
    host: str,
    port: int,
    domain: str,
    content_dir: str,
    log_level: str,
    default_mime: str,
    ignore_namespaces: List[str],
    index_dir: str,
    ssl_keyfile=None,
    ssl_certfile=None,
    ssl_ca_certs=None,
):
    global CONTENT_DIR
    CONTENT_DIR = content_dir
    if not CONTENT_DIR.endswith("/"):
        CONTENT_DIR += "/"
    global MIME_DEFAULT
    MIME_DEFAULT = default_mime
    global IGNORE_NAMESPACES
    IGNORE_NAMESPACES = ignore_namespaces
    global INDEX_DIR
    INDEX_DIR = index_dir
    build_base_url(
        domain,
        (
            ssl_keyfile is not None
            or ssl_certfile is not None
            or ssl_ca_certs is not None
        ),
    )
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        workers=5,
        log_level=log_level,
        ssl_keyfile=ssl_keyfile,
        ssl_certfile=ssl_certfile,
        ssl_ca_certs=ssl_ca_certs,
    )
    server = uvicorn.Server(config)
    return server


def activate_routes(features: str):
    """
    Disable the routes according to the features spec ('serve' to onlky serve schemas, 'validate' to only validate
    schemas, 'all' to both serve and validate).
    """
    global ROUTES
    if ROUTES is None:
        ROUTES = copy.copy(app.routes)  # save original list of routes
    for r in ROUTES:  # restore original list of routes
        if r not in app.routes:
            app.routes.append(r)
    for r in app.routes:
        if (features == "validate" and r.name == "get_schema") or (
            features == "serve" and r.name == "validate"
        ):
            app.routes.remove(r)


async def start_server(
    host: str,
    port: int,
    domain: str,
    content_dir: str,
    log_level: str,
    default_mime: str,
    features: str,
    ignore_namespaces: List[str],
    index_dir: str,
    ssl_keyfile=None,
    ssl_certfile=None,
    ssl_ca_certs=None,
):
    activate_routes(features)
    await get_server(
        host,
        port,
        domain,
        content_dir,
        log_level,
        default_mime,
        ignore_namespaces,
        index_dir,
        ssl_keyfile,
        ssl_certfile,
        ssl_ca_certs,
    ).serve()


def main(argv=None):
    args = get_args(argv)
    asyncio.run(
        start_server(
            args.host,
            args.port,
            args.domain,
            args.content_dir,
            args.log_level,
            args.default_mime,
            args.features,
            args.ignore_namespaces,
            args.index_dir,
            args.ssl_keyfile,
            args.ssl_certfile,
            args.ssl_ca_certs,
        )
    )


if __name__ == "__main__":
    main()
