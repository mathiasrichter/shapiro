import streamlit as st
from multipage import Page
import util as util
import pandas as pd
import json
import validators
from rdflib import Graph
from streamlit_agraph import Node, Edge, Config, agraph

class VisualizeElement:
    """Helper class to visualize the element's details as HTML such that
       it can be rendered through st.write (by way of the __repr_htlm_ method)"""

    def __init__(self, context, element, compact):
        """Construct this class to visualize the specified element
           within the specified contesxt. If compact is True, attribute
           names will be visualized without binding.
        """
        self.context = context
        self.element = element
        self.compact = compact

    def attr_html(self, key, value):
        """Create HTML for the specified key and value."""
        result = '<td>{}</td><td>{}</td>'
        if type(value) == dict:
            agg = '<table>'
            agg += self.elem_html(value)
            agg += '</table>'
            result = result.format(util.uri_link(self.context, key, self.compact), agg )
        elif type(value) == list:
            agg = '<table>'
            for e in value:
                agg += self.elem_html(e)
            agg += '</table>'
            result = result.format(util.uri_link(self.context, key, self.compact), agg)
        else:
            if validators.url(value):
                result = result.format(util.uri_link(self.context, key, self.compact), '<a href="{}">{}</a>'.format(value, value))
            else:
                result = result.format(util.uri_link(self.context, key, self.compact), value)
        return result

    def elem_html(self, element):
        """Return the HTML rendering for this element."""
        html = "<tr>"
        for k in element.keys():
            html += self.attr_html(k, element[k])
            html += "</tr>\n"
        return html

    def _repr_html_(self):
        """Return the HTML rendering for this element."""
        result = self.elem_html(self.element)
        return result


class ElementBrowser(Page):

    def title(self):
        return "Schema Element Browser"

    def prep_data(self, schema_name, type=None):
        self.elem_by_id = {}
        self.elements = []
        self.context = util.get(st.session_state['SERVER'] + schema_name + "/context/")
        for elem in util.get(st.session_state['SERVER'] + schema_name + "/elements/"):
            if type is None or elem['@type'] == type:
                self.elem_by_id[elem['@id']] = elem
                self.elements.append(elem)

    def prep_graph(self, schema_name, element_id):
        config = Config(width=750,
                        height=500,
                        directed=True,
                        nodeHighlightBehavior=True,
                        highlightColor="#F7A7A6", # or "blue"
                        collapsible=True,
                        node={'labelProperty':'label'},
                        link={'labelProperty': 'label', 'renderLabel': True}
                        # **kwargs e.g. node_size=1000 or node_color="blue"
                        )
        nodes = []
        edges = []
        graph = Graph()
        graph.parse(st.session_state['SERVER'] + schema_name, format='application/ld+json')
        for s, p, o in graph:
            s_id = str(s)
            s_label = util.compact(self.context, s_id)
            o_id = str(o)
            o_label = util.compact(self.context, o_id)
            p_id = str(p)
            p_label = util.compact(self.context, p_id)
            if s_label == element_id or p_label == element_id or o_label == element_id:
                nodes.append(Node(id=s_id, label=s_label))
                nodes.append(Node(id=o_id, label=o_label))
                edges.append(Edge(source=s_id, label=p_label, target=o_id, type="CURVE_SMOOTH"))
        return agraph(nodes=nodes, edges=edges, config=config)

    def elem_types(self):
        types = list(map(lambda e: e['@type'], self.elements))
        return list(set(types))

    def elem_ids(self):
        return self.elem_by_id.keys()

    def element(self, id):
        return self.elem_by_id[id]

    def run(self):
        st.title("Schema Element Browser")
        names = util.get(st.session_state['SERVER'] + 'schemas')
        compact = st.checkbox('Compact attribute names', True)
        col1, col2, col3 = st.columns(3)
        with col1:
            schema_name = st.selectbox('Schema', names, index=1)
            self.prep_data(schema_name)
        with col2:
            element_type = st.selectbox('Element Type', self.elem_types())
            self.prep_data(schema_name, element_type)
        with col3:
            element_id = st.selectbox('Element', self.elem_ids())
        with st.expander("Context Details", False):
            st.write(VisualizeElement(self.context, self.context, compact))
        with st.expander("Element Details", True):
            st.write(VisualizeElement(self.context, self.element(element_id), compact))
        with st.expander("Element Source", False):
            st.json(json.dumps(self.element(element_id)))
        with st.expander("Element Graph", False):
            self.prep_graph(schema_name, element_id)
