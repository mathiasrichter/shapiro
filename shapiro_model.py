from rdflib import Graph, URIRef, BNode
from rdflib.plugins.sparql import prepareQuery
from rdflib.plugin import PluginException
from typing import Tuple, List
from shapiro_util import prune_iri, get_logger
from urllib.parse import urlparse
import logging

log = get_logger("SHAPIRO_MODEL")

TYPE_MAP = {
    # maps (unprefixed) XSD datatypes to JSON-Schema types
    "string": "string",
    "boolean": "boolean",
    "decimal": "number",
    "integer": "integer",
    "float": "number",
    "date": "string",  # with "format": "date"
    "time": "string",  # with "format": "time"
    "dateTime": "string",  # with "format": "date-time"
    "dateTimeStamp": "string",  # with "format": "date-time"
    "gMonth": "string",
    "gDay": "string",
    "gYearMonth": "string",
    "gMonthDay": "string",
    "duration": "string",
    "yearMonthDuration": "string",
    "dayTimeDuration": "string",
    "short": "integer",
    "int": "integer",
    "long": "integer",
    "unsignedByte": "integer",
    "unsignedShort": "integer",
    "unsignedInt": "integer",
    "unsignedLong": "integer",
    "positiveInteger": "integer",
    "nonNegativeInteger": "integer",
    "negativeInteger": "integer",
    "nonPositiveInteger": "integer",
    "hexBinary": "string",
    "base64Binary": "string",
    "language": "string",
    "normalizedString": "string",
    "token": "string",
    "NMTOKEN": "string",
    "Name": "string",
    "NCName": "string",
}

UNQUOTED_TYPES = ["boolean", "number", "integer"]

CONSTRAINT_MAP = {
    # maps (unprefixed) SHACL constraints to JSON-Schema constraints
    "minCount": "minItems",  # for arrays only, "required" handled differently
    "maxCount": "maxItems",  # ditto
    "in": "enum",
    "minInclusive": "minimum",
    "maxInclusive": "maximum",
    "minExclusive": "exclusiveMinimum",
    "maxExclusive": "exclusiveMaximum",
    "minLength": "minLength",
    "maxLength": "maxLength",
    "pattern": "pattern",
}

NUMERIC_CONSTRAINTS = [
    # JSON-SCHEMA constraints that take numeric values
    "minItems",
    "maxItems",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
]

ARRAY_ITEM_CONSTRAINTS = [
    # JSON-SCHEMA constraints that apply to items of an array
    "enum",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "pattern",
]

class Subscriptable:
    def __getitem__(self, key):
        if key not in self.__dict__.keys():
            if key in dir(self):
                return getattr(self, key)()
            else:
                raise Exception(
                    "Class '{}' does not have property '{}'.".format(type(self), key)
                )
        return self.__dict__[key]


