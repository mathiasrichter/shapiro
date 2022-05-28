import validators
import streamlit as st
from multipage import Page

class ConfigPage(Page):

    def title(self):
        return "Configuration"

    def run(self):
        st.title('Shapiro UI Configuration')
        with st.form("Shapiro API URL"):
            url = st.text_input('Shapiro API URL', st.session_state['SERVER'])
            update = st.form_submit_button("Update")
            if update:
                if not validators.url(url):
                    st.error("Invalid url {}".format(url))
                else:
                    if not url.endswith('/'):
                        url += '/'
                    st.session_state['SERVER'] = url
                    st.success("Shapiro Server URL updated to '{}'.".format(url))
