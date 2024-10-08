"""
VAT (Virtual Account Table) Loading
"""

import asyncio
import os
import time

import streamlit as st
from driftpy.drift_client import DriftClient

from utils import load_newest_files, load_vat


@st.cache_data()
def cached_load_vat(dc: DriftClient):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    newest_snapshot = load_newest_files(os.getcwd() + "/pickles")
    vat = loop.run_until_complete(load_vat(dc, newest_snapshot))
    loop.close()
    return vat


def get_vat(dc: DriftClient):
    start_load_vat = time.time()
    vat = cached_load_vat(dc)
    print(f"loaded vat in {time.time() - start_load_vat}")
    return vat
