import streamlit as st

from lib.health_utils import (
    get_account_health_distribution,
    get_largest_perp_positions,
    get_largest_spot_borrows,
    get_most_levered_perp_positions_above_1m,
    get_most_levered_spot_borrows_above_1m,
)
from lib.page import VAT_STATE_KEY


def health_page():
    vat = st.session_state[VAT_STATE_KEY]
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
