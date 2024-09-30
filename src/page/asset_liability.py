import asyncio
from asyncio import AbstractEventLoop
import os
import time

from anchorpy import Wallet
from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.constants.perp_markets import mainnet_perp_market_configs
from driftpy.constants.spot_markets import mainnet_spot_market_configs
from driftpy.drift_client import DriftClient
from lib.page import RPC_STATE_KEY
from lib.page import VAT_STATE_KEY
from sections.asset_liab_matrix import get_matrix
from solana.rpc.async_api import AsyncClient
import streamlit as st

from utils import load_newest_files
from utils import load_vat


options = [0, 1, 2, 3]
labels = [
    "none",
    "liq within 50% of oracle",
    "maint. health < 10%",
    "init. health < 10%",
]


def asset_liab_matrix_page():  # (loop: AbstractEventLoop, vat: Vat, drift_client: DriftClient, env='mainnet'):
    st.write("Loading vat...")
    rpc = st.session_state[RPC_STATE_KEY]
    loop: AbstractEventLoop = asyncio.new_event_loop()
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
    st.write(f"loaded vat in {time.time() - start_load_vat}")
    st.session_state[VAT_STATE_KEY] = vat

    mode = st.selectbox("Options", options, format_func=lambda x: labels[x])

    if mode is None:
        mode = 0

    perp_market_inspect = st.selectbox(
        "Market index", [x.market_index for x in mainnet_perp_market_configs]
    )

    if perp_market_inspect is None:
        perp_market_inspect = 0

    res, df = get_matrix(loop, vat, drift_client, "mainnet", mode, perp_market_inspect)

    st.write(f"{df.shape[0]} users for scenario")

    st.write(res)

    tabs = st.tabs(["FULL"] + [x.symbol for x in mainnet_spot_market_configs])

    tabs[0].dataframe(df)

    for idx, tab in enumerate(tabs[1:]):
        important_cols = [x for x in df.columns if "spot_" + str(idx) in x]
        toshow = df[["spot_asset", "net_usd_value"] + important_cols]
        toshow = toshow[toshow[important_cols].abs().sum(axis=1) != 0].sort_values(
            by="spot_" + str(idx) + "_all", ascending=False
        )
        tab.write(f"{ len(toshow)} users with this asset to cover liabilities")
        tab.dataframe(toshow)
