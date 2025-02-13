import os
import time
from typing import Optional

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("BACKEND_URL")
STORAGE_PREFIX = os.getenv("STORAGE_PREFIX")


def fetch_api_data(
    section: str,
    path: str,
    params: Optional[dict] = None,
    retry: bool = False,
) -> dict:
    """
    Makes direct API calls to the backend service with optional retry logic for "miss" results.

    Args:
        section (str): API section (maps to filename in backend/api/)
        path (str): API endpoint (maps to function name)
        params (Optional[dict]): Query parameters to include in request
        retry (bool): Whether to retry on "miss" results up to 10 times with 0.5s delay

    Returns:
        dict: JSON response data
    """
    if not retry:
        if params:
            response = requests.get(f"{BASE_URL}/api/{section}/{path}", params=params)
        else:
            response = requests.get(f"{BASE_URL}/api/{section}/{path}")
    else:
        for _ in range(10):
            if params:
                response = requests.get(
                    f"{BASE_URL}/api/{section}/{path}", params=params
                )
            else:
                response = requests.get(f"{BASE_URL}/api/{section}/{path}")

            result = response.json()
            if not ("result" in result and result["result"] == "miss"):
                break
            time.sleep(0.5)
        else:
            print(f"Fetching {section}/{path} did not succeed after 10 retries")
            return None
    return response.json()


@st.cache_data(ttl=1000)
def fetch_cached_data(url: str, _params: Optional[dict] = None, key: str = "") -> dict:
    """
    Fetches cached data from storage with Streamlit caching. Constructs cache keys
    from the URL and parameters, supporting both local and remote storage.

    Example cache keys:
    - Simple: /api/health/distribution -> GET_api_health_distribution.json
    - With params: /api/shock/map?group=stable&dist=0.05
                  -> GET_api_shock_map__group-stable_dist-0.05.json

    Args:
        url (str): API endpoint path
        _params (Optional[dict]): Query parameters for the request
        key (str): Additional cache key modifier (unused)

    Returns:
        dict: Cached response content
    """
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

    use_storage = os.getenv("USE_STORAGE", "false").lower() == "true"

    if STORAGE_PREFIX and use_storage:
        storage_url = f"{STORAGE_PREFIX}/{cache_key}.json"
    else:
        storage_url = f"{BASE_URL}/api/ucache/{cache_key}.json"

    response = requests.get(storage_url)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch from storage: {response.status_code}")

    response_data = response.json()
    return response_data["content"]
