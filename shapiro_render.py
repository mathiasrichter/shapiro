from liquid import Environment
from liquid import Mode
from liquid import StrictUndefined
from liquid import FileSystemLoader
from urllib.parse import urlparse
from urllib.error import HTTPError
from shapiro_model import (
    Subscriptable,
    RdfClass,
    RdfProperty,
    SemanticModel,
    SemanticModelElement,
    ShaclConstraint,
    ShaclProperty,
    NodeShape,
)
from shapiro_util import (
    NotFoundException,
    ConflictingPropertyException,
    prune_iri,
    get_logger,
)
import markdown as md
import multiline
from typing import List
import re

log = get_logger("SHAPIRO_RENDER")

def url(value: str) -> str:
    url = urlparse(value)
    if url.scheme != "" and url.scheme is not None:
        return '<a href="' + value + '" data-bs-toggle="tooltip" data-bs-original-title="' + value + '">' + prune_iri(value) + "</a>"
    return value

def extract_namespace(iri:str):
    if iri.endswith('/'):
        iri = iri[0:len(iri)-1]
    if '#' in iri:
        iri = iri[0:iri.rfind('#')]
    iri = iri[0:iri.rfind('/')]
    namespace = iri[iri.rfind('/')+1:len(iri)].replace('.','_')
    valid = re.match('[a-zA-Z]+', namespace) is not None
    while valid is False:
        iri = iri[0:iri.rfind('/')]
        namespace = iri[iri.rfind('/')+1:len(iri)].replace('.','_')
        valid = re.match('[a-zA-Z]+', namespace) is not None
    return namespace
    

def get_id(iri:str):
    return iri.replace(':','_').replace('/','_').replace('.','_')    
        
class MermaidProperty(Subscriptable):
    
    def __init__(self, type_label:str, label:str):
        self.type_label = type_label
        self.label = label

    def __eq__(self, other):
        return self.type_label == other.type_label and self.label == other.label
    
    def __hash__(self):
        return hash((self.type_label, self.label))

class MermaidClass(Subscriptable):
    
    def __init__(self, iri:str, label:str, stereotype:str):
        self.iri = iri
        self.id = get_id(iri)
        self.namespace = extract_namespace(iri)
        self.label = label
        self.stereotype = stereotype
        self.properties = []
        
    def add_property(self, property:MermaidProperty):
        self.properties.append(property)

    def __eq__(self, other):
        return self.iri == other.iri
    
    def __hash__(self):
        return hash(self.iri)

class MermaidConnection(Subscriptable):
    
    INHERITANCE = 0
    ASSOCIATION = 1
    TARGET_CLASS = 2

    def __init__(self, from_node:str, to_node:str, connection_type:int, label:str=""):
        self.from_node = from_node
        self.to_node = to_node
        self.connection_type = connection_type
        self.label = label
        
    def __eq__(self, other):
        return self.from_node == other.from_node and self.to_node == other.to_node and self.label == other.label
    
    def __hash__(self):
        return hash((self.from_node, self.to_node, self.label))

