import streamlit as st


def welcome_page():
    st.title("Welcome to Drift v2 Risk Dashboard")

    st.markdown(
        """
    This dashboard provides comprehensive risk analysis tools for Drift v2. 
    Explore various aspects of the protocol's health and performance using the following pages:
    
    - **Orderbook**: Compare hyperliquid price to drift orderbook price
    - **Health**: View account health distribution and largest positions
    - **Price Shock**: Analyze the impact of price changes on the protocol
    - **Asset-Liability Matrix**: Examine the balance of assets and liabilities
    - **Liquidations**: Explore liquidation curves and potential risks
    
    To get started, select a page from the sidebar on the left.
    """
    )

    st.markdown("---")
    st.markdown(
        "For more information about Drift Protocol, visit [drift.trade](https://drift.trade)"
    )
