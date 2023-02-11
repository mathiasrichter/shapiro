# Renderer gets a graph and a focus node
# It registeres a number of SPARQL queries. For each query, it registers an HTML template to render the data resulting from the SPARQL query.
# The template can use additional standardized queries to get further information from the graph through the renderer.

from rdflib import Graph, URIRef, BNode
from rdflib.plugins.sparql import prepareQuery
from liquid import Environment
from liquid import Mode
from liquid import StrictUndefined
from liquid import FileSystemLoader
from typing import Tuple
from urllib.parse import urlparse
from urllib.error import HTTPError
from shapiro_util import NotFoundException
import markdown as md

KNOWN_PREFIXES = {
    'http://www.w3.org/2000/01/rdf-schema#': 'rdfs:',
    'http://www.w3.org/2004/02/skos/core#': 'skos:',
    'http://purl.org/dc/terms/': 'dct:' ,
    'http://www.w3.org/2002/07/owl#': 'owl:',
    'http://www.w3.org/ns/shacl#': 'shacl:',
    'http://www.w3.org/1999/02/22-rdf-syntax-ns#': 'rdf:',
    'http://schema.org': 'schema:',
    'http://www.w3.org/ns/adms#': 'adms:',
    'http://www.w3.org/2001/XMLSchema#': 'xsd:',
    'http://http://xmlns.com/foaf/0.1/': 'foaf:',
    'http://dbpedia.org/resource/': 'dbpedia:',
    'http://www.w3.org/ns/odrl1/2/': 'odrl:',
    'http://www.w3.org/ns/org#': 'org:',    
    'http://www.w3.org/2006/time#': 'time:',
    'http://www.w3.org/TR/vocab-dcat-2/#': 'dcat:',
    'http://purl.org/adms/status/': 'adms:'
}

def capitalize(name:str) -> str:
    return name[0].upper() + name[1:len(name)]

def prefix(iri:str, name:str) -> str:
    for k in KNOWN_PREFIXES.keys():
        if iri.lower().startswith(k.lower()):
            return KNOWN_PREFIXES[k] + name
    return name

def prune_iri(iri:str, name_only:bool = False) -> str:
    url = urlparse(iri)
    result = url.path
    if result.startswith('/'):
        result = result[1:len(result)]
    if (url.fragment == '' or url.fragment is None): 
        if result.endswith('/'):
            result = result[0:len(result)-1]
        result = result[result.rfind('/')+1:len(result)]
    else:
        result = url.fragment
    if name_only is False:
        result = prefix(iri, result)
    if result.__contains__(':'):
        return result
    else:
        return capitalize(result)
    
def url(value:str) -> str:
    url = urlparse(value)
    if url.scheme != '' and url.scheme is not None:
        return '<a href="'+value+'" target="blank">'+prune_iri(value)+'</a>'
    return value

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
        return (label, title, md.markdown(comment), md.markdown(description), md.markdown(definition))
    
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

