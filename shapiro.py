from fastapi import FastAPI, Response, status
import logging
import json
import os

# TODO: properly wrap this up in a set of classes
# TODO: package so can be installed with automatic dependency resolution

log = logging.getLogger("uvicorn")

app = FastAPI()

CONFIG = {
    'SCHEMA_SUFFIX': '.jsonld',
    'SCHEMA_PATH': '.',
    'SCHEMA_STORE': {}
}

@app.on_event("startup")
def init():
    load_schemas(get_schema_path())
    log.info("Welcome to Shapiro. Serving {} schemas.".format(len(list(get_schema_store()))))

def get_schema_store():
    return CONFIG['SCHEMA_STORE']

def get_schema_suffix():
    return CONFIG['SCHEMA_SUFFIX']

def get_schema_path():
    return CONFIG['SCHEMA_PATH']

#TODO: wrap this into "schema loader interface" with implementations pulling schemas from graph DB, file system, ...
def load_schemas(directory):
    log.info("Loading schemas.")
    for filename in os.listdir(directory):
        if filename.endswith(get_schema_suffix()):
            file = open(filename, 'r')
            schema_name = filename[0:len(filename)-len(get_schema_suffix())]
            log.info("Loading schema '{}' from '{}'".format(schema_name, filename))
            get_schema_store()[schema_name] = json.load(file)
            file.close()

def find_schema(schema_name):
    result = None
    if schema_name in get_schema_store():
        result = get_schema_store()[schema_name]
    return result

def find_element(schema_name, id):
    element_name = schema_name + ":" + id
    schema = find_schema(schema_name)
    if schema is not None:
        #TODO: assumes flattened schema, implement conversion
        for e in schema["@graph"]:
            if e["@id"] == element_name:
                return e
    return None

@app.get("/schemas", status_code=200)
def get_schema_list():
    log.info('Listing schemas')
    return list(get_schema_store())

@app.get("/{schema_name}", status_code=200)
def get_schema(schema_name:str, response:Response):
    log.info("Retrieving schema '{}'".format(schema_name))
    result = find_schema(schema_name)
    if result is None:
        response.status_code=status.HTTP_404_NOT_FOUND
        err_msg = "Schema '{}' not found".format(schema_name)
        log.error(err_msg)
        return err_msg
    return result

@app.get("/{schema_name}/{id}", status_code=200)
def get_schema_element(schema_name:str, id:str, response:Response):
    log.info("Retrieving element '{}' from schema '{}'".format(id, schema_name))
    result = find_element(schema_name, id)
    if result is None:
        response.status_code=status.HTTP_404_NOT_FOUND
        err_msg = "Element '{}' not found in schema '{}'".format(id, schema_name)
        return
    return result
