from fastapi import FastAPI, Response, status
import logging
import json
import os

log = logging.getLogger("uvicorn")

app = FastAPI()

CONFIG = {
    'SCHEMA_SUFFIX': '.jsonld',
    'SCHEMA_PATH': '.',
    'SCHEMA_STORE': {}
}

def get_schema_store():
    return CONFIG['SCHEMA_STORE']

def get_schema_suffix():
    return CONFIG['SCHEMA_SUFFIX']

def get_schema_path():
    return CONFIG['SCHEMA_PATH']

def init():
    load_schemas(get_schema_path())

def load_schemas(directory):
    for filename in os.listdir(directory):
        if filename.endswith(get_schema_suffix()):
            file = open(filename, 'r')
            schema_name = filename[0:len(filename)-len(get_schema_suffix())]
            log.info("Loading schema '" + schema_name + "' from '" + filename + "'")
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
    log.info("Retrieving schema '" + schema_name + "'")
    result = find_schema(schema_name)
    if result is None:
        response.status_code=status.HTTP_404_NOT_FOUND
        err_msg = "Schema '" + schema_name + "' not found"
        log.error(err_msg)
        return err_msg
    return result

@app.get("/{schema_name}/{id}", status_code=200)
def get_schema_element(schema_name:str, id:str, response:Response):
    log.info("Retrieving element '" + id + "' from schema '" + schema_name + "'")
    result = find_element(schema_name, id)
    if result is None:
        response.status_code=status.HTTP_404_NOT_FOUND
        err_msg = "Element '" + id + "' not found in schema '" + schema_name +"'"
        return
    return result

init()
