import streamlit as st
from multipage import Page
import util as util
import pandas as pd
from st_aggrid import AgGrid

class StartPage(Page):

    NAME = 'Schema Name'
    URL = 'Schema URL'

    def title(self):
        return 'Start'

    def prep_data(self):
        data = {}
        data[self.NAME] = []
        data[self.URL] = []
        for n in util.get(st.session_state['SERVER'] + 'schemas'):
            data[self.NAME].append(n)
            data[self.URL].append('{}{}'.format(st.session_state['SERVER'], n))
        return data

    def load_schema(name):
        st.info(name)

    def run(self):
        st.title('Shapiro UI')
        st.write('A browser/editor for JSON-LD Schemas served by Shapiro.')
        st.write("Using Shapiro Server at '{}'".format(st.session_state['SERVER']))
        st.header('Available Schemas')
        data = self.prep_data()
        rows = len(data.keys()) + 1
        grid_height = 0
        if rows < 10:
            grid_height = (rows * 30 ) + 1
        else:
            grid_height = 301
        try:
            AgGrid(pd.DataFrame(data), height=grid_height, theme='dark', fit_columns_on_grid_load=True)
        except Exception as x:
            st.error('Could not retrieve schemas from Shapiro Server: {}'.format(x))