class HtmlRenderer:    
    
    def __init__(self, template_path: str = './templates'):
        self.queries = []
        self.env = Environment(
            tolerance=Mode.STRICT,
            undefined=StrictUndefined,
            loader=FileSystemLoader(template_path),
        )
        self.env.add_filter("prune", prune_iri)
        self.env.add_filter("url", url)
    
    def render_page(self, base_url:str, content:str) -> str:
        return self.env.get_template("render_page.html").render(url = base_url, content = content)
    
    def render_model(self, base_url:str, model_iri: str) -> str:
        s = SemanticModel(model_iri)
        class_list = s.get_classes()
        shape_list = s.get_node_shapes()
        prop_list = s.get_properties()
        model_details = s.get_model_details()
        model_details_keys = list(model_details.keys())
        model_details_keys.sort(key=lambda k: prune_iri(k, True))
        model_details_names = {}
        for k in model_details_keys:
            model_details_names[k] = prune_iri(k, True)
        model_details_count = len(model_details_keys)
        content = self.env.get_template("render_model.html").render(
            url = base_url, 
            model = s, 
            model_details = model_details,
            model_details_count = model_details_count,
            model_details_keys = model_details_keys,
            model_details_names = model_details_names,
            classes = class_list,
            class_count = len(class_list), 
            shapes = shape_list,
            shape_count = len(shape_list),
            properties = prop_list,
            property_count = len(prop_list))
        return self.render_page( base_url, content )
    
    def render_model_element( self, base_url:str, iri: str) -> str:
        s = SemanticModel(iri)
        content = ""
        for t in s.get_types_of_instance(iri):
            if t == s.RDFS_CLASS:
                content += self.render_class(base_url, s)
            elif t == s.RDFS_PROPERTY:
                content += self.render_property(base_url, s)
            elif t == s.SHACL_NODESHAPE:
                content += self.render_nodeshape(base_url, s)
            elif t == s.SHACL_PROPERTY:
                content += self.render_shacl_property(base_url, s)
        if content == "" or content is None:
            raise NotFoundException("Cannot render HTML for {} (element not found, or type of element could not be determined)".format(iri))
        return self.render_page( base_url, content )
    
    def render_class(self, base_url:str, model:SemanticModel) -> str:
        for c in model.get_classes():
            if c.iri == model.iri:
                prop_types = {}
                for p in c.get_properties():
                    prop_types[p.iri] = []
                    for t in p.get_property_type():
                        prop_types[p.iri].append(t)
                return self.env.get_template("render_class.html").render(
                    url = base_url, 
                    model = model,
                    model_iri = c.iri[0:c.iri.rfind('/')],
                    the_class = c,
                    type = c.get_type(),
                    properties = c.get_properties(),
                    prop_count = len(c.get_properties()),
                    prop_types = prop_types,
                    superclasses = c.get_superclasses(),
                    shapes = c.get_nodeshapes()
                )

    def render_property(self, base_url:str, model:SemanticModel) -> str:
        for p in model.get_properties():
            if p.iri == model.iri:
                shacl_props = p.get_shacl_properties()
                prop_shapes = {}
                prop_constraints = {}
                for sp in shacl_props:
                    prop_shapes[sp.iri] = list(map( lambda n: n.iri, sp.get_nodeshapes()))
                    prop_constraints[sp.iri] = sp.get_constraints()
                return self.env.get_template("render_property.html").render(
                    url = base_url, 
                    model = model, 
                    model_iri = p.iri[0:p.iri.rfind('/')],
                    property = p,
                    type = p.get_type(),
                    classes = p.get_classes(),
                    prop_type = p.get_property_type(),
                    superprop = p.get_superproperties(),
                    shacl_props = shacl_props,
                    shacl_prop_count = len(shacl_props),
                    shacl_prop_shapes = prop_shapes,
                    shacl_prop_constraints = prop_constraints
                )

    def render_nodeshape(self, base_url:str, model:SemanticModel) -> str:
        for n in model.get_node_shapes():
            if n.iri == model.iri:
                shacl_props = n.get_shacl_properties()
                prop_shapes = {}
                prop_constraints = {}
                for sp in shacl_props:
                    prop_shapes[sp.iri] = list(map( lambda n: n.iri, sp.get_nodeshapes()))
                    prop_constraints[sp.iri] = sp.get_constraints()
                return self.env.get_template("render_shape.html").render(
                    url = base_url, 
                    model = model, 
                    model_iri = n.iri[0:n.iri.rfind('/')],
                    shape = n,
                    type = n.get_type(),
                    classes = n.get_classes(),
                    shacl_props = shacl_props,
                    shacl_prop_count = len(shacl_props),
                    shacl_prop_shapes = prop_shapes,
                    shacl_prop_constraints = prop_constraints
                )

    def render_shacl_property(self, base_url:str, model:SemanticModel) -> str:
        shacl_props = model.get_shacl_properties()
        for sp in shacl_props:
            if sp.iri == model.iri:
                prop_shapes = sp.get_nodeshapes()
                prop_constraints = sp.get_constraints()
                constraint_count = len(prop_constraints)
                return self.env.get_template("render_shacl_property.html").render(
                    url = base_url, 
                    model = model, 
                    model_iri = sp.iri[0:sp.iri.rfind('/')],
                    property = sp,
                    type = sp.get_type(),
                    shapes = prop_shapes,
                    constraints = prop_constraints,
                    constraint_count = constraint_count
                )

