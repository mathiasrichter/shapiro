from rdflib import Graph, URIRef, BNode
from rdflib.plugins.sparql import prepareQuery
from rdflib.plugin import PluginException
from typing import Tuple, List
from shapiro_util import NotFoundException, prune_iri, get_logger
from urllib.parse import urlparse
import logging

log = get_logger("SHAPIRO_RENDER")

class Subscriptable:
    
    def __getitem__(self, key):
        if key not in self.__dict__.keys():
            raise Exception("Class '{}' does not have property '{}'.".format(type(self), key))
        return self.__dict__[key]
    
class SemanticModelElement(Subscriptable):

    RDFS_CLASS = 'http://www.w3.org/2000/01/rdf-schema#Class'
    RDF_PROPERTY = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#Property'
    RDFS_PROPERTY = 'http://www.w3.org/2000/01/rdf-schema#Property'
    SHACL_NODESHAPE = 'http://www.w3.org/ns/shacl#NodeShape'
    SHACL_PROPERTY = 'http://www.w3.org/ns/shacl#Property'
        
    TYPE_QUERY = prepareQuery("""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            SELECT DISTINCT ?instance ?type
            WHERE
            {
                ?instance rdf:type ?type .
            }
            """)
    
    DESCRIPTION_QUERY = prepareQuery("""
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
                """)

    def __init__(self, iri:str, graph: Graph = None):
        log.info("Initializing model for {}".format(iri))
        self.iri = iri
        self.graph = graph
        self.label, self.title, self.comment, self.description, self.definition = ( "", "", "", "", "" )
        if urlparse(iri).scheme != '': #  if this is not a blank node
            if graph is None:
                try:
                    if "schema.org" in iri.lower():
                        # rdflib and schema.org both need a little more love - see https://github.com/RDFLib/rdflib-jsonld/issues/42
                        self.graph = Graph().parse("http://schema.org", format='json-ld')
                    else:
                        try: 
                            self.graph = Graph().parse(iri)
                        except PluginException as p:
                            log.warn("Creating empty graph in response to {}".format(p))
                            self.graph = Graph() # some schema servers like FOAF don't act nice for term references
                except Exception as x:
                    # happens when the overall ontology is exists, but any term contained does not resolve (e.g. if the IRIs are wrong)
                    msg = msg = "Cannot resolve the requested term in the existing ontology '{}' ({})".format(iri,x)
                    log.error(msg)
                    if '#' in iri:
                        msg += " It looks like your IRI contains a URL fragment ('#') not supported by Shapiro."
                    raise NotFoundException(msg)
            self.label, self.title, self.comment, self.description, self.definition = self.get_label_and_descriptions()
            if self.label == "" and self.title == "":
                log.warn("Empty title, label, description and comment from graph query. Setting label/title to default for {}".format(self.iri))
                self.label = self.title = prune_iri(self.iri, True)
        else:
            log.warn("Cannot create graph - setting to 'unnamed' 'n/a' for {}".format(self.iri))
            self.label = self.title = "unnamed"
            self.comment = self.description = self.definition = "n/a"
 
    def get_label_and_descriptions(self) -> Tuple[str, str, str, str, str]:
        result = self.graph.query(self.DESCRIPTION_QUERY, initBindings={'model': URIRef(self.iri)})
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
        if urlparse(self.iri).scheme == '': #  if this is a blank node
            ref = BNode(self.iri)
        else:
            ref = URIRef(self.iri)
        result = self.graph.query(self.TYPE_QUERY, initBindings={'instance':ref})
        types = []
        for r in result:
            types.append(str(r.type))
        types.sort(key=lambda c: c)
        return types

