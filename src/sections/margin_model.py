from driftpy.pickle.vat import Vat

import streamlit as st

from sections.asset_liab_matrix import NUMBER_OF_SPOT


def run_margin_model():
    if "vat" not in st.session_state:
        st.write("No Vat loaded.")
        return

    vat: Vat = st.session_state["vat"]
