import streamlit as st
from multipage import Page
import util as util
import json

class ViewSchemaJson(Page):

    def title(self):
        return "View Schema Source"

    def run(self):
        st.title("View Schema Source")
        try:
            names = util.get(st.session_state['SERVER'] + 'schemas')
            schema_name = st.selectbox('Available Schemas', names, index=1)
            try:
                schema_data = util.get(st.session_state['SERVER']+schema_name)
                st.download_button(
                     label="Download",
                     data=json.dumps(schema_data),
                     file_name=schema_name+'.jsonld',
                     mime='application/json',
                 )
                st.json(schema_data)
            except Exception as x:
                st.error('Could not retrieve schema from Shapiro Server: {}'.format(x))
        except Exception as x:
                st.error('Could not retrieve schema names from Shapiro Server: {}'.format(x))