class RdfProperty(SemanticModelElement):
    
    CLASSES_QUERY = prepareQuery("""
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
        """)

    SUPERPROPS_QUERY = prepareQuery("""
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
        """)

    RANGE_QUERY = prepareQuery("""
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
        """)

    SHACL_PROP_QUERY = prepareQuery(""" 
            PREFIX sh:<http://www.w3.org/ns/shacl#>
            SELECT DISTINCT ?shacl_prop
            WHERE
            {
                ?shacl_prop sh:path ?property .
            }
                """)

    def __init__(self, iri:str):
        super().__init__(iri)
        
    def query(self, query:str) -> List[str]:
        qresult = self.graph.query(query, initBindings={'property': URIRef(self.iri)})
        result = []
        for r in qresult:
            result.append(str(r.result))
        result.sort(key=lambda c: c)
        return result
    
    def get_property_type(self) -> List[str]:
        return self.query(self.RANGE_QUERY)

    def get_superproperties(self) -> List[str]:
        return self.query(self.SUPERPROPS_QUERY)

    def get_classes(self) -> List[str]:
        return self.query(self.CLASSES_QUERY)
    
    def get_shacl_properties(self) -> List[str]:
        result = self.graph.query(self.SHACL_PROP_QUERY, initBindings={'property': URIRef(self.iri)})
        props = []
        for r in result:
            props.append(ShaclProperty(str(r.shacl_prop), self.graph))
        props.sort(key=lambda p:p.label)
        return props

class NodeShape(SemanticModelElement):

    SHACL_PROP_QUERY = prepareQuery(""" 
            PREFIX sh:<http://www.w3.org/ns/shacl#>
            SELECT DISTINCT ?shacl_prop
            WHERE
            {
                ?shape sh:property ?shacl_prop .
            }
                """)

    CLASS_QUERY = prepareQuery(""" 
            PREFIX sh:<http://www.w3.org/ns/shacl#>
            SELECT DISTINCT ?target
            WHERE
            {
                ?shape sh:targetClass ?target .
            }
            """)
    
    def __init__(self, iri:str):
        super().__init__(iri)
        
    def get_shacl_properties(self) -> List['ShaclProperty']:
        result = self.graph.query(self.SHACL_PROP_QUERY, initBindings={'shape': URIRef(self.iri)})
        props = []
        for r in result:
            props.append(ShaclProperty(str(r.shacl_prop), self.graph))
        props.sort(key=lambda p:p.label)
        return props
       
    def get_classes(self) -> List['RdfClass']:
        result = self.graph.query(self.CLASS_QUERY, initBindings={'shape': URIRef(self.iri)})
        classes = []
        for r in result:
            classes.append(RdfClass(str(r.target)))
        classes.sort(key=lambda p:p.label)
        return classes
       
class RdfClass(SemanticModelElement):

    SUPERCLASSES_QUERY = prepareQuery("""
        PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
        SELECT DISTINCT ?superclass
        WHERE
        {
            ?subclass rdfs:subClassOf ?superclass .
        }
        """)

    PROPERTY_QUERY = prepareQuery("""
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
        """)

    SHAPE_QUERY = prepareQuery(""" 
                PREFIX sh:<http://www.w3.org/ns/shacl#>
                SELECT DISTINCT ?shape
                WHERE
                {
                    ?shape sh:targetClass ?class .
                }
                """)

    def __init__(self, iri:str):
        super().__init__(iri)

    def get_properties(self) -> List[RdfProperty]:
        result = self.graph.query(self.PROPERTY_QUERY, initBindings={'class': URIRef(self.iri)})
        props = []
        for r in result:
            props.append(RdfProperty(str(r.property)))
        props.sort(key=lambda c: c.label)
        return props
        
    def get_superclasses(self) -> list:
        result = self.graph.query(self.SUPERCLASSES_QUERY, initBindings={'subclass': URIRef(self.iri)})
        superclasses = []
        for r in result:
            superclasses.append(RdfClass(str(r.superclass)))
        superclasses.sort(key=lambda c: c.label)
        return superclasses
    
    def get_nodeshapes(self) -> List[NodeShape]:
        result = self.graph.query(self.SHAPE_QUERY, initBindings={'class': URIRef(self.iri)})
        shapes = []
        for r in result:
            shapes.append(NodeShape(str(r.shape)))
        shapes.sort(key=lambda c: c.label)
        return shapes        
    
class ShaclConstraint(Subscriptable):
    
    def __init__(self, constraint_iri:str, value:str):
        self.constraint_iri = constraint_iri
        self.value = value

