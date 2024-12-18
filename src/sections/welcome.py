import streamlit as st
from streamlit.navigation.page import StreamlitPage


def welcome_page():
    st.title("Drift Risk Dashboard")
    st.markdown("Track key risk metrics across Drift through these dashboard pages")
    st.page_link(
        StreamlitPage("page/orderbook.py"),
        label="📈 **Orderbook** - Compare hyperliquid price to drift orderbook price",
    )

    st.page_link(
        StreamlitPage("page/health.py"),
        label="🏥 **Health** - View account health distribution and largest positions",
    )

    st.page_link(
        StreamlitPage("page/price_shock.py"),
        label="⚡ **Price Shock** - Analyze the impact of price changes on the protocol",
    )

    st.page_link(
        StreamlitPage("page/asset_liability.py"),
        label="📊 **Asset-Liability Matrix** - Track assets and liabilities across markets and accounts",
    )

    st.page_link(
        StreamlitPage("page/liquidation_curves.py"),
        label="💧 **Liquidations** - Explore liquidation curves and potential risks",
    )

    st.markdown("---")
    st.markdown(
        "For more information about Drift Protocol, visit [drift.trade](https://drift.trade)"
    )
