from driftpy.constants.perp_markets import mainnet_perp_market_configs
from driftpy.constants.spot_markets import mainnet_spot_market_configs
from lib.api import api
import pandas as pd
import streamlit as st


options = [0, 1, 2, 3]
labels = [
    "none",
    "liq within 50% of oracle",
    "maint. health < 10%",
    "init. health < 10%",
]


def asset_liab_matrix_page():
    mode = st.selectbox("Options", options, format_func=lambda x: labels[x])
    if mode is None:
        mode = 0

    perp_market_index = st.selectbox(
        "Market index", [x.market_index for x in mainnet_perp_market_configs]
    )
    if perp_market_index is None:
        perp_market_index = 0

    result = api(
        "asset-liability",
        "matrix",
        "0" if mode is None else str(mode),
        "0" if perp_market_index is None else str(perp_market_index),
        as_json=True,
    )
    res = pd.DataFrame(result["res"])
    df = pd.DataFrame(result["df"])

    st.write(f"{df.shape[0]} users for scenario")
    st.write(res)

    tabs = st.tabs(["FULL"] + [x.symbol for x in mainnet_spot_market_configs])
    tabs[0].dataframe(df, hide_index=True)

    for idx, tab in enumerate(tabs[1:]):
        important_cols = [x for x in df.columns if "spot_" + str(idx) in x]
        toshow = df[["spot_asset", "net_usd_value"] + important_cols]
        toshow = toshow[toshow[important_cols].abs().sum(axis=1) != 0].sort_values(
            by="spot_" + str(idx) + "_all", ascending=False
        )
        tab.write(f"{ len(toshow)} users with this asset to cover liabilities")
        tab.dataframe(toshow, hide_index=True)
