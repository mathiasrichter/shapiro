import logging
import json
import os
from abc import ABC, abstractmethod

log = logging.getLogger("uvicorn")

# Abstract super class for a JSON-LD schema store
# Provides methods for retrieving schemas and schema elements
class AbstractSchemaStore(ABC):

    # Return the number of schemas in this store
    @abstractmethod
    def schema_count(self):
        pass

    # Return the names of all schemas in this store
    @abstractmethod
    def schema_names(self):
        pass

    # Add the specified JSON-LD schema to the store. This overrides
    # existing schemas stored under the same name.
    @abstractmethod
    def add_schema(self, schema_name, jsonld):
        pass

    # Find the schema with the specified name.
    # Returns JSON-LD for the schema or None if a schema with
    # the specified name does not exist.
    @abstractmethod
    def find_schema(self, schema_name):
        pass

    # Find the element with the specified id in the schema with
    # the specified name. Returns JSON-LD for the element or
    # none if either schema or element does not exist.
    @abstractmethod
    def find_element(self, schema_name, id):
        pass

    # Return all classes in the specified schema.
    @abstractmethod
    def classes(self, schema_name):
        pass

# Default implementatipon of schema store.
# Loads schemas into memory from a directory.
# This is a naive implementation of a schema store.
class DefaultSchemaStore(AbstractSchemaStore):

    def __init__(self, schema_suffix = '.jsonld', schema_path = '.'):
        self.schema_suffix = schema_suffix
        self.schema_path = schema_path
        self.schema_store = {}
        self.load_schemas()

    def load_schemas(self):
        log.info("Loading schemas from directory {}.".format(self.schema_path))
        for filename in os.listdir(self.schema_path):
            if filename.endswith(self.schema_suffix):
                file = open(filename, 'r')
                schema_name = filename[0:len(filename)-len(self.schema_suffix)]
                log.info("Loading schema '{}' from '{}'".format(schema_name, filename))
                self.add_schema(schema_name, json.load(file))
                file.close()

    def add_schema(self, schema_name, jsonld):
        # TODO: validate schema?
        self.schema_store[schema_name] = jsonld

    def schema_count(self):
        return len(list(self.schema_store))

    def schema_names(self):
        return(list(self.schema_store))

    def find_schema(self, schema_name):
        result = None
        if schema_name in self.schema_store:
            result = self.schema_store[schema_name]
        return result

    def find_element(self, schema_name, id):
        element_name = schema_name + ":" + id
        schema = self.find_schema(schema_name)
        if schema is not None:
            #TODO: assumes flattened schema, implement conversion
            for e in schema["@graph"]:
                if e["@id"] == element_name:
                    return e
        return None

    def classes(self, schema_name):
        #TODO: implement properly.
        return None