class SemanticModelElement(Subscriptable):
    RDFS_CLASS = "http://www.w3.org/2000/01/rdf-schema#Class"
    OWL_CLASS = "http://www.w3.org/2002/07/owl#Class"
    RDF_PROPERTY = "http://www.w3.org/1999/02/22-rdf-syntax-ns#Property"
    RDFS_PROPERTY = "http://www.w3.org/2000/01/rdf-schema#Property"
    SHACL_NODESHAPE = "http://www.w3.org/ns/shacl#NodeShape"
    SHACL_PROPERTY = "http://www.w3.org/ns/shacl#Property"

    TYPE_QUERY = prepareQuery(
        """
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            SELECT DISTINCT ?instance ?type
            WHERE
            {
                ?instance rdf:type ?type .
            }
            """
    )

    DESCRIPTION_QUERY = prepareQuery(
        """
                PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
                PREFIX skos:<http://www.w3.org/2004/02/skos/core#>
                PREFIX dct: <http://purl.org/dc/terms/>
                PREFIX owl: <http://www.w3.org/2002/07/owl#>
                SELECT DISTINCT ?label ?title ?comment ?definition ?description
                WHERE
                {
                    OPTIONAL { ?model rdfs:label ?label . } 
                    OPTIONAL { ?model dct:title ?title . } 
                    OPTIONAL { ?model rdfs:comment ?comment . } 
                    OPTIONAL { ?model dct:description ?description . } 
                    OPTIONAL { ?model skos:definition ?definition . } 
                }
                """
    )

    PREDICATES_QUERY = prepareQuery(
        """
                SELECT DISTINCT ?predicate ?object
                WHERE
                {
                    { ?subject ?predicate ?object }
                }
                """
    )

    def __init__(self, iri: str, graph: Graph = None):
        log.info("Initializing model for {}".format(iri))
        self.iri = str(iri)  # ensure this is a string, may sometimes be a URIRef object
        self.graph = graph
        self.label, self.title, self.comment, self.description, self.definition = (
            "",
            "",
            "",
            "",
            "",
        )
        if urlparse(iri).scheme != "":  #  if this is not a blank node
            if graph is None:
                self.graph = Graph().parse(iri)
            (
                self.label,
                self.title,
                self.comment,
                self.description,
                self.definition,
            ) = self.get_label_and_descriptions()
            if self.label == "" and self.title == "":
                log.warn(
                    "Empty title, label, description and comment from graph query. Setting label/title to default for {}".format(
                        self.iri
                    )
                )
                self.label = self.title = prune_iri(self.iri, True)
        else:
            log.warn(
                "Cannot create graph - setting to 'unnamed' 'n/a' for {}".format(
                    self.iri
                )
            )
            self.label = self.title = "unnamed"
            self.comment = self.description = self.definition = "n/a"

    def get_label_and_descriptions(self) -> Tuple[str, str, str, str, str]:
        result = self.graph.query(
            self.DESCRIPTION_QUERY, initBindings={"model": URIRef(self.iri)}
        )
        label = ""
        title = ""
        comment = "n/a"
        description = "n/a"
        definition = "n/a"
        if result.__len__() == 1:
            for r in result:
                if r.label is not None:
                    label = str(r.label)
                if r.title is not None:
                    title = str(r.title)
                if r.comment is not None:
                    comment = str(r.comment)
                if r.description is not None:
                    description = str(r.description)
                if r.definition is not None:
                    definition = str(r.definition)
        return (label, title, comment, description, definition)

    def get_types(self) -> str:
        ref = URIRef(self.iri)
        result = self.graph.query(self.TYPE_QUERY, initBindings={"instance": ref})
        types = []
        for r in result:
            types.append(str(r.type))
        types.sort(key=lambda c: c)
        return types

    def get_predicates(self) -> dict:
        result = self.graph.query(
            self.PREDICATES_QUERY, initBindings={"subject": URIRef(self.iri)}
        )
        predicates = []
        for r in result:
            predicates.append(Predicate(str(r.predicate), self.graph, PredicateValue(str(r.object), self.graph)))
        return predicates
    

class PredicateValue(SemanticModelElement):
    
    def __init__(self, iri, graph: Graph):
        url = urlparse(iri)
        if url.scheme != "" and url.scheme is not None:
            super().__init__(iri, graph)
        else:
            self.label = iri
            self.iri = ""

class Predicate(SemanticModelElement):
    
    def __init__(self, iri: str, graph: Graph, value:PredicateValue):
        super().__init__(iri, graph)
        self.value_label = value.label
        self.value_iri = value.iri

