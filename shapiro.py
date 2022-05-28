from fastapi import FastAPI, Response, Request, status
import logging
from pyld import jsonld
from schema_store import DefaultSchemaStore
import json

# TODO: package so can be installed with automatic dependency resolution

log = logging.getLogger("uvicorn")

app = FastAPI()

SCHEMA_STORE = DefaultSchemaStore()

@app.on_event("startup")
def init():
    log.info("Welcome to Shapiro. Serving {} schemas.".format(SCHEMA_STORE.schema_count()))

@app.post("/validate", status_code=200)
async def validate(request:Request, response:Response):
    log.info("Validating JSON-LD")
    payload =  await request.body()
    #TODO: implement validation
    log.error("Validation not implemented")
    raise Exception("Validation not implemented yet")

@app.get("/schemas", status_code=200)
def get_schema_list():
    log.info('Listing schemas')
    return SCHEMA_STORE.schema_names()

@app.get("/{schema_name}", status_code=200)
def get_schema(schema_name:str, response:Response):
    log.info("Retrieving schema '{}'".format(schema_name))
    result = SCHEMA_STORE.find_schema(schema_name)
    if result is None:
        response.status_code=status.HTTP_404_NOT_FOUND
        err_msg = "Schema '{}' not found".format(schema_name)
        log.error(err_msg)
        return err_msg
    return result

@app.get("/{schema_name}/context", status_code=200)
def get_schema(schema_name:str, response:Response):
    log.info("Retrieving context for schema '{}'".format(schema_name))
    result = SCHEMA_STORE.context(schema_name)
    if result is None:
        response.status_code=status.HTTP_404_NOT_FOUND
        err_msg = "Schema '{}' not found".format(schema_name)
        log.error(err_msg)
        return err_msg
    return result

@app.get("/{schema_name}/elements/{type}", status_code=200)
def get_classes(schema_name:str, type:str, response:Response):
    log.info("Retrieving elements for schema '{}' with type '{}'".format(schema_name, type))
    result = SCHEMA_STORE.elements(schema_name, type)
    if result is None:
        response.status_code=status.HTTP_404_NOT_FOUND
        err_msg = "Schema '{}' not found".format(schema_name)
        log.error(err_msg)
        return err_msg
    return result

@app.get("/{schema_name}/elements", status_code=200)
def get_classes(schema_name:str, response:Response):
    log.info("Retrieving elements for schema '{}'".format(schema_name))
    result = SCHEMA_STORE.elements(schema_name, None)
    if result is None:
        response.status_code=status.HTTP_404_NOT_FOUND
        err_msg = "Schema '{}' not found".format(schema_name)
        log.error(err_msg)
        return err_msg
    return result

@app.put("/{schema_name}", status_code=200)
async def put_schema(schema_name:str, request:Request, response:Response):
    log.info("Adding/updating schema '{}'".format(schema_name))
    payload =  await request.body()
    SCHEMA_STORE.add_schema(schema_name, json.loads(payload))
    log.info("Now serving {} schemas.".format(SCHEMA_STORE.schema_count()))

@app.get("/{schema_name}/{id}", status_code=200)
def get_schema_element(schema_name:str, id:str, response:Response):
    log.info("Retrieving element '{}' from schema '{}'".format(id, schema_name))
    result = SCHEMA_STORE.find_element(schema_name, id)
    if result is None:
        response.status_code=status.HTTP_404_NOT_FOUND
        err_msg = "Element '{}' not found in schema '{}'".format(id, schema_name)
        return
    return result
