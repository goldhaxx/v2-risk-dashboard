import asyncio
import heapq
import time
import os

from asyncio import AbstractEventLoop
import plotly.express as px  # type: ignore
import pandas as pd  # type: ignore

from typing import Any

from solana.rpc.async_api import AsyncClient

from anchorpy import Wallet

import streamlit as st
from driftpy.drift_user import DriftUser
from driftpy.drift_client import DriftClient
from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.constants.numeric_constants import (
    BASE_PRECISION,
    SPOT_BALANCE_PRECISION,
    PRICE_PRECISION,
)
from driftpy.types import is_variant
from driftpy.pickle.vat import Vat
from driftpy.constants.spot_markets import (
    mainnet_spot_market_configs,
    devnet_spot_market_configs,
)
from driftpy.constants.perp_markets import (
    mainnet_perp_market_configs,
    devnet_perp_market_configs,
)

from utils import load_newest_files, load_vat, to_financial
from sections.asset_liab_matrix import asset_liab_matrix_page
from sections.ob import ob_cmp_page
from sections.scenario import plot_page
from sections.liquidation_curves import plot_liquidation_curve
from sections.margin_model import run_margin_model
from cache import get_cached_asset_liab_dfs

from health_utils import *


# @st.cache
# def load_price_shock_dfs(dc: DriftClient, vat: Vat, loop: AbstractEventLoop):


def setup_context(dc: DriftClient, loop: AbstractEventLoop):
    vat: Vat
    if "vat" not in st.session_state:
        newest_snapshot = load_newest_files(os.getcwd() + "/pickles")

        start_load_vat = time.time()
        vat = loop.run_until_complete(load_vat(dc, newest_snapshot))
        st.session_state["vat"] = vat
        print(f"loaded vat in {time.time() - start_load_vat}")
    else:
        vat = st.session_state["vat"]

    if "asset_liab_data" not in st.session_state:
        st.session_state["asset_liab_data"] = get_cached_asset_liab_dfs(dc, vat, loop)

    st.session_state["context"] = True


def main():
    st.set_page_config(layout="wide")

    url = os.getenv("RPC_URL", "🤫")
    env = st.sidebar.radio("env", ("mainnet-beta", "devnet"))
    rpc = st.sidebar.text_input("RPC URL", value=url)
    if env == "mainnet-beta" and (rpc == "🤫" or rpc == ""):
        rpc = os.environ["ANCHOR_PROVIDER_URL"]

    query_index = 0

    def query_string_callback():
        st.query_params["tab"] = st.session_state.query_key

    query_tab = st.query_params.get("tab", ["Welcome"])[0]
    tab_options = (
        "Welcome",
        "Health",
        "Price-Shock",
        "Asset-Liab-Matrix",
        "Orderbook",
        "Liquidations",
        "Margin-Model",
    )
    for idx, x in enumerate(tab_options):
        if x.lower() == query_tab.lower():
            query_index = idx

    tab = st.sidebar.radio(
        "Select Tab:",
        tab_options,
        query_index,
        on_change=query_string_callback,
        key="query_key",
    )

    if tab is None:
        tab = "Welcome"

    if rpc == "🤫" or rpc == "":
        st.warning("Please enter a Solana RPC URL")
    else:
        drift_client = DriftClient(
            AsyncClient(rpc),
            Wallet.dummy(),
            account_subscription=AccountSubscriptionConfig("cached"),
        )

        loop: AbstractEventLoop = asyncio.new_event_loop()
        st.session_state["context"] = False
        if (
            tab.lower()
            in [
                "welcome",
                "health",
                "price-shock",
                "asset-liab-matrix",
                "liquidations",
                "margin-model",
            ]
            and "vat" not in st.session_state
        ):
            # start_sub = time.time()
            # loop.run_until_complete(dc.subscribe())
            # print(f"subscribed in {time.time() - start_sub}")

            # newest_snapshot = load_newest_files(os.getcwd() + "/pickles")

            # start_load_vat = time.time()
            # vat = loop.run_until_complete(load_vat(drift_client, newest_snapshot))
            # st.session_state["vat"] = vat
            # print(f"loaded vat in {time.time() - start_load_vat}")
            if st.session_state["context"] == False:
                setup_context(drift_client, loop)
        elif tab.lower() in [
            "health",
            "price-shock",
            "asset-liab-matrix",
            "liquidations",
            "margin model",
        ]:
            vat = st.session_state["vat"]

        if tab.lower() == "health":
            health_distribution = get_account_health_distribution(vat)

            with st.container():
                st.plotly_chart(health_distribution, use_container_width=True)

            perp_col, spot_col = st.columns([1, 1])

            with perp_col:
                largest_perp_positions = get_largest_perp_positions(vat)
                st.markdown("### **Largest perp positions:**")
                st.table(largest_perp_positions)
                most_levered_positions = get_most_levered_perp_positions_above_1m(vat)
                st.markdown("### **Most levered perp positions > $1m:**")
                st.table(most_levered_positions)

            with spot_col:
                largest_spot_borrows = get_largest_spot_borrows(vat)
                st.markdown("### **Largest spot borrows:**")
                st.table(largest_spot_borrows)
                most_levered_borrows = get_most_levered_spot_borrows_above_1m(vat)
                st.markdown("### **Most levered spot borrows > $750k:**")
                st.table(most_levered_borrows)

        elif tab.lower() == "price-shock":
            plot_page(loop, vat, drift_client)
        elif tab.lower() == "asset-liab-matrix":
            asset_liab_matrix_page(loop, vat, drift_client)
        elif tab.lower() == "orderbook":
            ob_cmp_page()
        elif tab.lower() == "liquidations":
            plot_liquidation_curve(vat)
        elif tab.lower() == "margin model":
            run_margin_model()


main()
