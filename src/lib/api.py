import json
import os
from typing import Optional

from dotenv import load_dotenv
import pandas as pd
import requests
import streamlit as st


load_dotenv()

BASE_URL = os.environ["BACKEND_URL"]
R2_PREFIX = "https://pub" + "-7dc8852b9fd5407a92614093e1f73280.r" + "2.dev"


def api(
    section: str,
    path: str,
    as_json: bool = False,
    params: Optional[dict] = None,
):
    """
    Fetches data from the backend API. To find the corresponding
    path, look at the `backend/api/` directory. It should be setup
    so that the `section` is the name of the file, the `path` is the
    function inside the file.

    Args:
        section (str): The section of the API to fetch from.
        path (str): The path of the API to fetch from.
        path_extra (Optional[str]): An optional extra path to append to the path.
        as_json (bool): Whether to return the response as JSON.

    Returns:
        The response from the API.
    """
    if params:
        response = requests.get(f"{BASE_URL}/api/{section}/{path}", params=params)
    else:
        response = requests.get(f"{BASE_URL}/api/{section}/{path}")

    if as_json:
        return response.json()

    try:
        return pd.DataFrame(response.json())
    except ValueError:
        return response.json()


@st.cache_data(ttl=1000)
def api2(url: str, _params: Optional[dict] = None, key: str = "") -> dict:
    """
    Fetch data from R2 storage using the simplified naming scheme.
    Example: /api/health/health_distribution -> GET_api_health_health_distribution.json
    Example with params: /api/price-shock/usermap?asset_group=ignore+stables&oracle_distortion=0.05
        -> GET_api_price-shock_usermap__asset_group-ignore+stables_oracle_distortion-0.05.json
    """
    print("===> SERVING CACHE")

    cache_key = f"GET/api/{url}".replace("/", "_")

    if _params:
        print(f"Params: {_params}")
        query_parts = []
        for k, v in _params.items():
            if isinstance(v, str):
                v = v.replace(" ", "%2B")
            query_parts.append(f"{k}-{v}")
        query_str = "_".join(query_parts)
        cache_key = f"{cache_key}__{query_str}"

    use_local = os.environ.get("USE_LOCAL_CACHE", "false").lower() == "true"
    r2_url = f"{R2_PREFIX}/{cache_key}.json"
    if use_local:
        r2_url = f"{BASE_URL}/api/ucache/{cache_key}.json"

    print(f"Fetching from: {r2_url}")
    response = requests.get(r2_url)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch from R2: {response.status_code}")

    try:
        response_data = response.json()
        return response_data["content"]
    except requests.exceptions.JSONDecodeError as e:
        error_message = f"Cache file for {url} is malformed. Please regenerate the cache."
        print(error_message)
        raise Exception(error_message) from e