class MermaidRenderer:
    
    def __init__(self, template_path: str = "./templates"):
        self.env = Environment(
            tolerance=Mode.STRICT,
            undefined=StrictUndefined,
            loader=FileSystemLoader(template_path),
        )
        
    def render_model(self, model_iri:str) -> str:
        log.info("Rendering model diagram for {}".format(model_iri))
        s = SemanticModel(model_iri)
        classes = []
        connections = []
        for c in s.get_classes():
            cl, co = self.get_class_structure(c)
            classes += cl
            connections += co
        for n in s.get_node_shapes():
            cl, co = self.get_shape_structure(n)
            classes += cl
            connections += co
        result = self.env.get_template("render.mermaid").render(
            classes=list(set(classes)),
            connections=list(set(connections))
        )
        return result
        
    def get_class_structure(self, the_class:RdfClass) -> {}:
        classes = []
        connections = []
        iri = the_class.iri
        stereotype = ""
        for t in the_class.get_types():
            if stereotype == "":
                stereotype += t
            else:
                stereotype += ', ' + t
        result = MermaidClass(iri, the_class.label, stereotype)
        classes.append(result)
        for p in the_class.get_properties():
            typestring = ""
            is_scalar_type = False
            for t in p.get_property_type():
                if p.is_xsd_datatype() is True:
                    is_scalar_type = True
                if typestring == "":
                    typestring += t
                else:
                    typestring += ', ' + t
            if is_scalar_type is True:
                result.add_property(MermaidProperty(typestring, p.label))
            else:
                    target = MermaidClass(p.iri, p.label, typestring)
                    classes.append(target)
                    connections.append(MermaidConnection(result.id, target.id, MermaidConnection.ASSOCIATION, p.label))                
        for s in the_class.get_superclasses(False):
            cl, cn = self.get_class_structure(s)
            classes += cl
            connections += cn
            connections.append(MermaidConnection(get_id(the_class.iri), get_id(s.iri), MermaidConnection.INHERITANCE))
        # TODO: add nodeshapes for which this class is the target class, but how much of the nodeshape diagram do we want to render? Full or just the nodeshape itself? definitely different colors?
        for n in the_class.get_nodeshapes():
            nl, nn = self.get_shape_structure(n)
            classes += nl
            connections += nn
            connections.append(MermaidConnection(get_id(n.iri), get_id(the_class.iri), MermaidConnection.TARGET_CLASS))
        return classes, list(set(connections))
        
    def get_shape_structure(self, the_shape:NodeShape) -> {}:
        classes = []
        connections = []
        iri = the_shape.iri
        stereotype = ""
        for t in the_shape.get_types():
            if stereotype == "":
                stereotype += t
            else:
                stereotype += ', ' + t
        result = MermaidClass(iri, the_shape.label, stereotype)
        classes.append(result)
        for p in the_shape.get_shacl_properties()+the_shape.get_inherited_shacl_properties():
            tp = p.get_target_property()
            label = p.label
            if label == 'unnamed':
                label = tp.label
            typestring = p.xsd_datatype()
            if p.is_object_reference() is False and typestring is not None and typestring != '':
                result.add_property(MermaidProperty(typestring, label))
            else:
                    target = MermaidClass(tp.iri, label, p.class_datatype())
                    classes.append(target)
                    connections.append(MermaidConnection(result.id, target.id, MermaidConnection.ASSOCIATION, label))                
        return classes, list(set(connections))
    
    def render_class(self, iri:str) -> str:
        log.info("Rendering class diagram for {}".format(iri))
        s = SemanticModel(iri)
        classes = []
        connections = []
        for c in s.get_classes():
            if c.iri == s.iri:
                classes, connections = self.get_class_structure(c)
        return self.env.get_template("render.mermaid").render(
            classes=classes,
            connections=connections
        )
        
    def render_nodeshape(self, iri:str) -> str:
        log.info("Rendering class diagram for {}".format(iri))
        s = SemanticModel(iri)
        classes = []
        connections = []
        for c in s.get_node_shapes():
            if c.iri == s.iri:
                classes, connections = self.get_shape_structure(c)
        return self.env.get_template("render.mermaid").render(
            classes=classes,
            connections=connections
        )
  
