from lib.api import api2
import plotly.express as px
import streamlit as st

from utils import fetch_result_with_retry


def health_cached_page():
    health_distribution = api2("health/health_distribution")
    largest_perp_positions = api2("health/largest_perp_positions")
    most_levered_positions = api2("health/most_levered_perp_positions_above_1m")
    largest_spot_borrows = api2("health/largest_spot_borrows")
    most_levered_borrows = api2("health/most_levered_spot_borrows_above_1m")

    print(health_distribution)

    fig = px.bar(
        health_distribution,
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
        st.markdown("### **Largest perp positions:**")
        st.dataframe(largest_perp_positions, hide_index=True)
        st.markdown("### **Most levered perp positions > $1m:**")
        st.dataframe(most_levered_positions, hide_index=True)

    with spot_col:
        st.markdown("### **Largest spot borrows:**")
        st.dataframe(largest_spot_borrows, hide_index=True)
        st.markdown("### **Most levered spot borrows > $750k:**")
        st.dataframe(most_levered_borrows, hide_index=True)