class RdfProperty(SemanticModelElement):
    CLASSES_QUERY = prepareQuery(
        """
        PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT DISTINCT ?result
        WHERE
        {
            {
                ?property rdf:type rdfs:Property .
                OPTIONAL { ?property rdfs:domain ?result . }
            }
            UNION
            {
                ?property rdf:type rdf:Property .
                OPTIONAL { ?property rdfs:domain ?result . }
            }
        }
        """
    )

    SUPERPROPS_QUERY = prepareQuery(
        """
        PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT DISTINCT ?result
        WHERE
        {
            {
                ?property rdf:type rdfs:Property .
                OPTIONAL { ?property rdfs:subPropertyOf ?result . }
            }
            UNION
            {
                ?property rdf:type rdf:Property .
                OPTIONAL { ?property rdfs:subPropertyOf ?result . }
            }
        }
        """
    )

    RANGE_QUERY = prepareQuery(
        """
        PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT DISTINCT ?result
        WHERE
        {
            {
                ?property rdf:type rdfs:Property .
                OPTIONAL { ?property rdfs:range ?result . }
            }
            UNION
            {
                ?property rdf:type rdf:Property .
                OPTIONAL { ?property rdfs:range ?result . }
            }
        }
        """
    )

    KIND_OF_QUERY = prepareQuery(
        """
        PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT DISTINCT ?result
        WHERE
        {
            ?property rdf:type ?result .
        }
        """
    )

    SHACL_PROP_QUERY = prepareQuery(
        """ 
            PREFIX sh:<http://www.w3.org/ns/shacl#>
            SELECT DISTINCT ?shacl_prop
            WHERE
            {
                ?shacl_prop sh:path ?property .
            }
                """
    )

    def __init__(self, iri: str, graph: Graph):
        super().__init__(iri, graph)

    def query(self, query: str) -> List[str]:
        qresult = self.graph.query(query, initBindings={"property": URIRef(self.iri)})
        result = []
        for r in qresult:
            result.append(str(r.result))
        result.sort(key=lambda c: c)
        return result
    
    def get_property_kind(self) -> List[str]:
        return self.query(self.KIND_OF_QUERY)

    def get_property_type(self) -> List[str]:
        return self.query(self.RANGE_QUERY)

    def get_superproperties(self) -> List[str]:
        return self.query(self.SUPERPROPS_QUERY)

    def get_classes(self) -> List[str]:
        return self.query(self.CLASSES_QUERY)

    def get_shacl_properties(self) -> List[str]:
        result = self.graph.query(
            self.SHACL_PROP_QUERY, initBindings={"property": URIRef(self.iri)}
        )
        props = []
        for r in result:
            props.append(ShaclProperty(str(r.shacl_prop), self.graph))
        props.sort(key=lambda p: p.label)
        return props

    def is_xsd_datatype(self) -> bool:
        for t in self.get_property_type():
            if 'xmlschema#' in t[t.rfind('/'):len(t)].lower():
                return True
        return False

class NodeShape(SemanticModelElement):
    SHACL_PROP_QUERY = prepareQuery(
        """ 
            PREFIX sh:<http://www.w3.org/ns/shacl#>
            SELECT DISTINCT ?shacl_prop
            WHERE
            {
                ?shape sh:property ?shacl_prop .
            }
        """
    )

    CLASS_QUERY = prepareQuery(
        """ 
            PREFIX sh:<http://www.w3.org/ns/shacl#>
            SELECT DISTINCT ?target
            WHERE
            {
                ?shape sh:targetClass ?target .
            }
        """
    )

    def __init__(self, iri: str, graph: Graph):
        super().__init__(iri, graph)

    def get_inherited_shacl_properties(self):
        # need to get the full set of (transitive) superclasses,
        # find a NodeShape for the class and get the properties from
        # that shape. need to be lenient, ie. if there's no nodeshape,
        # the set is empty, it's not a failure.
        clazzes = set()
        properties = []
        for c in self.get_classes():
            clazzes = clazzes | set(c.get_superclasses(True))
        for c in clazzes:
            shapes = c.get_nodeshapes()
            for s in shapes:
                properties = properties + s.get_shacl_properties()
        return properties

    def get_shacl_properties(self) -> List["ShaclProperty"]:
        result = self.graph.query(
            self.SHACL_PROP_QUERY, initBindings={"shape": URIRef(self.iri)}
        )
        props = []
        for r in result:
            props.append(ShaclProperty(str(r.shacl_prop), self.graph))
        props.sort(key=lambda p: p.label)
        return props

    def get_classes(self) -> List["RdfClass"]:
        result = self.graph.query(
            self.CLASS_QUERY, initBindings={"shape": URIRef(self.iri)}
        )
        classes = []
        for r in result:
            classes.append(RdfClass(str(r.target), self.graph))
        classes.sort(key=lambda p: p.label)
        return classes

    def get_json_schema_comment(self) -> str:
        no_comment = (
            self.comment is None or self.comment == "" or self.comment.lower() == "n/a"
        )
        if no_comment is False:
            return self.comment
        for c in self.get_classes():
            no_comment = (
                c.comment is None or c.comment == "" or c.comment.lower() == "n/a"
            )
            if no_comment is False:
                return c.comment
        return "n/a"