class JsonSchemaRenderer:
    def __init__(self, template_path: str = "./templates"):
        self.env = Environment(
            tolerance=Mode.STRICT,
            undefined=StrictUndefined,
            loader=FileSystemLoader(template_path),
        )

    def convert_shacl_constraints(
        self, shacl_constraints: List[ShaclConstraint]
    ) -> List[dict]:
        constraints = []
        for c in shacl_constraints:
            name = c.get_json_schema_name()
            if name is not None:
                d = {
                    "name": name,
                    "needs_quotes": c.needs_quotes(),
                    "value": c.value,
                }
                delim = ""
                remove = 2
                if c.needs_quotes() is True:
                    delim = '"'
                    remove = 3
                if c.is_enum is True:
                    v = "[" + delim
                    for i in c.value:
                        v += str(i) + delim + ", " + delim
                    v = v[0 : len(v) - remove] + "]"
                    d["value"] = v
                    d["needs_quotes"] = False  # avoid outer quotes around enum array
                constraints.append(d)
        return constraints

    def get_data_for_shape(self, shape: NodeShape) -> dict:
        properties = (
            []
        )  # list of dicts with all information for each property, including constraints
        shacl_props = shape.get_shacl_properties()
        shacl_props = shacl_props + shape.get_inherited_shacl_properties()
        for p in shacl_props:
            name = p.get_json_schema_name()
            jstype = p.get_json_schema_type()
            type = None
            format = None
            if jstype is not None:
                type = jstype[0]
                format = jstype[1]
            prop = {
                "iri": p.get_iri(),
                "type": type,
                "format": format,
                "is_object": p.is_object_reference(),
                "is_array": p.is_array(),
                "name": p.get_json_schema_name(),
                "description": p.get_json_schema_comment(),
                "is_required": p.is_required(),
            }
            prop["array_item_constraints"] = self.convert_shacl_constraints(
                p.get_json_schema_array_item_constraints()
            )
            prop["array_item_constraint_count"] = len(prop["array_item_constraints"])
            prop["constraints"] = []
            for d1 in self.convert_shacl_constraints(p.get_constraints()):
                is_array_item_constraint = False
                for d2 in prop["array_item_constraints"]:
                    if d1["name"] == d2["name"] and d1["value"] == d2["value"]:
                        is_array_item_constraint = True
                if not is_array_item_constraint and not (
                    p.is_array() == False
                    and (d1["name"] == "maxItems" or d1["name"] == "minItems")
                ):
                    prop["constraints"].append(d1)
            prop["constraint_count"] = len(prop["constraints"])
            if self.is_conflict(properties, prop) == False:
                properties.append(prop)
            else:
                msg = "Cannot produce well-formed JSON-SCHEMA: The SHACL property for {} defined in shape {} conflicts with another SHACL property for the same {} defined in the same shape or another shape.".format(
                    prop["name"],
                    list(map(lambda s: s.iri, p.get_nodeshapes())),
                    prop["name"],
                )
                log.error(msg)
                raise ConflictingPropertyException(msg)
        return properties

    def is_conflict(self, properties: List[dict], property: dict):
        # check if the specified property is already in the list of properties
        # this can happen if different nodeshapes with the same targetclass
        # define SHACL property constraints on the same properties of the shared targetclass.
        for p in properties:
            if p["iri"] == property["iri"]:
                return True
        return False

    def render_nodeshape(self, shape_iri: str) -> str:
        log.info("Rendering JSON-SCHEMA for {}".format(shape_iri))
        s = SemanticModel(shape_iri)
        shape_list = s.get_node_shapes()
        shapes = list(filter(lambda s: s.iri == shape_iri, shape_list))
        content = None
        if len(shapes) == 0 or len(shapes) > 1:
            log.warn("{} shape(s) found for iri '{}'".format(len(shapes), shape_iri))
            content = self.env.get_template("render_model.jsonschema").render(
                shape_iri=shape_iri,
                shape_label=s.label,
                shape_description=s.comment,
                properties=[],
                required=[],
                required_count=0,
            )
        else:
            shape = shapes[0]
            properties = self.get_data_for_shape(shape)
            required = list(filter(lambda p: p["is_required"] == True, properties))
            content = self.env.get_template("render_model.jsonschema").render(
                shape_iri=shape_iri,
                shape_label=shape.label,  # TODO: use target class label if shape label is empty
                shape_description=shape.get_json_schema_comment(),
                properties=properties,
                required=required,
                required_count=len(required),
            )
        d = multiline.loads(
            content, multiline=True
        )  # this ensures template generated valid JSON...
        return multiline.dumps(
            d, indent=5
        )  # ...and we can return properly formatted JSON (while keeping the template code readable)


