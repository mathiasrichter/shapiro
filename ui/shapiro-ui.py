import streamlit as st
from multipage import MultiPage
from pages import start, config, view_schema_json, element_browser, view_schema_graph, schema_editor

if 'SERVER' not in st.session_state:
    st.session_state['SERVER'] = 'http://localhost:8000/'

app = MultiPage('Shapiro UI')

app.add_page(start.StartPage())
app.add_page(view_schema_json.ViewSchemaJson())
app.add_page(schema_editor.SchemaEditor())
app.add_page(view_schema_graph.ViewSchemaGraph())
app.add_page(element_browser.ElementBrowser())
app.add_page(config.ConfigPage())

app.run()
