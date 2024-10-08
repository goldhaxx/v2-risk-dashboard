"""
Common page functionality
"""

import asyncio
from asyncio import AbstractEventLoop
from datetime import datetime
import os
import time

from anchorpy import Wallet
from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.drift_client import DriftClient
import humanize
from lib.api import api
from solana.rpc.async_api import AsyncClient
import streamlit as st

from utils import load_newest_files
from utils import load_vat


RPC_STATE_KEY = "rpc_url"
NETWORK_STATE_KEY = "network"
VAT_STATE_KEY = "vat"


def header():
    image_path = os.path.abspath("./images/drift.svg")
    st.logo(image=image_path)


def sidebar():
    st.sidebar.header("Data Information")
    try:
        metadata = api("metadata", "", as_json=True)
        pickle_file = metadata["pickle_file"]
        if pickle_file[-1] == "/":
            pickle_file = pickle_file[:-1]
        timestamp = pickle_file.split("-")[1:]
        timestamp = datetime.strptime(" ".join(timestamp), "%Y %m %d %H %M %S")
        time_ago = datetime.now() - timestamp
        time_ago_str = humanize.precisedelta(
            time_ago,
            minimum_unit="seconds",
        )
        st.sidebar.write(f"Last snapshot: {timestamp}")
        st.sidebar.write(f"Time since last snapshot: {time_ago_str}")
    except Exception as e:
        print(e)
        st.sidebar.error("Unable to reach backend")


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
