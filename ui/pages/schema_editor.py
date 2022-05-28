import streamlit as st
from multipage import Page
import util as util
from streamlit_ace import st_ace, LANGUAGES, THEMES
import json

class SchemaEditor(Page):

    def title(self):
        return "Schema Editor"

    def run(self):
        st.title("Schema Editor")
        try:
            names = util.get(st.session_state['SERVER'] + 'schemas')
        except Exception as x:
            st.error("Could not load schemas from server: {}".format(x))
        schema_name = st.selectbox('Schema', names, index=1)
        schema = util.get(st.session_state['SERVER'] + schema_name)
        schema = json.dumps(schema, indent=4)
        code = st_ace(value=schema, language='json', theme=THEMES[35],
                        wrap=True, font_size=12, auto_update=False)
        if code != schema:
            try:
                json.loads(code)
                util.put(st.session_state['SERVER'] + schema_name, code)
                st.success("Saved schema {}.".format(schema_name))
            except Exception as x:
                st.error("Could not save schema {} to server: {}".format(schema_name, x))
        else:
            st.info('No edits to save.')
