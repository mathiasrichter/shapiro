from fastapi import FastAPI, Response, Request, status, Header
import logging
import os
from rdflib import Graph

log = logging.getLogger("uvicorn")

app = FastAPI()

MIME_HTML = "text/html"
MIME_JSONLD = "application/ld+json"
MIME_TTL = "text/turtle"
MIME_JSONSCHEMA = "application/json"
MIME_DEFAULT = MIME_TTL

SUFFIX_JSONLD = 'jsonld'
SUFFIX_TTL = 'ttl'
SUPPORTED_SUFFIXES = [ SUFFIX_JSONLD, SUFFIX_TTL ]

PATH_SEP = '/'

SUPPORTED_MIME_TYPES = [MIME_HTML, MIME_JSONLD, MIME_TTL, MIME_JSONSCHEMA]

CONTENT_DIR_ENV_VAR = 'SHAPIRO_CONTENT_DIR'

if CONTENT_DIR_ENV_VAR not in os.environ.keys() or os.environ[CONTENT_DIR_ENV_VAR] == '':
    log.warn("No environment variable '{}' set - using current dir as default content directory.".format(CONTENT_DIR_ENV_VAR))
    CONTENT_DIR = './'
else:
    CONTENT_DIR = os.environ[CONTENT_DIR_ENV_VAR]

if not CONTENT_DIR.endswith('/'):
    CONTENT_DIR += '/'

log.info("Using '{}' as content dir.".format(CONTENT_DIR))

@app.on_event("startup")
def init():
    log.info("Welcome to Shapiro.")

@app.get("/{_:path}",  status_code=200)
def get_schema(request:Request, response:Response, accept_header=Header(None)):
    path = request.url.path[1:]
    if accept_header is None:
        accept_header=''
    log.info("Retrieving schema '{}' with accept-headers '{}'".format(path, accept_header))
    result = resolve(accept_header, path)
    if result is None:
        response.status_code=status.HTTP_404_NOT_FOUND
        err_msg = "Schema '{}' not found".format(path)
        log.error(err_msg)
        return err_msg
    return result

def resolve(accept_header:str, path:str):
    mime_type = negotiate(accept_header)
    filename = map_filename(path)
    if filename is None:
        return None
    f = open(filename, 'r')
    content = f.read()
    f.close()
    return convert(filename, content, mime_type)

def convert(filename:str, content:str, mime_type:str):
    if mime_type == MIME_JSONLD:
        if filename.endswith(SUFFIX_JSONLD):
            return content
        if filename.endswith(SUFFIX_TURTLE):
            g = Graph()
            g.parse(filename)
            return g.serialize(format='ttl')
    if mime_type == MIME_TTL:
        if filename.endswith(SUFFIX_JSONLD):
            g = Graph()
            g.parse(filename)
            return g.serialize(format='json-ld')
        if filename.endswith(SUFFIX_TURTLE):
            return content
    log.warn("No conversion possible for content path '{}' and mime type '{}'".format(filename, mime_type))

def map_filename(path:str):
    """
    Take the hierarchical path specified and identify the file with the ontology content that this
    path maps to.
    """
    # is last element of the path the name of a file with one of the supported suffixes?
    full_path = CONTENT_DIR + path
    for s in SUPPORTED_SUFFIXES:
        current = full_path + s
        if os.path.isfile(current):
            return current
    # it is not, so assume that last element of the path is an element in the file
    full_path =  full_path[0:full_path.rfind(PATH_SEP)]
    for s in SUPPORTED_SUFFIXES:
        current = full_path + s
        if os.path.isfile(current):
            return current
    log.error("Could not map '{}' to a schema file with one of the supported suffixes {}.".format(path, SUPPORTED_SUFFIXES))
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
        log.warn("No supported mime type found in accept header - resorting to default ({})".format(MIME_DEFAULT))
        preferred = MIME_DEFAULT
    return preferred
