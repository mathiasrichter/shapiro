from modeller import Model, Entity, EntityRef, Property, PropertyRef, PropertyType, ModelNode, RelatedTo, ValidationConstraint, ValueMandatoryConstraint, StringLengthConstraint, StringPatternConstraint, RangeConstraint, Cardinality
import json
import validators
from datetime import date, time

def datetime_converter(o):
    """
    Help the JSON module serialize date/time/datetime values.
    """
    if isinstance(o, date): # also covers datetime
        return o.__str__()
    if isinstance(o, time):
        return o.__str__()

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
        return json.dumps(result, indent=2, default=datetime_converter)

    def __get_iri(self, node:ModelNode) -> str:
        if isinstance(node, RelatedTo):
            return self.alias + ":" + node.name
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
        nodes += self.__entities()
        nodes += self.__relationships()
        nodes += self.__constraints()
        return nodes

    def __properties(self) -> list[dict]:
        """
        Generate the dict representing the property nodes into the JSON-LD graph.
        """
        result = []
        iris = []
        properties = self.model.get_properties() + self.model.get_property_refs()
        for p in properties:
            iri = self.__get_iri(p)
            if iri not in iris:
                node = {}
                node['@id'] = iri
                node['@type'] = "rdf:Property"
                node['rdfs:comment'] = p.description
                node['schema:rangeIncludes'] = {"@id": self.__get_type(p.type)}
                entities = list(map(lambda x: {"@id": self.__get_iri(x)}, self.model.get_entities_having(p)))
                if len(entities) > 0:
                    node['schema:domainIncludes'] = entities
                iris.append(iri)
                result.append(node)
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
            node['@type'] = 'rdf:Class'
            node['rdfs:comment'] = e.description
            subclasses = list(map(lambda x: {'@id': self.__get_iri(x)}, self.model.get_superclasses(e)))
            if len(subclasses) > 0:
                node['rdfs:subClassOf'] = subclasses
            result.append(node)
        return result

    def __relationships(self) -> list[dict]:
        """
        Generate the dict representing the relationships into the JSON-LD graph.
        """
        result = []
        iris = []
        for r in self.model.get_relationships():
            iri = self.__get_iri(r)
            if iri not in iris:
                node = {}
                node['@id'] = iri
                node['@type'] = 'rdf:Property'
                node['rdfs:comment'] = r.description
                node['schema:rangeIncludes'] = {"@id": self.__get_iri(r.target)}
                node['schema:domainIncludes'] = list(map(lambda x: {'@id': self.__get_iri(x.source)}, self.model.get_relationships_to(r.target)))
                iris.append(iri)
                result.append(node)
        return result

    def __constraints(self) -> list[dict]:
        """
        Generate constrainst for entities and their properties/relationships.
        """
        result = []
        iris = []
        entities = self.model.get_entities() + self.model.get_entity_refs()
        for e in entities:
            iri = self.__get_iri(e)
            if iri not in iris:
                node = {}
                node['@id'] = iri + 'Validation'
                node['@type'] = 'sh:NodeShape'
                node['sh:targetClass'] = { '@id': iri }
                constraints = self.__property_constraints(e)
                constraints += self.__relationship_constraints(e)
                node['sh:property'] = constraints
                # model constraints? (every entity/property must have a description, etc.)
                iris.append(iri)
                if len(constraints) > 0:
                    result.append(node)
        return result

    def __property_constraints(self, entity) -> list[dict]:
        """
        Generate constraints for the properties of the specified entity.
        """
        result = []
        for p in self.model.get_properties_of(entity):
            iri = self.__get_iri(p)
            t_node = {}
            t_node['sh:path'] = { '@id': iri }
            t_node['sh:type'] = self.__get_type(p.type)
            result.append(t_node)
            for c in self.model.get_constraints(p):
                node = {}
                node['sh:path'] = { '@id': iri }
                self.__set_constraint_details(c, node)
                result.append(node)
        return result

    def __relationship_constraints(self, entity:Entity) -> list[dict]:
        """
        Generate constraints for the relationships of the specified entity.
        """
        result = []
        for r in self.model.get_relationships_from(entity):
            iri = self.__get_iri(r)
            node = {}
            node['sh:path'] = { '@id': iri }
            node['sh:type'] = self.__get_iri(r.target)
            if r.cardinality == Cardinality.ONE:
                node['sh:minCount'] = 1
                node['sh:maxCount'] = 1
                node['sh:message'] = "A {} must be associated with one {}.".format(r.source.name, r.target.name)
            elif r.cardinality == Cardinality.ZERO_TO_ONE:
                node['sh:minCount'] = 0
                node['sh:maxCount'] = 1
                node['sh:message'] = "A {} must be associated with zero or one {}.".format(r.source.name, r.target.name)
            elif r.cardinality == Cardinality.ONE_TO_MANY:
                node['sh:minCount'] = 1
                node['sh:message'] = "A {} must be associated with one or more {}.".format(r.source.name, r.target.name)
            elif r.cardinality == Cardinality.ZERO_TO_MANY:
                node['sh:minCount'] = 0
                node['sh:message'] = "A {} must be associated with zero or more {}.".format(r.source.name, r.target.name)
            result.append(node)
        return result

    def __set_constraint_details(self, constraint: ValidationConstraint, data:dict):
        if isinstance(constraint, ValueMandatoryConstraint):
            data['sh:minCount'] = 1
            data['sh:maxCount'] = 1
        if isinstance(constraint, StringLengthConstraint):
            if constraint.min_length is not None:
                data['sh:minLength'] = constraint.min_length
            if constraint.max_length is not None:
                data['sh:maxLength'] = constraint.max_length
        if isinstance(constraint, StringPatternConstraint):
            data['sh:pattern'] = constraint.regex
        if isinstance(constraint, RangeConstraint):
            if constraint.min is not None:
                data['sh:minInclusive'] = constraint.min
            if constraint.max is not None:
                data['sh:maxInclusive'] = constraint.max
        data['sh:message'] = constraint.description
