import pandas as pd
import streamlit as st
from driftpy.constants.spot_markets import mainnet_spot_market_configs

from lib.api import api
from utils import fetch_result_with_retry


def format_authority(authority: str) -> str:
    """Format authority to show first and last 4 chars"""
    return f"{authority[:4]}...{authority[-4:]}"


def deposits_page():
    params = st.query_params
    market_index = int(params.get("market_index", 0))

    col1, col2 = st.columns([2, 2])

    with col1:
        market_index = st.selectbox(
            "Market index",
            [x.market_index for x in mainnet_spot_market_configs],
            index=[x.market_index for x in mainnet_spot_market_configs].index(
                market_index
            ),
            format_func=lambda x: f"{x} ({mainnet_spot_market_configs[int(x)].symbol})",
        )
        st.query_params.update({"market_index": str(market_index)})

    result = fetch_result_with_retry(
        api,
        "deposits",
        "deposits",
        as_json=True,
        params={"market_index": market_index},
    )
    if result is None:
        st.error("No deposits found")
        return

    df = pd.DataFrame(result["deposits"])
    total_number_of_deposited = sum([x["balance"] for x in result["deposits"]])

    with col2:
        min_balance = st.number_input(
            "Minimum Balance",
            min_value=0.0,
            max_value=float(df["balance"].max()),
            value=0.0,
            step=0.1,
            format="%.4f",
        )

    # Filter dataframe based on minimum balance
    filtered_df = df[df["balance"] >= min_balance]

    st.write(f"Total deposits value: **${filtered_df['value'].sum():,.2f}**")
    st.write(f"Number of depositors: **{len(filtered_df)}**")
    st.write(
        f"Total number of deposited {mainnet_spot_market_configs[market_index].symbol}: **{total_number_of_deposited}**"
    )

    # Create tabs for different views
    tabs = st.tabs(["All Deposits", "By Authority"])

    with tabs[0]:
        # Add download button for all deposits
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            "Download All Deposits CSV",
            csv,
            "all_deposits.csv",
            "text/csv",
            key="download-all-deposits",
        )

        st.dataframe(
            filtered_df.sort_values("value", ascending=False),
            column_config={
                "authority": st.column_config.TextColumn(
                    "Authority",
                    help="Account authority",
                ),
                "user_account": st.column_config.TextColumn(
                    "User Account",
                    help="User account address",
                ),
                "value": st.column_config.NumberColumn(
                    "Value",
                    format="$%.8f",
                ),
                "balance": st.column_config.NumberColumn(
                    "Balance",
                    format="%.8f",
                ),
            },
            hide_index=True,
        )

    with tabs[1]:
        # Add download button for grouped deposits
        grouped_df = (
            filtered_df.groupby("authority")
            .agg({"value": "sum", "balance": "sum", "user_account": "count"})
            .reset_index()
        )
        grouped_df = grouped_df.rename(columns={"user_account": "num_accounts"})
        grouped_df = grouped_df.sort_values("value", ascending=False)

        csv_grouped = grouped_df.to_csv(index=False)
        st.download_button(
            "Download Authority Summary CSV",
            csv_grouped,
            "deposits_by_authority.csv",
            "text/csv",
            key="download-grouped-deposits",
        )

        st.dataframe(
            grouped_df,
            column_config={
                "authority": st.column_config.TextColumn(
                    "Authority",
                    help="Account authority",
                ),
                "value": st.column_config.NumberColumn(
                    "Total Value",
                    format="$%.2f",
                ),
                "balance": st.column_config.NumberColumn(
                    "Total Balance",
                    format="%.4f",
                ),
                "num_accounts": st.column_config.NumberColumn(
                    "Number of Accounts",
                    format="%d",
                ),
            },
            hide_index=True,
        )
