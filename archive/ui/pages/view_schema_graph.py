import streamlit as st
from ui.multipage import Page
import util
from rdflib import Graph
from streamlit_agraph import Node, Edge, Config, agraph

class ViewSchemaGraph(Page):

    def title(self):
        return "View Schema Graph"

    def prep_graph(self, schema_name, context):
        config = Config(width=750,
                        height=500,
                        directed=True,
                        nodeHighlightBehavior=True,
                        highlightColor="#F7A7A6",
                        collapsible=True,
                        node={'labelProperty':'label'},
                        link={'labelProperty': 'label', 'renderLabel': True}
                        )
        nodes = []
        edges = []
        graph = Graph()
        graph.parse(st.session_state['CONFIG'].getServer() + schema_name, format='application/ld+json')
        for s, p, o in graph:
            s_id = str(s)
            s_label = util.compact(context, s_id)
            o_id = str(o)
            o_label = util.compact(context, o_id)
            p_id = str(p)
            p_label = util.compact(context, p_id)
            nodes.append(Node(id=s_id, label=s_label))
            nodes.append(Node(id=o_id, label=o_label))
            edges.append(Edge(source=s_id, label=p_label, target=o_id, type="CURVE_SMOOTH"))
        return agraph(nodes=nodes, edges=edges, config=config)

    def run(self):
        st.title("View Schema Graph")
        try:
            names = util.get(st.session_state['CONFIG'].getServer() + 'schemas')
            schema_name = st.selectbox('Available Schemas', names, index=1)
            context = util.get(st.session_state['CONFIG'].getServer() + schema_name + "/context/")
            self.prep_graph(schema_name, context)
        except Exception as x:
                st.error('Could not retrieve schema names from Shapiro Server: {}'.format(x))
