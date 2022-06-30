import networkx as nx
from enum import Enum
import requests
import util
import typing

class PropertyType(Enum):
    """
    Enum for the types properties can take.
    """

    INT = 1
    FLOAT = 2
    STRING = 3
    DATE = 4
    TIME = 5
    DATETIME = 6
    BOOL = 7

class Cardinality(Enum):
    """
    Enum for the cardinalities of relationships.
    """

    ONE = 1
    ZERO_TO_ONE = 2
    ONE_TO_MANY = 3
    ZERO_TO_MANY = 4

    def __str__(self):
        if self == self.ONE:
            return "1"
        if self == self.ZERO_TO_ONE:
            return "0..1"
        if self == self.ONE_TO_MANY:
            return "1..*"
        if self == self.ZERO_TO_MANY:
            return "0..*"

class ModelBase:
    """
    Base class for all elements of a model (entities, properties, different types of relationships).
    Ensures all of them have a name and a description and a readable string representation.
    """

    def __init__(self, name:str, description:str):
        self.name = name
        self.description = description

    def __str__(self):
        return '{}@{}({})'.format(self.name, util.classname(type(self)), hash(self))

class ModelNode(ModelBase):
    """
    Base class for all nodes of a model graph (entities, properties, constraints). Ensures they have a reference
    to the model to which they belong.
    """

    def __init__(self, model:'Model', name:str, description:str):
        self.model = model
        self.name = name
        self.description = description


class ValidationConstraint(ModelNode):
    """
    Base class for all validation constraints.
    """

    def __init__(self, model:'Model', name:str, description:str):
        super().__init__(model, name, description)

class ValueMandatoryConstraint(ValidationConstraint):
    """
    Expresses that a property value must be present.
    """
    pass

class StringLengthConstraint(ValidationConstraint):
    """
    Expresses a min and/or a max value for the string length. To express just a min or just a max, specify the other
    value as None.
    """
    def __init__(self, model:'Model', name:str, description:str, min_length:int, max_length:int):
        super().__init__(model, name, description)
        self.min_length = min_length
        self.max_length = max_length

class StringPatternConstraint(ValidationConstraint):
    """
    Expresses a regexp constraint for the string length.
    """
    def __init__(self, model:'Model', name:str, description:str, regex:str):
        super().__init__(model, name, description)
        self.regex = regex

class RangeConstraint(ValidationConstraint):
    """
    Expresses a min and/or a max value for the numeric range of an integer or a decimal. To express just a min or just a max, specify the other
    value as None. The min/max values can be int or float depending on the type of the property the constraint is for.
    """
    def __init__(self, model:'Model', name:str, description:str, min, max):
        super().__init__(model, name, description)
        self.min = min
        self.max = max

class ModelEdge(ModelBase):
    """
    Base class for all edges of a the model graph (relationships, inheritance, has-constraint). Ensures that
    edges know their source node and their target node.
    """

    def __init__(self, name:str, description:str, source:ModelNode, target:ModelNode):
        super().__init__(name, description)
        self.source = source
        self.target = target

class UnnamedEdge(ModelEdge):
    """
    Base class for edges without a name and a description.
    """

    def __init__(self, source:ModelNode, target:ModelNode):
        super().__init__(None, None, source, target)

    def __str__(self):
        return util.classname(type(self))

class HasProperty(UnnamedEdge):
    """
    An edge between an entity node and a property node expressing that an entity has a property.
    """
    pass

class HasInheritedProperty(HasProperty):
    """
    An edge between an entity node and a property node expressing that an entity has a property
    by way of inheritance.
    """
    pass

class IsA(UnnamedEdge):
    """
    An edge expressing the inheritance relationship between two entities.
    """
    pass

class HasConstraint(UnnamedEdge):
    """
    An edge expressing that a property has a constraint.
    """
    pass

class RelatedTo(ModelEdge):
    """
    An edge expressing a named relationship between two entities.
    """

    def __init__(self, name:str, description:str, source:ModelNode, target:ModelNode, cardinality:Cardinality):
        super().__init__(name, description, source, target)
        self.cardinality = cardinality

    def __str__(self):
        return super().__str__() + " " + str(self.cardinality)

class InheritedRelatedTo(RelatedTo):
    """
    An edge between an entity node and another node expressing that an entity
    has in inherited relationship to another entity.
    """
    pass

