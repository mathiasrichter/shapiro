from modeller import Model, Entity, EntityRef, Property, PropertyRef, PropertyType, ModelNode
import json
import validators

class Generator:
    """
    Takes a model and generates JSON-LD for that model.
    """

    def __init__(self, model: Model, model_alias:str, schema_url:str):
        self.model = model
        if not validators.url(schema_url):
            raise Exception("not a valid url: "+url)
        self.schema_url = schema_url
        self.alias = model_alias

    def generate(self) -> str:
        """
        Generate the JSON-LD for this model and return it as a string.
        """
        result = {}
        result['@context'] = self.__context()
        result['@graph'] = self.__graph()
        return json.dumps(result, indent=2)

    def __get_iri(self, node:ModelNode) -> str:
        if isinstance(node, PropertyRef):
            return node.alias + ":" + node.name
        if isinstance(node, Property):
            return self.alias + ":" + node.name
        if isinstance(node, EntityRef):
            return node.alias + ":" + node.name
        if isinstance(node, Entity):
            return self.alias + ":" + node.name
        raise Exception("Don't know how to build an iri for a node of type {}".format(type(node)))

    def __get_type(self, type: PropertyType) -> str:
        if type == PropertyType.STRING:
            return "xsd:string"
        if type == PropertyType.INT:
            return "xsd:integer"
        if type == PropertyType.FLOAT:
            return "xsd:decimal"
        if type == PropertyType.DATE:
            return "xsd:date"
        if type == PropertyType.TIME:
            return "xsd:time"
        if type == PropertyType.DATETIME:
            return "xsd:dateTime"
        if type == PropertyType.BOOL:
            return "xsd:boolean"
        raise Exception("Don't know xsd type for property type {}".format(type))

    def __context(self) -> dict:
        """
        Generate the dict representing the @context entry in JSON-LD for this generator's model.
        """
        result = {
                    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                    "schema": "http://schema.org/",
                    "shacl": "http://www.w3.org/ns/shacl#",
                    "xsd": "http://www.w3.org/2001/XMLSchema#"
        }
        result[self.alias] = self.schema_url
        for e in self.model.get_entity_refs():
            result[e.alias] = e.url
        for p in self.model.get_property_refs():
            result[p.alias] = p.url
        return result

    def __graph(self) -> dict:
        """
        Generate the dict representing the @graph entry in JSON-LD for this generator's model.
        """
        nodes = self.__properties()
        nodes = nodes + self.__entities()
        # Property constraints
        # Entities & inheritance
        # Relationships
        return nodes

    def __properties(self) -> list[dict]:
        """
        Generate the dict representing the property nodes into the JSON-LD graph.
        """
        result = []
        properties = self.model.get_properties() + self.model.get_property_refs()
        for p in properties:
            node = {}
            node['@id'] = self.__get_iri(p)
            node['@type'] = "rdf:Property"
            node['rdfs:comment'] = p.description
            node['schema:rangeIncludes'] = {"@id": self.__get_type(p.type)}
            entities = list(map(lambda x: {"@id": self.__get_iri(x)}, self.model.get_entities_having(p)))
            if len(entities) > 0:
                node['schema:domainIncludes'] = entities
            result.append(entities)
        return result

    def __entities(self) -> list[dict]:
        """
        Generate the dict representing the entity nodes into the JSON-LD graph.
        """
        result = []
        entities = self.model.get_entities() + self.model.get_entity_refs()
        for e in entities:
            node = {}
            node['@id'] = self.__get_iri(e)
            node['@type'] = "rdf:Class"
            node['rdfs:comment'] = e.description
            subclasses = list(map(lambda x: {"@id": self.__get_iri(x)}, self.model.get_superclasses(e)))
            if len(subclasses) > 0:
                node['rdfs:subClassOf'] = subclasses
            result.append(node)
        return result