class HtmlRenderer:
    def __init__(self, template_path: str = "./templates"):
        self.queries = []
        self.env = Environment(
            tolerance=Mode.STRICT,
            undefined=StrictUndefined,
            loader=FileSystemLoader(template_path),
        )
        self.env.add_filter("prune", prune_iri)
        self.env.add_filter("url", url)
        self.env.add_filter("markdown", md.markdown)
        self.diagram_renderer = MermaidRenderer(template_path)

    def render_page(self, base_url: str, content: str) -> str:
        return self.env.get_template("render_page.html").render(
            url=base_url, content=content
        )

    def render_model(self, base_url: str, model_iri: str) -> str:
        log.info("HTML rendering model at {}".format(model_iri))
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
        instances = s.get_instances()
        instance_count = len(instances)
        instance_classes = {}
        for i in instances:
            instance_classes[i.iri] = i.get_classes()
        content = self.env.get_template("render_model.html").render(
            url=base_url,
            model=s,
            model_details=model_details,
            model_details_count=model_details_count,
            model_details_keys=model_details_keys,
            model_details_names=model_details_names,
            classes=class_list,
            class_count=len(class_list),
            shapes=shape_list,
            shape_count=len(shape_list),
            properties=prop_list,
            property_count=len(prop_list),
            instance_count=instance_count,
            instances=instances,
            instance_classes=instance_classes,
        )
        content += self.env.get_template("render_diagram.html").render(
            url = base_url,
            element = s, 
            diagram = self.diagram_renderer.render_model(s.iri)
        )        
        return self.render_page(base_url, content)

    def render_model_element(self, base_url: str, iri: str) -> str:
        log.info("HTML rendering model element at {}".format(iri))
        s = SemanticModel(iri)
        content = ""
        for t in s.get_types_of_instance(iri):
            if t == s.RDFS_CLASS or t == s.OWL_CLASS:
                content += self.render_class(base_url, s)
            elif t == s.RDFS_PROPERTY or t == s.RDF_PROPERTY:
                content += self.render_property(base_url, s)
            elif t == s.SHACL_NODESHAPE:
                content += self.render_nodeshape(base_url, s)
            elif t == s.SHACL_PROPERTY:
                content += self.render_shacl_property(base_url, s)
            elif s.is_instance(iri):
                content += self.render_instance(base_url, s)
        if content == "" or content is None:
            msg = "Cannot render HTML for {} (element not found, or type of element could not be determined)".format(
                iri
            )
            log.error(msg)
            raise NotFoundException(msg)
        log.info("HTML rendering full page for model element at {}".format(iri))
        content += self.render_predicates(SemanticModelElement(iri))
        return self.render_page(base_url, content)

    def render_class(self, base_url: str, model: SemanticModel) -> str:
        log.info("HTML rendering class at {}".format(model.iri))
        for c in model.get_classes():
            if c.iri == model.iri:
                prop_types = {}
                for p in c.get_properties():
                    prop_types[p.iri] = []
                    for t in p.get_property_type():
                        prop_types[p.iri].append(t)
                instances = c.get_instances()
                instance_count = len(instances)
                content = self.env.get_template("render_class.html").render(
                    url=base_url,
                    model=model,
                    model_iri=c.iri[0 : c.iri.rfind("/")],
                    the_class=c,
                    types=c.get_types(),
                    properties=c.get_properties(),
                    prop_count=len(c.get_properties()),
                    prop_types=prop_types,
                    superclasses=c.get_superclasses(),
                    shapes=c.get_nodeshapes(),
                    instances=instances,
                    instance_count=instance_count,
                )
                diagram = self.env.get_template("render_diagram.html").render(
                    url = base_url,
                    element = c, 
                    diagram = self.diagram_renderer.render_class(c.iri)
                )
                return content + diagram
                
    def render_predicates(self, element:SemanticModelElement) -> str:
        log.info("HTML rendering predicates for {}".format(element.iri))
        return self.env.get_template("render_predicates.html").render(
            element=element,
            predicates=element.get_predicates(),
        )

    def render_instance(self, base_url: str, model: SemanticModel) -> str:
        log.info("HTML rendering instance at {}".format(model.iri))
        for i in model.get_instances():
            if i.iri == model.iri:
                return self.env.get_template("render_instance.html").render(
                    url=base_url,
                    model_iri=i.iri[0 : i.iri.rfind("/")],
                    instance=i,
                    classes=i.get_classes(),
                )

    def render_property(self, base_url: str, model: SemanticModel) -> str:
        log.info("HTML rendering property at {}".format(model.iri))
        for p in model.get_properties():
            if p.iri == model.iri:
                shacl_props = p.get_shacl_properties()
                prop_shapes = {}
                prop_constraints = {}
                for sp in shacl_props:
                    prop_shapes[sp.iri] = list(
                        map(lambda n: n.iri, sp.get_nodeshapes())
                    )
                    prop_constraints[sp.iri] = sp.get_constraints()
                return self.env.get_template("render_property.html").render(
                    url=base_url,
                    model=model,
                    model_iri=p.iri[0 : p.iri.rfind("/")],
                    property=p,
                    types=p.get_types(),
                    classes=p.get_classes(),
                    prop_type=p.get_property_type(),
                    superprop=p.get_superproperties(),
                    shacl_props=shacl_props,
                    shacl_prop_count=len(shacl_props),
                    shacl_prop_shapes=prop_shapes,
                    shacl_prop_constraints=prop_constraints,
                )

    def render_nodeshape(self, base_url: str, model: SemanticModel) -> str:
        log.info("HTML rendering nodeshape at {}".format(model.iri))
        for n in model.get_node_shapes():
            if n.iri == model.iri:
                shacl_props = n.get_shacl_properties()
                prop_shapes = {}
                prop_constraints = {}
                for sp in shacl_props:
                    prop_shapes[sp.iri] = list(
                        map(lambda n: n.iri, sp.get_nodeshapes())
                    )
                    prop_constraints[sp.iri] = sp.get_constraints()
                content = self.env.get_template("render_shape.html").render(
                    url=base_url,
                    model=model,
                    model_iri=n.iri[0 : n.iri.rfind("/")],
                    shape=n,
                    types=n.get_types(),
                    classes=n.get_classes(),
                    shacl_props=shacl_props,
                    shacl_prop_count=len(shacl_props),
                    shacl_prop_shapes=prop_shapes,
                    shacl_prop_constraints=prop_constraints,
                )
                diagram = self.env.get_template("render_diagram.html").render(
                    url = base_url,
                    element = n, 
                    diagram = self.diagram_renderer.render_nodeshape(n.iri)
                )
                return content + diagram
                

    def render_shacl_property(self, base_url: str, model: SemanticModel) -> str:
        log.info("HTML rendering SHACL property at {}".format(model.iri))
        shacl_props = model.get_shacl_properties()
        for sp in shacl_props:
            if sp.iri == model.iri:
                prop_shapes = sp.get_nodeshapes()
                prop_constraints = sp.get_constraints()
                constraint_count = len(prop_constraints)
                return self.env.get_template("render_shacl_property.html").render(
                    url=base_url,
                    model=model,
                    model_iri=sp.iri[0 : sp.iri.rfind("/")],
                    property=sp,
                    types=sp.get_types(),
                    shapes=prop_shapes,
                    constraints=prop_constraints,
                    constraint_count=constraint_count
                )
