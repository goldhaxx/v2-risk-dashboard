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
    st.sidebar.header("Options")

    network = st.sidebar.radio("env", ("mainnet-beta", "devnet"))
    st.session_state[NETWORK_STATE_KEY] = network

    url = os.getenv("RPC_URL", "")
    rpc = st.sidebar.text_input("RPC URL", value=url)
    if network == "mainnet-beta" and rpc == "":
        rpc = os.getenv("ANCHOR_PROVIDER_URL", "")
    st.session_state[RPC_STATE_KEY] = rpc

    if VAT_STATE_KEY not in st.session_state:
        st.session_state[VAT_STATE_KEY] = None
    st.sidebar.write(
        f"Have VAT? {'✅' if st.session_state[VAT_STATE_KEY] is not None else 'Not Loaded'} "
    )

    metadata = api("metadata", "", as_json=True)
    pickle_file = metadata["pickle_file"]
    pickle_file = pickle_file.split("/")[-1]
    timestamp = pickle_file.split("-")[1:]
    timestamp = datetime.strptime(" ".join(timestamp), "%Y %m %d %H %M %S")
    time_ago = datetime.now() - timestamp
    time_ago_str = humanize.precisedelta(time_ago, minimum_unit="minutes")
    st.sidebar.write(f"Last snapshot taken at: {timestamp} ({time_ago_str} ago)")


def needs_rpc_and_vat(page_callable: callable):
    """
    Decorator to add a guard to a page function
    """

    def page_with_guard():
        rpc = st.session_state[RPC_STATE_KEY]
        if rpc == "🤫" or rpc == "" or rpc is None:
            st.warning("Please enter a Solana RPC URL in the sidebar")
            return

        vat = st.session_state[VAT_STATE_KEY]
        if vat is None:
            drift_client = DriftClient(
                AsyncClient(rpc),
                Wallet.dummy(),
                account_subscription=AccountSubscriptionConfig("cached"),
            )
            loop: AbstractEventLoop = asyncio.new_event_loop()
            newest_snapshot = load_newest_files(os.getcwd() + "/pickles")
            start_load_vat = time.time()
            vat = loop.run_until_complete(load_vat(drift_client, newest_snapshot))
            st.session_state["vat"] = vat
            print(f"loaded vat in {time.time() - start_load_vat}")
            st.session_state[VAT_STATE_KEY] = vat
            loop.close()

        page_callable()

    return page_with_guard