class RdfClass(SemanticModelElement):
    SUPERCLASSES_QUERY = prepareQuery(
        """
        PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
        SELECT DISTINCT ?superclass
        WHERE
        {
            ?subclass rdfs:subClassOf ?superclass .
        }
        """
    )

    TRANSITIVE_SUPERCLASSES_QUERY = prepareQuery(
        """
        PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
        SELECT DISTINCT ?superclass
        WHERE
        {
            ?subclass rdfs:subClassOf+ ?superclass .
        }
        """
    )

    PROPERTY_QUERY = prepareQuery(
        """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>

        SELECT DISTINCT ?property
        WHERE
        {
            {
                ?property rdf:type rdfs:Property .
                ?property rdfs:domain ?class .
            }
            UNION
            {
                ?property rdf:type rdf:Property .
                ?property rdfs:domain ?class .
            }
        }
        """
    )

    SHAPE_QUERY = prepareQuery(
        """ 
                PREFIX sh:<http://www.w3.org/ns/shacl#>
                SELECT DISTINCT ?shape
                WHERE
                {
                    ?shape sh:targetClass ?class .
                }
                """
    )

    INSTANCE_QUERY = prepareQuery(
        """
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
                SELECT DISTINCT ?instance
                WHERE
                {
                    ?instance rdf:type ?clazz .
                    ?clazz rdf:type rdfs:Class .
                }
                """
    )

    def __init__(self, iri: str, graph: Graph):
        super().__init__(iri, graph)

    def get_properties(self) -> List[RdfProperty]:
        result = self.graph.query(
            self.PROPERTY_QUERY, initBindings={"class": URIRef(self.iri)}
        )
        props = []
        for r in result:
            props.append(RdfProperty(str(r.property), self.graph))
        props.sort(key=lambda c: c.label)
        return props

    def get_superclasses(self, transitive: bool = False) -> list:
        query = self.SUPERCLASSES_QUERY
        if transitive == True:
            query = self.TRANSITIVE_SUPERCLASSES_QUERY
        result = self.graph.query(query, initBindings={"subclass": URIRef(self.iri)})
        superclasses = []
        for r in result:
            superclasses.append(RdfClass(str(r.superclass), self.graph))
        superclasses.sort(key=lambda c: c.label)
        return superclasses

    def get_nodeshapes(self) -> List[NodeShape]:
        result = self.graph.query(
            self.SHAPE_QUERY, initBindings={"class": URIRef(self.iri)}
        )
        shapes = []
        for r in result:
            shapes.append(NodeShape(str(r.shape), self.graph))
        shapes.sort(key=lambda c: c.label)
        return shapes

    def get_instances(self) -> List["Instance"]:
        result = self.graph.query(
            self.INSTANCE_QUERY, initBindings={"clazz": URIRef(self.iri)}
        )
        instances = []
        for r in result:
            instances.append(Instance(r.instance, self.graph))
        instances.sort(key=lambda c: c.label)
        return instances


class ShaclConstraint(Subscriptable):
    def __init__(
        self, parent: "ShaclProperty", constraint_iri: str, value: str, is_enum: bool
    ):
        self.parent = parent
        self.constraint_iri = constraint_iri
        self.value = value
        self.is_enum = is_enum

    def get_json_schema_name(self):
        for k in CONSTRAINT_MAP.keys():
            if self.constraint_iri.endswith(k):
                return CONSTRAINT_MAP[k]
        return None

    def needs_quotes(self) -> bool:
        if self.is_enum:
            return self.parent.get_json_schema_type()[0] not in UNQUOTED_TYPES
        return self.get_json_schema_name() not in NUMERIC_CONSTRAINTS