class Property(ModelNode):
    """
    A property with a value and potential constraints that can be associated with an entity.
    """

    def __init__(self, model:'Model', name:str, description:str, type:PropertyType):
        super().__init__(model, name, description)
        self.type = type

    def set_mandatory(self, mandatory:bool) -> 'Property':
        """
        Express whether or not the property must have a value in any compliant
        instance of this model.
        """
        self.model.set_mandatory(self, mandatory)
        return self

    def is_mandatory(self) -> bool:
        """
        Return whether or not this property must have a value in any
        compliant instance of this model.
        """
        return self.model.is_mandatory(self)

    def set_min_length(self, min:int) -> 'Property':
        """
        Set the min string length of this property, if it is of type string.
        If it is not, an exception will be raised.
        Set to None to remove any min string length constraint.
        """
        self.model.set_min_length(self, min)
        return self

    def get_min_length(self):
        """
        Return the min string length or None, if no constraint is present.
        """
        return self.model.get_min_length(self)

    def set_max_length(self, max) -> 'Property':
        """
        Set the max string length of this property, if it is of type string.
        If it is not, an exception will be raised.
        Set to None to remove any max string length constraint.
        """
        self.model.set_max_length(self, max)
        return self

    def get_max_length(self):
        """
        Return the max string length or None, if no constraint is present.
        """
        return self.model.get_max_length(self)

    def set_string_pattern(self, pattern:str) -> 'Property':
        """
        Set a regexp constraint on this property, if it is of type string.
        If it is not, an exception will be raised.
        """
        self.model.set_string_pattern(self, pattern)
        return self

    def get_string_pattern(self) -> str:
        """
        Get the regexp pattern constraint for this property or None, if it is not set.
        """
        return self.model.get_string_pattern(self)

    def set_min_range(self, min) -> 'Property':
        """
        Set the min range of this property, if it is of type int or float.
        If it is not, an exception is raised.
        Set to None to remove any min range constraint.
        """
        self.model.set_min_range(self, min)
        return self

    def get_min_range(self):
        """
        Get the min range constraint for this property or None.
        """
        return self.model.get_min_range(self)

    def set_max_range(self, max) -> 'Property':
        """
        Set the max range of this property, if it is of type int or float.
        If it is not, an exception is raised.
        Set to None to remove any max range constraint.
        """
        self.model.set_max_range(self, max)
        return self

    def get_max_range(self):
        """
        Get the max range constraint for this property or None.
        """
        return self.model.get_max_range(self)

class Entity(ModelNode):
    """
    An entity with potential properties, relationships to other entities or inheritance relationships.
    """

    def __init__(self, model:'Model', name:str, description:str):
        super().__init__(model, name, description)

    def property(self, property:Property) -> 'Entity':
        """
        Link this entity to having the specified property.
        """
        self.model.add_property(self, property)
        return self

    def relate_zero_to_many(self, target:'Entity', relationship_name:str, relationship_description:str) -> 'Entity':
        """
        Relate this entity to zero or more of the specified target entity.
        """
        self.model.relate_zero_to_many(self, target, relationship_name, relationship_description)
        return self

    def relate_one_to_many(self, target:'Entity', relationship_name:str, relationship_description:str) -> 'Entity':
        """
        Relate this entity to one or more of the specified target entity.
        """
        self.model.relate_one_to_many(self, target, relationship_name, relationship_description)
        return self

    def relate_one(self, target:'Entity', relationship_name:str, relationship_description:str) -> 'Entity':
        """
        Relate this entity to one specified target entity.
        """
        self.model.relate_one_to_many(self, target, relationship_name, relationship_description)
        return self

    def relate_zero_to_one(self, target:'Entity', relationship_name:str, relationship_description:str) -> 'Entity':
        """
        Relate this entity to zero or one of the specified target entity.
        """
        self.model.relate_zero_to_one(self, target, relationship_name, relationship_description)
        return self

    def is_a(self, super_entity:'Entity') -> 'Entity':
        """
        Create an inheritance relationship between this entity and the specified super entity.
        Will raise an exception if the resulting inheritance relationship is circular.
        """
        self.model.is_a(self, super_entity)
        return self

    def get_relationships(self) -> list[RelatedTo]:
        return self.model.get_relationships_from(self)

    def get_relationship(self, name:str) -> RelatedTo:
        return self.model.get_relationship_from(self, name)

    def properties(self) -> list[Property]:
        return self.model.get_properties_of(self)

    def get_property(self, name:str) -> Property:
        return self.model.get_property_of(self, name)

    def inherit_properties_from(self, super_entity:'Entity', property_names:list[str]) -> 'Entity':
        self.model.inherit_properties_from(self, super_entity, property_names)
        return self

    def inherit_all_properties_from(self, super_entity:'Entity') -> 'Entity':
        self.model.inherit_all_properties_from(self, super_entity)
        return self

    def inherit_relationships_from(self, super_entity:'Entity', relationship_names:list[str]) -> 'Entity':
        self.model.inherit_relationships_from(self, super_entity, relationship_names)
        return self

    def inherit_all_relationships_from(self, super_entity:'Entity') -> 'Entity':
        self.model.inherit_all_relationships_from(self, super_entity)
        return self

    def get_superclasses(self, recursive = False) -> list['Entity']:
        return self.model.get_superclasses(self, recursive)

