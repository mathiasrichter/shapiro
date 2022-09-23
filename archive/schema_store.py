import logging
import json
from json import JSONDecodeError
import os
from abc import ABC, abstractmethod

log = logging.getLogger("uvicorn")

class AbstractSchemaStore(ABC):
    """
    Abstract super class for a JSON-LD schema store
    Provides methods for retrieving schemas and schema elements
    """

    @abstractmethod
    def schema_count(self):
        """
        Return the number of schemas in this store
        """
        pass

    @abstractmethod
    def schema_names(self):
        """
        Return the names of all schemas in this store
        """
        pass

    @abstractmethod
    def add_schema(self, schema_name, jsonld):
        """
        Add the specified JSON-LD schema to the store. This overwrites
        existing schemas stored under the same name.
        """
        pass

    @abstractmethod
    def find_schema(self, schema_name):
        """
        Find the schema with the specified name.
        Returns JSON-LD for the schema or None if a schema with
        the specified name does not exist.
        """
        pass

    @abstractmethod
    def find_element(self, schema_name, id):
        """
        Find the element with the specified id in the schema with
        the specified name. Returns JSON-LD for the element or
        none if either schema or element does not exist.
        """
        pass

    @abstractmethod
    def elements(self, schema_name, type):
        """
        Return all classes in the specified schema with the specified type.
        If no type is specified (None or '') then all elements are returned.
        """
        pass

    @abstractmethod
    def context(self, schema_name):
        """
        Return the context of the schema with the specified name.
        """
        pass

    @abstractmethod
    def save(self, schema_name):
        """
        Save the specified schema to persistent store.
        """
        pass

class DefaultSchemaStore(AbstractSchemaStore):
    """
    Naive default implementation of schema store.
    Loads schemas into memory from a directory.
    """

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
                try:
                    self.add_schema(schema_name, json.load(file))
                except JSONDecodeError as x:
                    log.error("Could not load schema '{}' from '{}': {}".format(schema_name, filename, x))
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

    def elements(self, schema_name, type):
        schema = self.find_schema(schema_name)
        if schema is not None:
            result = []
            for e in schema["@graph"]:
                if e["@type"] == type or type == '' or type is None:
                    result.append(e)
            return result
        return None

    def context(self, schema_name):
        schema = self.find_schema(schema_name)
        if schema is not None:
            return schema['@context']
        return None

    def save(self, schema_name):
        schema = self.find_schema(schema_name)
        if schema is not None:
            with open(self.schema_path + schema_name + self.schema_suffix, 'w') as f:
                json.dump(schema, f)
