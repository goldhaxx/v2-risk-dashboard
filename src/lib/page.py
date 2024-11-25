"""
Common page functionality
"""

from datetime import datetime
import os

import humanize
from lib.api import api
import streamlit as st

from utils import fetch_result_with_retry


RPC_STATE_KEY = "rpc_url"
NETWORK_STATE_KEY = "network"
VAT_STATE_KEY = "vat"


def header():
    image_path = os.path.abspath("./images/drift.svg")
    st.logo(image=image_path)


def sidebar():
    st.sidebar.header("Data Information")
    st.sidebar.write(
        "Slot information available for price shock and asset liability matrix pages. Data is live otherwise."
    )


def needs_backend(page_callable: callable):
    """
    Decorator to add a guard to a page function
    """

    def page_with_guard():
        try:
            api("metadata", "", as_json=True)
        except Exception as e:
            st.error("Sorry, unable to reach backend")
            return

        page_callable()

    return page_with_guard
