import os
from typing import Optional

import requests
from driftpy.drift_client import DriftClient
from driftpy.market_map.market_map import MarketMap
from driftpy.market_map.market_map_config import MarketMapConfig
from driftpy.market_map.market_map_config import (
    WebsocketConfig as MarketMapWebsocketConfig,
)
from driftpy.pickle.vat import Vat
from driftpy.types import MarketType
from driftpy.user_map.user_map import UserMap
from driftpy.user_map.user_map_config import UserMapConfig, UserStatsMapConfig
from driftpy.user_map.user_map_config import (
    WebsocketConfig as UserMapWebsocketConfig,
)
from driftpy.user_map.userstats_map import UserStatsMap

from dotenv import load_dotenv
load_dotenv()

def to_financial(num):
    num_str = str(num)
    decimal_pos = num_str.find(".")
    if decimal_pos != -1:
        return float(num_str[: decimal_pos + 3])
    return num


def load_newest_files(directory: Optional[str] = None) -> dict[str, str]:
    directory = directory or os.getcwd()

    newest_files: dict[str, tuple[str, int]] = {}

    prefixes = ["perp", "perporacles", "spot", "spotoracles", "usermap", "userstats"]

    for filename in os.listdir(directory):
        if filename.endswith(".pkl") and any(
            filename.startswith(prefix + "_") for prefix in prefixes
        ):
            start = filename.index("_") + 1
            prefix = filename[: start - 1]
            end = filename.index(".")
            slot = int(filename[start:end])
            if prefix not in newest_files or slot > newest_files[prefix][1]:
                newest_files[prefix] = (directory + "/" + filename, slot)

    prefix_to_filename = {
        prefix: filename for prefix, (filename, _) in newest_files.items()
    }

    return prefix_to_filename


async def load_vat(dc: DriftClient, pickle_map: dict[str, str]) -> Vat:
    perp = MarketMap(
        MarketMapConfig(
            dc.program,
            MarketType.Perp(),  # type: ignore
            MarketMapWebsocketConfig(),
            dc.connection,
        )
    )

    spot = MarketMap(
        MarketMapConfig(
            dc.program,
            MarketType.Spot(),  # type: ignore
            MarketMapWebsocketConfig(),
            dc.connection,
        )
    )

    user = UserMap(UserMapConfig(dc, UserMapWebsocketConfig()))

    stats = UserStatsMap(UserStatsMapConfig(dc))

    user_filename = pickle_map["usermap"]
    stats_filename = pickle_map["userstats"]
    perp_filename = pickle_map["perp"]
    spot_filename = pickle_map["spot"]
    perp_oracles_filename = pickle_map["perporacles"]
    spot_oracles_filename = pickle_map["spotoracles"]

    vat = Vat(dc, user, stats, spot, perp)

    await vat.unpickle(
        user_filename,
        stats_filename,
        spot_filename,
        perp_filename,
        spot_oracles_filename,
        perp_oracles_filename,
    )

    return vat


def get_current_slot():
    payload = {
        "id": 1,
        "jsonrpc": "2.0",
        "method": "getSlot",
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
    }
    response = requests.post(
        os.getenv("RPC_URL"), json=payload, headers=headers
    )
    return response.json()["result"]
