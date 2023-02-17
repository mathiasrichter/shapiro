# Renderer gets a graph and a focus node
# It registeres a number of SPARQL queries. For each query, it registers an HTML template to render the data resulting from the SPARQL query.
# The template can use additional standardized queries to get further information from the graph through the renderer.
from liquid import Environment
from liquid import Mode
from liquid import StrictUndefined
from liquid import FileSystemLoader
from urllib.parse import urlparse
from urllib.error import HTTPError
from shapiro_model import RdfClass, RdfProperty, SemanticModel, SemanticModelElement, ShaclConstraint, ShaclProperty
from shapiro_util import NotFoundException, prune_iri, get_logger
import markdown as md

log = get_logger("SHAPIRO_RENDER")

def url(value:str) -> str:
    url = urlparse(value)
    if url.scheme != '' and url.scheme is not None:
        return '<a href="'+value+'" target="blank">'+prune_iri(value)+'</a>'
    return value

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
        self.env.add_filter("markdown", md.markdown)
    
    def render_page(self, base_url:str, content:str) -> str:
        return self.env.get_template("render_page.html").render(url = base_url, content = content)
    
    def render_model(self, base_url:str, model_iri: str) -> str:
        log.info("HTML rendering model at {}".format(model_iri), stack_info=True)
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
        log.info("HTML rendering model element at {}".format(iri))
        s = SemanticModel(iri)
        content = ""
        for t in s.get_types_of_instance(iri):
            if t == s.RDFS_CLASS:
                content += self.render_class(base_url, s)
            elif t == s.RDFS_PROPERTY or t == s.RDF_PROPERTY:
                content += self.render_property(base_url, s)
            elif t == s.SHACL_NODESHAPE:
                content += self.render_nodeshape(base_url, s)
            elif t == s.SHACL_PROPERTY:
                content += self.render_shacl_property(base_url, s)
        if content == "" or content is None:
            msg = "Cannot render HTML for {} (element not found, or type of element could not be determined)".format(iri)
            log.error(msg)
            raise NotFoundException(msg)
        log.info("HTML rendering full page for model element at {}".format(iri))
        return self.render_page( base_url, content )
    
    def render_class(self, base_url:str, model:SemanticModel) -> str:
        log.info("HTML rendering class at {}".format(model.iri))
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
                    types = c.get_types(),
                    properties = c.get_properties(),
                    prop_count = len(c.get_properties()),
                    prop_types = prop_types,
                    superclasses = c.get_superclasses(),
                    shapes = c.get_nodeshapes()
                )

    def render_property(self, base_url:str, model:SemanticModel) -> str:
        log.info("HTML rendering property at {}".format(model.iri))
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
                    types = p.get_types(),
                    classes = p.get_classes(),
                    prop_type = p.get_property_type(),
                    superprop = p.get_superproperties(),
                    shacl_props = shacl_props,
                    shacl_prop_count = len(shacl_props),
                    shacl_prop_shapes = prop_shapes,
                    shacl_prop_constraints = prop_constraints
                )

    def render_nodeshape(self, base_url:str, model:SemanticModel) -> str:
        log.info("HTML rendering nodeshape at {}".format(model.iri))
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
                    types = n.get_types(),
                    classes = n.get_classes(),
                    shacl_props = shacl_props,
                    shacl_prop_count = len(shacl_props),
                    shacl_prop_shapes = prop_shapes,
                    shacl_prop_constraints = prop_constraints
                )

    def render_shacl_property(self, base_url:str, model:SemanticModel) -> str:
        log.info("HTML rendering SHACL property at {}".format(model.iri))
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
                    types = sp.get_types(),
                    shapes = prop_shapes,
                    constraints = prop_constraints,
                    constraint_count = constraint_count
                )

