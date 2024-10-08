import os
from typing import Optional

from dotenv import load_dotenv
import pandas as pd
import requests


load_dotenv()

BASE_URL = os.environ["BACKEND_URL"]


def api(
    section: str,
    path: str,
    path_extra_1: Optional[str] = None,
    path_extra_2: Optional[
        str
    ] = None,  # TODO: this is pretty silly, but it works for now
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
    if path_extra_1:
        path = f"{path}/{path_extra_1}"
    if path_extra_2:
        path = f"{path}/{path_extra_2}"
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