class EntityRef(Entity):

    def __init__(self, model:'Model', name:str, url:str, url_alias:str):
        util.resolve(url+name)
        super().__init__(model, name, 'References entity '+name+' at '+url)
        self.url = url
        self.alias = url_alias

class PropertyRef(Property):

    def __init__(self, model:'Model', name:str, url:str, url_alias:str, type:PropertyType):
        util.resolve(url+name)
        super().__init__(model, name, 'References property '+name+' at '+url, type)
        self.url = url
        self.alias = url_alias

class Model(ModelBase):

    def __init__(self, name:str, description:str):
        super().__init__(name, description)
        self.graph = nx.MultiDiGraph()

    def __get_node(self, name:str, node_type:type):
        result = list(filter(lambda x: (type(x)==node_type and x.name==name), self.graph.nodes()))
        if len(result) == 1:
            return result[0]
        else:
            return None

    def __nodes(self, node_type:type) -> list[ModelNode]:
        return list(filter(lambda x: type(x)==node_type, self.graph.nodes()))

    def get_all_edges(self):
        return list(map(lambda x: self.__get_edge_object(x), self.graph.edges()))

    def __get_edges(self, edge_type:type) -> list[ModelEdge]:
        result = filter(lambda x: isinstance(self.__get_edge_object(x), edge_type), self.graph.edges())
        return list(map(lambda x: self.__get_edge_object(x), result))

    def __get_edge(self, source:ModelNode, target:ModelNode, edge_type:type) -> ModelEdge:
        result = list(filter(lambda x: x[1] == target and isinstance(self.__get_edge_object(x), edge_type), self.graph.out_edges(source)))
        if len(result) == 1:
            return self.__get_edge_object(x)
        else:
            return None

    def __get_edges_from(self, source:ModelNode, edge_type:type) -> list[ModelEdge]:
        result = filter(lambda x: isinstance(self.__get_edge_object(x), edge_type), self.graph.out_edges(source))
        return list(map(lambda x: self.__get_edge_object(x), result))

    def __get_edges_to(self, target:ModelNode, edge_type:type) -> list[ModelEdge]:
        result = filter(lambda x: isinstance(self.__get_edge_object(x), edge_type), self.graph.in_edges(target))
        return list(map(lambda x: self.__get_edge_object(x), result))

    def __successor(self, source:ModelNode, name:str, successor_node_type:type) -> ModelNode:
        result = list(filter(lambda x: (type(x)==successor_node_type and x.name==name), self.graph.successors(source)))
        if len(result) == 1:
            return result[0]
        else:
            return None

    def __successors(self, source:ModelNode, successor_node_type:type) -> list[ModelNode]:
        return list(filter(lambda x: (type(x)==successor_node_type), self.graph.successors(source)))

    def __predecessor(self, target:ModelNode, name:str, predecessor_node_type:type) -> ModelNode:
        result = list(filter(lambda x: (type(x)==predecessor_node_type and x.name==name), self.graph.predecessors(target)))
        if len(result) == 1:
            return result[0]
        else:
            return None

    def __predecessors(self, target:ModelNode, predecessor_node_type:type) -> list[ModelNode]:
        return list(filter(lambda x: (type(x)==predecessor_node_type), self.graph.predecessors(target)))

    def __get_edge_object(self, edge:tuple) -> ModelEdge:
        d = self.graph.get_edge_data(edge[0], edge[1])
        if len(d) == 1:
            if 'edge_type' in d[0]:
                return d[0]['edge_type']
        return None

    def entity(self, name:str, description:str) -> Entity:
        e = Entity(self, name, description)
        self.graph.add_node(e)
        return e

    def entity_ref(self, name:str, url:str, alias:str) -> EntityRef:
        e = EntityRef(self, name, url, alias)
        self.graph.add_node(e)
        return e

    def property(self, name:str, description:str, property_type:PropertyType) -> Property:
        p = Property(self, name, description, property_type)
        self.graph.add_node(p)
        return p

    def property_ref(self, name:str, url:str, alias:str, type:PropertyType) -> PropertyRef:
        p = PropertyRef(self, name, url, alias, type)
        self.graph.add_node(p)
        return p

    def add_property(self, entity:Entity, property: Property) -> 'Model':
        if property not in self.get_properties_of(entity):
            self.graph.add_edge(entity, property, edge_type=HasProperty(entity, property))
        return self

    def get_property(self, name:str) -> Property:
        return self.__get_node(name, Property)

    def get_properties(self) -> list[Property]:
        return self.__nodes(Property)

    def get_property_refs(self) -> list[PropertyRef]:
        return self.__nodes(PropertyRef)

    def get_properties_of(self, entity:Entity) -> list[Property]:
        return list(map(lambda x: x.target, self.__get_edges_from(entity, HasProperty)))

    def get_property_of(self, entity:Entity, name:str) -> Property:
        result = list(filter(lambda x: x.name == name, self.get_properties_of(entity)))
        if len(result) == 1:
            return result[0]
        else:
            return None

    def get_entity(self, name:str) -> Entity:
        return self.__get_node(name, Entity)

    def get_entities(self) -> list[Entity]:
        return self.__nodes(Entity)

    def get_entity_refs(self) -> list[EntityRef]:
        return self.__nodes(EntityRef)

    def get_entities_having(self, property: Property) -> list[Entity]:
        return list(map(lambda x: x.source, self.__get_edges_to(property, HasProperty)))

    def get_relationships(self) -> list[RelatedTo]:
        return self.__get_edges(RelatedTo)

    def get_relationships_from(self, source:Entity) -> list[RelatedTo]:
        return self.__get_edges_from(source, RelatedTo)

    def get_relationship_from(self, entity:Entity, name:str)-> RelatedTo:
        result = list(filter(lambda x: x.name == name, self.get_relationships_from(entity)))
        if len(result) == 1:
            return result[0]
        else:
            return None

    def get_relationships_to(self, target:ModelNode)-> list[RelatedTo]:
        return self.__get_edges_to(target, RelatedTo)

    def get_constraints(self, property:Property)-> list[ValidationConstraint]:
        return self.__get_successors(property, ValidationConstraint)

    def get_constraint(self, property:Property, constraint_type:type) -> ValidationConstraint:
        return self.__get_successors(property, constraint_type)

    def get_superclasses(self, entity:Entity, recursive = False) -> list[Entity]:
        result = list(map(lambda x: x.target, self.__get_edges_from(entity, IsA)))
        if len(result) > 0 and recursive is True:
            for c in result:
                result = result + self.get_superclasses(c, recursive)
        return result

    def get_subclasses(self, entity:Entity, recursive = False) -> list[Entity]:
        result = list(map(lambda x: x.source, self.__get_edges_to(entity, IsA)))
        if len(result) > 0 and recursive is True:
            for c in result:
                result = result + self.get_subclasses(c, recursive)
        return result

    def set_mandatory(self, property:Property, mandatory:bool) -> 'Model':
        c = self.get_constraint(property, ValueMandatoryConstraint)
        if mandatory is False and c is not None:
            self.graph.remove_edge(property, c)
            self.graph.remove_node(c)
        elif mandatory is True and c is None:
            c = ValueMandatoryConstraint(self, property.name, "A value is mandatory for property '"+property.name+"'")
            self.model.add_edge(property, c, edge_type=HasConstraint(self, property, c))
        return self

    def is_mandatory(self, property:Property)  -> bool:
        return self.get_constraint(property, ValueMandatoryConstraint) is not None

    def set_min_length(self, property:Property, min:int) -> 'Model':
        if property.type != PropertyType.STRING:
            raise Exception("Property must have type STRING for a string length constraint.")
        c = self.get_constraint(property, StringLengthConstraint)
        if c is not None and min is not None and c.max_length is not None and min > c.max_length:
            raise Exception("Min length cannot be greater than max length.")
        if c is not None and min is None and c.max_length is None:
            self.graph.remove_node(c)
            return self
        desc = None
        if c is not None:
            if min is not None and c.max_length is None:
                desc = "String length must be at least {}.".format(min)
            elif min is not None and c.max_length is not None:
                desc = "String length must be between {} and {}".format(min, c.max_length)
            elif min is None and c.max_length is not None:
                desc = "String length must be at most {}.".format(c.max_length)
            c.min_length = min
            c.description = desc
        else:
            c = StringLengthConstraint(self, property.name, desc, min, None)
            self.graph.add_edge(property, c, edge_type=HasConstraint(self, property, c))
        return self

    def get_min_length(self, property:Property) -> int:
        c = self.__get_constraint(property, StringLengthConstraint)
        if c is not None:
            return c.min_length
        else:
            return None

    def set_max_length(self, property:Property, max:int) -> 'Model':
        if property.type != PropertyType.STRING:
            raise Exception("Property must have type STRING for a string length constraint.")
        c = self.__get_constraint(property, StringLengthConstraint)
        if c is not None and c.min_length is not None and max is not None and c.min_length > max:
            raise Exception("Min length cannot be greater than max length.")
        if c is not None and c.min_length is None and max is None:
            self.graph.remove_node(c)
            return self
        desc = None
        if c is not None:
            if c.min_length is not None and max is None:
                desc = "String length must be at least {}.".format(c.min_length)
            elif c.min_length is not None and max is not None:
                desc = "String length must be between {} and {}".format(c.min_length, max)
            elif c.min_length is None and max is not None:
                desc = "String length must be at most {}.".format(max)
            c.max_length = max
            c.description = desc
        else:
            c = StringLengthConstraint(self.model, self.name, desc, None, max)
            self.graph.add_edge(property, c, edge_type=HasConstraint(self, property, c))
        return self

    def get_max_length(self, property:Property) -> int:
        c = self.__get_constraint(property, StringLengthConstraint)
        if c is not None:
            return c.max_length
        else:
            return None

    def set_string_pattern(self, property:Property, pattern:str) -> 'Model':
        if property.type != PropertyType.STRING:
            raise Exception("Property must have type STRING for a string pattern constraint.")
        c = self.__get_constraint(property, StringPatternConstraint)
        if c is None and pattern is not None:
            newconstraint = StringPatternConstraint(self.model, self.name, "The string must match this pattern.", pattern)
            self.graph.add_edge(property, newconstraint, edge_type=HasConstraint(self, property, newconstraint))
        if c is not None:
            if pattern is None:
                self.graph.remove_node(c)
            else:
                c.regex = pattern
        return self

    def get_string_pattern(self, property:Property) -> str:
        c = self.__get_constraint(property, StringPatternConstraint)
        if c is not None:
            return c.regex
        else:
            return None

    def set_min_range(self, property:Property, min) -> 'Model':
        if (property.type != PropertyType.INT and type(min) == int):
            raise Exception("Property must have type INT for a INT range constraint.")
        if (property.type != PropertyType.FLOAT and type(min) == float):
            raise Exception("Property must have type FLOAT for a FLOAT range constraint.")
        c = self.__get_constraint(property, RangeConstraint)
        if c is not None and min is not None and c.max is not None and min > c.max:
            raise Exception("Min range cannot be greater than max range.")
        if c is not None and min is None and c.max is None:
            self.graph.remove_node(c)
            return self
        desc = None
        if c is not None:
            if min is not None and c.max is None:
                desc = "Value must be at least {}.".format(min)
            elif min is not None and c.max is not None:
                desc = "Value must be between {} and {}".format(min, c.max)
            elif min is None and c.max is not None:
                desc = "Value must be at most {}.".format(c.max)
            c.min = min
            c.description = desc
        else:
            c = RangeConstraint(self.model, property.name, desc, min, None)
            self.graph.add_edge(property, c, edge_type=HasConstraint(self, property, c))
        return self

    def get_min_range(self, property:Property):
        c = self.__get_constraint(property, RangeConstraint)
        if c is not None:
            return c.min
        else:
            return None

    def set_max_range(self, property:Property, max) -> 'Model':
        if (property.type != PropertyType.INT and type(max) == int):
            raise Exception("Property must have type INT for a INT range constraint.")
        if (property.type != PropertyType.FLOAT and type(max) == float):
            raise Exception("Property must have type FLOAT for a FLOAT range constraint.")
        c = self.__get_constraint(property, RangeConstraint)
        if c is not None and c.min is not None and max is not None and c.min > max:
            raise Exception("Min range cannot be greater than max range.")
        if c is not None and c.min is None and max is None:
            self.graph.remove_node(c)
            return self
        desc = None
        if c is not None:
            if c.min is not None and max is None:
                desc = "Value must be at least {}.".format(c.min)
            elif c.min is not None and max is not None:
                desc = "Value must be between {} and {}".format(c.min, max)
            elif c.min is None and max is not None:
                desc = "Value must be at most {}.".format(max)
            c.max = max
            c.description = desc
        else:
            c = RangeConstraint(self.model, self.name, desc, None, max)
            self.model.add_edge(self, c, edge_type=HasConstraint(self, property, c))
        return self

    def get_max_range(self, property:Property):
        c = self.__get_constraint(property, RangeConstraint)
        if c is not None:
            return c.max
        else:
            return None

    def __relate(self, source:Entity, target:Entity, relationship_name:str, relationship_description:str, cardinality: Cardinality):
        self.graph.add_edge(source, target, edge_type=RelatedTo(relationship_name, relationship_description, source, target, cardinality))

    def relate_zero_to_many(self, source:Entity, target:Entity, relationship_name:str, relationship_description:str) -> 'Model':
        self.__relate(source, target, relationship_name, relationship_description, Cardinality.ZERO_TO_MANY)
        return self

    def relate_one_to_many(self, source:Entity, target:Entity, relationship_name:str, relationship_description:str) -> 'Model':
        self.__relate(source, target, relationship_name, relationship_description, Cardinality.ONE_TO_MANY)
        return self

    def relate_one(self, source:Entity, target:Entity, relationship_name:str, relationship_description:str) -> 'Model':
        self.__relate(source, target, relationship_name, relationship_description, Cardinality.ONE)
        return self

    def relate_zero_to_one(self, source:Entity, target:Entity, relationship_name:str, relationship_description:str) -> 'Model':
        self.__relate(source, target, relationship_name, relationship_description, Cardinality.ZERO_TO_ONE)
        return self

    def is_a(self, sub_entity:Entity, super_entity:Entity) -> 'Model':
        superclasses = self.get_superclasses(sub_entity, True)
        if super_entity not in superclasses:
            superclasses = superclasses + self.get_superclasses(super_entity, True)
        if sub_entity in superclasses or sub_entity == super_entity:
            raise Exception("Circular inheritance relationship is not allowed.")
        if super_entity not in superclasses:
            self.graph.add_edge(sub_entity, super_entity, edge_type=IsA(sub_entity, super_entity))
        return self

    def inherit_properties_from(self, sub_entity:Entity, super_entity:Entity, property_names:list[str]) -> 'Model':
        self.is_a(sub_entity, super_entity)
        for n in property_names:
            p = super_entity.get_property(n)
            if p is None:
                raise Exception("Property '{}' does not exist in entity '{}'".format(n, super_entity.name))
            if self.__get_egde(sub_entity, p, HasProperty) is None:
                self.graph.add_edge(sub_entity, p, edge_type=HasInheritedProperty(sub_entity, p))
        return self

    def inherit_all_properties_from(self, sub_entity:Entity, super_entity:Entity) -> 'Model':
        self.is_a(super_entity)
        for p in super_entity.get_properties():
            if self.__get_egde(sub_entity, p, HasProperty) is None:
                self.graph.add_edge(sub_entity, p, edge_type=HasInheritedProperty(self, sub_entity, p))
        return self

    def inherit_relationships_from(self, sub_entity:Entity, super_entity:Entity, relationship_names:list[str]) -> 'Model':
        self.is_a(sub_entity, super_entity)
        for n in relationship_names:
            r = self.get_relationship_from(super_entity, n)
            if r is None:
                raise Exception("Relationship '{}' does not exist in entity '{}'".format(n, super_entity.name))
            if self.get_relationship_from(sub_entity, n) is None:
                self.graph.add_edge(sub_entity, r.target, edge_type=InheritedRelatedTo(r.name, r.description, sub_entity, r.target, r.cardinality))
        return self

    def inherit_all_relationships_from(self, sub_entity:Entity, super_entity:Entity) -> 'Model':
        self.is_a(super_entity)
        for r in super_entity.get_relationships():
            if self.__get_relationship_from(sub_entity, n) is None:
                self.graph.add_edge(sub_entity, r.target, edge_type=InheritedRelatedTo(r.name, r.description, sub_entity, r.target, r.cardinality))
        return self
