import pandas as pd
import streamlit as st

from lib.api import fetch_api_data


def pnl_page():
    st.title("Top PnL by User (All Time)")
    try:
        pnl_data = fetch_api_data("pnl", "top_pnl", retry=True)
    except Exception as e:
        st.error(f"Error fetching PnL data: {e}")
        return

    df = pd.DataFrame(pnl_data)
    for col in ["realized_pnl", "unrealized_pnl", "total_pnl"]:
        df[col] = df[col].map("${:,.2f}".format)

    csv = df.to_csv(index=False)
    st.download_button(
        "Download PnL Data CSV", csv, "top_pnl.csv", "text/csv", key="download-pnl"
    )
    st.dataframe(
        df,
        column_config={
            "authority": st.column_config.TextColumn(
                "Authority",
                help="Authority address",
            ),
            "user_key": st.column_config.TextColumn(
                "User Account",
                help="User account address",
            ),
            "realized_pnl": st.column_config.NumberColumn("All Time Realized PnL"),
            "unrealized_pnl": st.column_config.NumberColumn("Unrealized PnL"),
            "total_pnl": st.column_config.NumberColumn("Total PnL"),
        },
        hide_index=True,
    )
