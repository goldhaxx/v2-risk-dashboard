from lib.api import api
import streamlit as st


def backend_page():

    if st.button("Load Pickle"):
        result = api("snapshot", "pickle", as_json=True)
        st.write(result)

    st.write(
        """
    ## Backend API

    - [swagger](http://localhost:8000/docs)

    - [redoc](http://localhost:8000/redoc)
    """
    )

    st.title("Health")
