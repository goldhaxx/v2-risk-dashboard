import pandas as pd
import requests
import streamlit as st


def test_backend():
    response = requests.get("http://localhost:8000/users")
    df = pd.DataFrame(response.json())
    st.dataframe(df, hide_index=True)