class ShaclProperty(SemanticModelElement):
    SHAPE_QUERY = prepareQuery(
        """ 
                PREFIX sh:<http://www.w3.org/ns/shacl#>
                SELECT DISTINCT ?shape
                WHERE
                {
                    ?shape sh:property ?property .
                }
                """
    )

    SHACL_CONSTRAINTS_QUERY = prepareQuery(
        """ 
                SELECT DISTINCT ?property ?constraint ?value
                WHERE
                {
                    ?property ?constraint ?value .
                    FILTER(STRSTARTS(STR(?constraint), "http://www.w3.org/ns/shacl#")) .
                }
                """
    )

    SHACL_IN_QUERY = prepareQuery(
        """
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX sh: <http://www.w3.org/ns/shacl#>

                SELECT  ?source ?item
                WHERE {
                ?source sh:in/rdf:rest*/rdf:first ?item
                }
            """
    )

    def __init__(self, iri: str, graph: Graph):
        super().__init__(iri, graph)

    def get_constraints(self) -> List[ShaclConstraint]:
        prop = None
        if urlparse(self.iri).scheme == "":  #  if this is a blank node
            prop = BNode(self.iri)
        else:
            prop = URIRef(self.iri)
        result = self.graph.query(
            self.SHACL_CONSTRAINTS_QUERY, initBindings={"property": prop}
        )
        constraints = []
        for r in result:
            p = str(r.property)
            c = str(r.constraint)
            v = str(r.value)
            is_enum = False
            if c.endswith("shacl#in"):
                is_enum = True
                v = []
                if urlparse(p).scheme == "":  #  if p is a blank node
                    prop = BNode(self.iri)
                else:
                    prop = URIRef(self.iri)
                items = self.graph.query(
                    self.SHACL_IN_QUERY, initBindings={"source": prop}
                )
                for i in items:
                    v.append(i.item)
            constraints.append(ShaclConstraint(self, c, v, is_enum))
        constraints.sort(key=lambda c: c.constraint_iri)
        return constraints

    def is_required(self):
        constraints = self.get_constraints()
        minCount = list(
            filter(lambda c: c.constraint_iri.lower().endswith("mincount"), constraints)
        )
        if len(minCount) == 1:
            return int(minCount[0].value) >= 1
        return False

    def is_array(self):
        constraints = self.get_constraints()
        maxCount = list(
            filter(lambda c: c.constraint_iri.lower().endswith("maxcount"), constraints)
        )
        if len(maxCount) == 1:
            return int(maxCount[0].value) > 1
        return False

    def get_json_schema_type(self) -> Tuple:
        # would assume that property shape points to another nodeshape for object references,
        # if it does not, we should try and find a suitable nodeshape in the model, which is ok
        # if there is only one, but not if there are multiple nodeshapes in the same model
        t = self.xsd_datatype()
        if t is not None:
            for k in TYPE_MAP.keys():
                if t.lower().endswith(
                    k.lower()
                ):  # TODO: endswith is going to collide with names of classes!!
                    # add format for date/time
                    if k == "date":
                        return (TYPE_MAP[k], "date")
                    if k == "time":
                        return (TYPE_MAP[k], "time")
                    if k == "dateTime" or k == "dateTimeStamp":
                        return (TYPE_MAP[k], "date-time")
                    return (TYPE_MAP[k], None)
            # must be an object reference, make sure we point to a NodeShape
            # so JSON-SCHEMA tooling can resolve the $ref to that NodeShape's
            # JSON-SCHEMA through Shapiro
        t = self.class_datatype()
        if t is not None:
            return (self.get_nodeshape_for(t), None)
        return None  # no mapping found, return None meaning no constraint is put in JSON-SCHEMA

    def get_target_property(self) -> RdfProperty:
        target_prop_iri = list(
            filter(lambda c: c.constraint_iri.endswith("path"), self.get_constraints())
        )[
            0
        ].value  # there must be one
        return RdfProperty(target_prop_iri, self.graph)

    def get_iri(self) -> str:
        # if this SHACL property is a blank node, then return the iri of the target property, otherwise return the original iri of this property
        if self.label == "unnamed":
            return self.get_target_property().iri
        return self.iri

    def get_json_schema_name(self) -> str:
        no_label = (
            self.label is None
            or self.label == ""
            or self.label.lower() == "unnamed"
            or self.label.lower() == "n/a"
        )
        if no_label is False:
            return self.label
        return self.get_target_property().label

    def get_json_schema_comment(self) -> str:
        no_comment = (
            self.comment is None or self.comment == "" or self.comment.lower() == "n/a"
        )
        if no_comment is False:
            return self.comment
        return self.get_target_property().comment

    def get_json_schema_array_item_constraints(self) -> List[ShaclConstraint]:
        if self.is_array():
            return list(
                filter(
                    lambda c: c.get_json_schema_name() in ARRAY_ITEM_CONSTRAINTS,
                    self.get_constraints(),
                )
            )
        return []

    def get_nodeshape_for(self, iri: str) -> str:
        s = SemanticModel(iri)
        types = s.get_types()
        nodeshapes = list(filter(lambda t: t.lower().endswith("nodeshape"), types))
        if len(nodeshapes) > 0:
            # iri is a nodeshape
            return iri
        classes = list(filter(lambda t: t.lower().endswith("class"), types))
        if len(classes) > 0:
            # iri is a class, find nodeshape with this class as targetclass in the model
            clazz = RdfClass(iri, self.graph)
            nodeshapes = clazz.get_nodeshapes()
            l = len(nodeshapes)
            if l > 1:
                log.warn(
                    "Found {} nodeshapes for class {}. Selecting {}.".format(
                        l, iri, nodeshapes[0].iri
                    )
                )
            if l > 0:
                return nodeshapes[0].iri
        return iri  # no nodeschape, so just reference the class as type

    def xsd_datatype(self) -> str:
        # TODO: what if multiple datatypes are defined?
        constraints = self.get_constraints()
        datatype = list(
            filter(lambda c: c.constraint_iri.lower().endswith("datatype"), constraints)
        )
        if len(datatype) == 1:  # must be simple type
            return datatype[0].value
        return None

    def class_datatype(self) -> str:
        # TODO: what if multiple datatypes are defined?
        constraints = self.get_constraints()
        datatype = list(
            filter(lambda c: c.constraint_iri.lower().endswith("class"), constraints)
        )
        if len(datatype) == 1:  # relationship to instances of another class
            return datatype[0].value
        return None

    def is_object_reference(self) -> bool:
        constraints = self.get_constraints()
        datatype = list(
            filter(lambda c: c.constraint_iri.lower().endswith("datatype"), constraints)
        )
        if len(datatype) == 1:  # must be simple type
            return False
        datatype = list(
            filter(lambda c: c.constraint_iri.lower().endswith("class"), constraints)
        )
        if len(datatype) == 1:  # relationship to instances of another class
            return True
        return False  # meaning we will not put any constraint in JSON-SCHEMA

    def get_nodeshapes(self) -> List[NodeShape]:
        prop = None
        if urlparse(self.iri).scheme == "":  #  if this is a blank node
            prop = BNode(self.iri)
        else:
            prop = URIRef(self.iri)
        result = self.graph.query(self.SHAPE_QUERY, initBindings={"property": prop})
        shapes = []
        for r in result:
            shapes.append(NodeShape(str(r.shape), self.graph))
        shapes.sort(key=lambda s: s.label)
        return shapes