class ShaclProperty(SemanticModelElement):

    SHAPE_QUERY = prepareQuery(""" 
                PREFIX sh:<http://www.w3.org/ns/shacl#>
                SELECT DISTINCT ?shape
                WHERE
                {
                    ?shape sh:property ?property .
                }
                """)
    
    SHACL_CONSTRAINTS_QUERY = prepareQuery(""" 
                SELECT DISTINCT ?constraint ?value
                WHERE
                {
                    ?property ?constraint ?value .
                    FILTER(STRSTARTS(STR(?constraint), "http://www.w3.org/ns/shacl#")) .
                }
                """)
    
    def __init__(self, iri:str, graph: Graph):
        super().__init__(iri, graph)
             
    def get_constraints(self) -> List[ShaclConstraint]:
        prop = None
        if urlparse(self.iri).scheme == '': #  if this is a blank node
            prop = BNode(self.iri)
        else:
            prop = URIRef(self.iri)
        result = self.graph.query(self.SHACL_CONSTRAINTS_QUERY, initBindings={'property': prop})
        constraints = []
        for r in result:
            constraints.append(ShaclConstraint(str(r.constraint), str(r.value)))
        constraints.sort(key=lambda c: c.constraint_iri)
        return constraints
    
    def get_nodeshapes(self):
        prop = None
        if urlparse(self.iri).scheme == '': #  if this is a blank node
            prop = BNode(self.iri)
        else:
            prop = URIRef(self.iri)
        result = self.graph.query(self.SHAPE_QUERY, initBindings={'property': prop})
        shapes = []
        for r in result:
            shapes.append(NodeShape(str(r.shape)))
        shapes.sort(key=lambda s:s.label)
        return shapes
    
class SemanticModel(SemanticModelElement):
        
    MODEL_DETAILS_QUERY = prepareQuery("""
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX owl: <http://www.w3.org/2002/07/owl#>
                SELECT DISTINCT ?property ?value
                WHERE
                {
                    ?model rdf:type owl:Ontology .
                    ?model ?property ?value .
                }
                """)
    
    CLASS_QUERY = prepareQuery("""
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
                PREFIX sh:  <http://www.w3.org/ns/shacl#>
                SELECT DISTINCT ?instance
                WHERE
                {
                    ?instance rdf:type rdfs:Class .
                    MINUS {
                        ?instance rdf:type rdf:Property .                        
                        ?instance rdf:type rdfs:Property .
                        ?instance rdf:type sh:property .
                        ?instance rdf:type sh:PropertyShape .
                    }                    
                }
                """)
    
    SHACL_PROP_QUERY =  prepareQuery("""
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX sh:  <http://www.w3.org/ns/shacl#>
                SELECT DISTINCT ?property
                WHERE
                {
                    { ?shape sh:property ?property }
                    UNION
                    { ?property rdf:type sh:Property }
                }
                """)

    def __init__(self, iri:str):
        super().__init__(iri)
        
    def get_model_details_for_iri(self, iri) -> dict:
        result = self.graph.query(self.MODEL_DETAILS_QUERY, initBindings={'model':URIRef(iri)})
        details = {}
        for r in result:
            details[str(r.property)] = str(r.value)
        return details
        
    def get_model_details(self) -> dict:
        result = self.get_model_details_for_iri(self.iri)
        if result == {} and not ( self.iri.endswith('/') or self.iri.endswith('#') ):
           result = self.get_model_details_for_iri(self.iri+"/")
           if result == {}:
               result = self.get_model_details_for_iri(self.iri+"#")
        return result
    
    def get_types_of_instance(self, instance_iri:str) -> str:
        result = self.graph.query(self.TYPE_QUERY, initBindings={'instance':URIRef(instance_iri)})
        types = []
        for r in result:
            types.append(str(r.type))
        types.sort(key=lambda c: c)
        return types   
        
    def get_instances_of_type(self, type_iri:str, type_class:type) -> list:
        type_ref = None
        if urlparse(type_iri).scheme == '': # if there's no scheme it must be a plain node, not a uri reference
            type_ref = BNode(type_iri)
        else:
            type_ref = URIRef(type_iri)
        result = self.graph.query(self.TYPE_QUERY, initBindings={'type':type_ref})
        instances = []
        for r in result:
            instances.append(type_class(str(r.instance)))
        return instances
    
    def get_classes(self) -> List[RdfClass]:
        # can't use the generic query here as we explicitly need to exclude rdfs & shacl properties
        # (which end up being classes themselves)
        result = self.graph.query(self.CLASS_QUERY)
        classes = []
        for r in result:
            classes.append(RdfClass(str(r.instance)))
        classes.sort(key=lambda c: c.label)
        return classes
   
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

