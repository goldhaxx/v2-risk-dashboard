from lib.api import api
import plotly.express as px
import streamlit as st


def health_page():
    health_distribution = api("health", "health_distribution")
    largest_perp_positions = api("health", "largest_perp_positions")
    most_levered_positions = api("health", "most_levered_perp_positions_above_1m")
    largest_spot_borrows = api("health", "largest_spot_borrows")
    most_levered_borrows = api("health", "most_levered_spot_borrows_above_1m")

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
        st.write(largest_perp_positions)
        st.markdown("### **Most levered perp positions > $1m:**")
        st.write(most_levered_positions)

    with spot_col:
        st.markdown("### **Largest spot borrows:**")
        st.write(largest_spot_borrows)
        st.markdown("### **Most levered spot borrows > $750k:**")
        st.write(most_levered_borrows)