class Instance(SemanticModelElement):
    CLASS_QUERY = prepareQuery(
        """
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
                PREFIX owl: <http://www.w3.org/2002/07/owl#> 
                PREFIX sh:<http://www.w3.org/ns/shacl#>
                SELECT DISTINCT ?clazz
                WHERE
                {
                    ?instance rdf:type ?clazz .
                    ?class rdf:type rdfs:Class
                }
                """
    )

    def __init__(self, iri: str, graph: Graph):
        super().__init__(iri, graph)

    def get_classes(self) -> RdfClass:
        result = self.graph.query(
            self.CLASS_QUERY, initBindings={"instance": URIRef(self.iri)}
        )
        clazzes = []
        for r in result:
            clazzes.append(RdfClass(r.clazz, self.graph))
        clazzes.sort(key=lambda c: c.label)
        return clazzes


class SemanticModel(SemanticModelElement):
    MODEL_DETAILS_QUERY = prepareQuery(
        """
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX owl: <http://www.w3.org/2002/07/owl#>
                SELECT DISTINCT ?property ?value
                WHERE
                {
                    ?model rdf:type owl:Ontology .
                    ?model ?property ?value .
                }
                """
    )

    CLASS_QUERY = prepareQuery(
        """
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
                PREFIX sh:  <http://www.w3.org/ns/shacl#>
                PREFIX owl: <http://www.w3.org/2002/07/owl#> 
                SELECT DISTINCT ?instance
                WHERE
                {
                    {
                        {?instance rdf:type rdfs:Class .}
                        UNION 
                        { ?instance rdf:type owl:Class . }
                        UNION
                        {?instance rdfs:subClassOf rdfs:Class .}
                    }
                    MINUS {
                        ?instance rdf:type rdf:Property .                        
                        ?instance rdf:type rdfs:Property .
                        ?instance rdf:type sh:property .
                        ?instance rdf:type sh:PropertyShape .
                    }                    
                }
                """
    )

    SHACL_PROP_QUERY = prepareQuery(
        """
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX sh:  <http://www.w3.org/ns/shacl#>
                SELECT DISTINCT ?property
                WHERE
                {
                    { ?shape sh:property ?property }
                    UNION
                    { ?property rdf:type sh:Property }
                }
                """
    )

    INSTANCE_QUERY = prepareQuery(
        """
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
                PREFIX owl: <http://www.w3.org/2002/07/owl#> 
                PREFIX sh:  <http://www.w3.org/ns/shacl#>
                SELECT DISTINCT ?instance
                WHERE
                {
                    ?instance rdf:type ?clazz .
                    MINUS
                    {
                          ?instance rdf:type rdfs:Class .
                    }
                    MINUS
                    {
                          ?instance rdf:type rdf:Property . 
                    }
                    MINUS
                    {
                          ?instance rdf:type rdfs:Property . 
                    }
                    MINUS
                    {
                          ?instance rdf:type owl:Class . 
                    }
                    MINUS
                    {
                          ?instance rdf:type owl:Ontology . 
                    }
                    MINUS
                    {
                          ?instance rdf:type sh:NodeShape . 
                    }
                    MINUS
                    {
                          ?instance rdf:type sh:Property . 
                    }
                }
                """
    )

    def __init__(self, iri: str):
        super().__init__(iri)
        
    def get_model_details_for_iri(self, iri) -> dict:
        result = self.graph.query(
            self.MODEL_DETAILS_QUERY, initBindings={"model": URIRef(iri)}
        )
        details = {}
        for r in result:
            details[str(r.property)] = str(r.value)
        return details

    def get_model_details(self) -> dict:
        result = self.get_model_details_for_iri(self.iri)
        if result == {} and not (self.iri.endswith("/") or self.iri.endswith("#")):
            result = self.get_model_details_for_iri(self.iri + "/")
            if result == {}:
                result = self.get_model_details_for_iri(self.iri + "#")
        return result

    def get_types_of_instance(self, instance_iri: str) -> str:
        result = self.graph.query(
            self.TYPE_QUERY, initBindings={"instance": URIRef(instance_iri)}
        )
        types = []
        for r in result:
            types.append(str(r.type))
        types.sort(key=lambda c: c)
        return types

    def get_instances_of_type(self, type_iri: str, type_class: type) -> list:
        type_ref = URIRef(type_iri)
        result = self.graph.query(self.TYPE_QUERY, initBindings={"type": type_ref})
        instances = []
        for r in result:
            instances.append(type_class(str(r.instance), self.graph))
        return instances

    def get_classes(self) -> List[RdfClass]:
        # can't use the generic query here as we explicitly need to exclude rdfs & shacl properties
        # (which end up being classes themselves)
        result = self.graph.query(self.CLASS_QUERY)
        classes = []
        for r in result:
            classes.append(RdfClass(str(r.instance), self.graph))
        classes.sort(key=lambda c: c.label)
        return classes

    def get_instances(self) -> List[Instance]:
        result = self.graph.query(self.INSTANCE_QUERY)
        instances = []
        for r in result:
            instances.append(Instance(r.instance, self.graph))
        instances.sort(key=lambda c: c.label)
        return instances

    def is_instance(self, iri: str) -> bool:
        result = self.graph.query(self.INSTANCE_QUERY)
        for r in result:
            if str(r.instance) == iri:
                return True
        return False

    def get_properties(self) -> List[RdfProperty]:
        result = self.get_instances_of_type(self.RDFS_PROPERTY, RdfProperty)
        result += self.get_instances_of_type(self.RDF_PROPERTY, RdfProperty)
        result.sort(key=lambda c: c.label)
        return result

    def get_node_shapes(self) -> List[NodeShape]:
        shapes = self.get_instances_of_type(self.SHACL_NODESHAPE, NodeShape)
        shapes.sort(key=lambda c: c.label)
        return shapes

    def get_shacl_properties(self) -> List[ShaclProperty]:
        result = self.graph.query(self.SHACL_PROP_QUERY)
        props = []
        for r in result:
            props.append(ShaclProperty(str(r.property), self.graph))
        props.sort(key=lambda c: c.label)
        return props
