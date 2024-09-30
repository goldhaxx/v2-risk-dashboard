"""
Common page functionality
"""

import asyncio
import os
import time
from asyncio import AbstractEventLoop

import streamlit as st
from anchorpy import Wallet
from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.drift_client import DriftClient
from solana.rpc.async_api import AsyncClient

from utils import load_newest_files, load_vat

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
