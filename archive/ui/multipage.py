# based on https://github.com/prakharrathi25/data-storyteller/ with my own improvements

"""
This file is the framework for generating multiple Streamlit applications
through an object oriented framework.
"""

# Import necessary libraries
import streamlit as st
from abc import ABC, abstractmethod

# Define abstract base class for pages
class Page(ABC):

    @abstractmethod
    def title(self):
        """Name of the page to be used in navigation"""

    @abstractmethod
    def run(self):
        """The actual Streamlit code for the page"""

# Define the multipage class to manage the multiple apps in our program
class MultiPage:
    """Class for combining multiple streamlit applications as pages."""

    def __init__(self, nav_title = 'App Navigation') -> None:
        self.nav_title = nav_title
        self.pages = {}

    def add_page(self, page:Page) -> None:
        """Add a page to the project
        Args:
            page: Implementation of the actual page as subclass of Page
        """
        self.pages[page.title()] = page.run

    def run(self):
        page = st.sidebar.selectbox(self.nav_title, self.pages.keys(), help='Select a screen to navigate to.')
        self.pages[page]()
