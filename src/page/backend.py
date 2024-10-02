import pandas as pd
import requests
import streamlit as st


def backend_page():

    if st.button("Load Pickle"):
        result = requests.get("http://localhost:8000/pickle")
        st.write(result.json())

    st.write(
        """
    ## Backend API

    - [swagger](http://localhost:8000/docs)

    - [redoc](http://localhost:8000/redoc)
    """
    )

    st.title("Health")
