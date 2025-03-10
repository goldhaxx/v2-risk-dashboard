import pandas as pd
import plotly.express as px
import streamlit as st

from lib.api import fetch_api_data


def health_page():
    st.markdown("# Health")

    st.markdown(
        """
        Account health is a measure of the health of a user's account. It is calculated as the ratio of the user's collateral to the user's debt.
        For more information about how account health is calculated, see [account health](https://docs.drift.trade/trading/account-health) in the docs.
        """
    )
    health_distribution = fetch_api_data(
        "health",
        "health_distribution",
        retry=True,
    )

    fig = px.bar(
        pd.DataFrame(health_distribution),
        x="Health Range",
        y="Counts",
        title="Health Distribution",
        hover_data={"Notional Values": ":,"},  # Custom format for notional values
        labels={"Counts": "Num Users", "Notional Values": "Notional Value ($)"},
    )

    fig.update_traces(
        hovertemplate="<b>Health Range: %{x}</b><br>Count: %{y}<br>Notional Value: $%{customdata[0]:,.0f}<extra></extra>"
    )

    with st.container():
        st.plotly_chart(fig, use_container_width=True)

    perp_col, spot_col = st.columns([1, 1])

    with perp_col:
        largest_perp_positions = fetch_api_data(
            "health",
            "largest_perp_positions",
            retry=True,
        )
        st.markdown("### **Largest perp positions:**")
        st.dataframe(pd.DataFrame(largest_perp_positions), hide_index=True)

        most_levered_positions = fetch_api_data(
            "health",
            "most_levered_perp_positions_above_1m",
            retry=True,
        )
        st.markdown("### **Most levered perp positions > $1m:**")
        st.dataframe(pd.DataFrame(most_levered_positions), hide_index=True)

    with spot_col:
        largest_spot_borrows = fetch_api_data(
            "health",
            "largest_spot_borrows",
            retry=True,
        )
        st.markdown("### **Largest spot borrows:**")
        st.dataframe(pd.DataFrame(largest_spot_borrows), hide_index=True)

        most_levered_borrows = fetch_api_data(
            "health",
            "most_levered_spot_borrows_above_1m",
            retry=True,
        )
        st.markdown("### **Most levered spot borrows > $750k:**")
        st.dataframe(pd.DataFrame(most_levered_borrows), hide_index=True)
