from rdflib import Graph, URIRef, BNode
from rdflib.plugins.sparql import prepareQuery
from typing import Tuple
from shapiro_util import NotFoundException, prune_iri
from urllib.parse import urlparse

class Subscriptable:
    
    def __getitem__(self, key):
        if key not in self.__dict__.keys():
            raise Exception("Class '{}' does not have property '{}'.".format(type(self), key))
        return self.__dict__[key]
    
class SemanticModelElement(Subscriptable):

    RDFS_CLASS = 'http://www.w3.org/2000/01/rdf-schema#Class'
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
                        self.graph = Graph().parse(iri)
                except:
                    # happens when the overall ontology is exists, but any term contained does not resolve (e.g. if the IRIs are wrong)
                    raise NotFoundException("Cannot resolve the requested term in the existing ontology {}".format(iri))
            self.label, self.title, self.comment, self.description, self.definition = self.get_label_and_descriptions()
            if self.label == "" and self.title == "":
                self.label = self.title = prune_iri(self.iri, True)
        else:
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
        #return (label, title, comment, description, definition)
        return (label, title, comment, description, definition)
    
    def get_type(self) -> str:
        if urlparse(self.iri).scheme == '': #  if this is a blank node
            ref = BNode(self.iri)
        else:
            ref = URIRef(self.iri)
        result = self.graph.query(self.TYPE_QUERY, initBindings={'instance':ref})
        for r in result:
            return str(r.type)
        return "n/a"        

class RdfProperty(SemanticModelElement):
    
    CLASSES_QUERY = prepareQuery("""
        PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
        SELECT DISTINCT ?result
        WHERE
        {
            ?property rdf:type rdfs:Property .
            OPTIONAL { ?property rdfs:domain ?result . }
        }
        """)

    SUPERPROPS_QUERY = prepareQuery("""
        PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
        SELECT DISTINCT ?result
        WHERE
        {
            ?property rdf:type rdfs:Property .
            OPTIONAL { ?property rdfs:subPropertyOf ?result . }
        }
        """)

    RANGE_QUERY = prepareQuery("""
        PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
        SELECT DISTINCT ?result
        WHERE
        {
            ?property rdf:type rdfs:Property .
            OPTIONAL { ?property rdfs:range ?result . }
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
        
    def query(self, query:str) -> list[str]:
        qresult = self.graph.query(query, initBindings={'property': URIRef(self.iri)})
        result = []
        for r in qresult:
            result.append(str(r.result))
        result.sort(key=lambda c: c)
        return result
    
    def get_property_type(self) -> list[str]:
        return self.query(self.RANGE_QUERY)

    def get_superproperties(self) -> list[str]:
        return self.query(self.SUPERPROPS_QUERY)

    def get_classes(self) -> list[str]:
        return self.query(self.CLASSES_QUERY)
    
    def get_shacl_properties(self) -> list[str]:
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
        
    def get_shacl_properties(self) -> list['ShaclProperty']:
        result = self.graph.query(self.SHACL_PROP_QUERY, initBindings={'shape': URIRef(self.iri)})
        props = []
        for r in result:
            props.append(ShaclProperty(str(r.shacl_prop), self.graph))
        props.sort(key=lambda p:p.label)
        return props
       
    def get_classes(self) -> list['RdfClass']:
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
        PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
        SELECT DISTINCT ?property
        WHERE
        {
            ?property rdf:type rdfs:Property .
            ?property rdfs:domain ?class .
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

    def get_properties(self) -> list[RdfProperty]:
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
    
    def get_nodeshapes(self) -> list[NodeShape]:
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
             
    def get_constraints(self) -> list[ShaclConstraint]:
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
                        ?instance rdf:type rdfs:Property .
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
        
    def get_model_details(self) -> dict:
        result = self.graph.query(self.MODEL_DETAILS_QUERY, initBindings={'model':URIRef(self.iri)})
        details = {}
        for r in result:
            details[str(r.property)] = str(r.value)
        return details
    
    def get_types_of_instance(self, instance_iri:str) -> str:
        result = self.graph.query(self.TYPE_QUERY, initBindings={'instance':URIRef(instance_iri)})
        types = []
        for r in result:
            types.append(str(r.type))
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
    
    def get_classes(self) -> list[RdfClass]:
        # can't use the generic query here as we explicitly need to exclude rdfs & shacl properties
        # (which end up being classes themselves)
        result = self.graph.query(self.CLASS_QUERY)
        classes = []
        for r in result:
            classes.append(RdfClass(str(r.instance)))
        classes.sort(key=lambda c: c.label)
        return classes
   
    def get_properties(self) -> list[RdfProperty]:
        result = self.get_instances_of_type(self.RDFS_PROPERTY, RdfProperty)
        result.sort(key=lambda c: c.label)
        return result
    
    def get_node_shapes(self) -> list[NodeShape]:
        shapes = self.get_instances_of_type(self.SHACL_NODESHAPE, NodeShape)
        shapes.sort(key=lambda c: c.label)
        return shapes
    
    def get_shacl_properties(self) -> list[ShaclProperty]:
        result = self.graph.query(self.SHACL_PROP_QUERY)
        props = []
        for r in result:
            props.append(ShaclProperty(str(r.property), self.graph))
        props.sort(key=lambda c: c.label)
        return props

