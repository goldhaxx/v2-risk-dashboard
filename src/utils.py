import os
from typing import Optional

from driftpy.drift_client import DriftClient
from driftpy.drift_user import DriftUser
from driftpy.market_map.market_map import MarketMap
from driftpy.market_map.market_map_config import (
    WebsocketConfig as MarketMapWebsocketConfig,
)
from driftpy.market_map.market_map_config import MarketMapConfig
from driftpy.math.margin import MarginCategory
from driftpy.pickle.vat import Vat
from driftpy.types import MarketType
from driftpy.user_map.user_map import UserMap
from driftpy.user_map.user_map_config import (
    WebsocketConfig as UserMapWebsocketConfig,
)
from driftpy.user_map.user_map_config import UserMapConfig
from driftpy.user_map.user_map_config import UserStatsMapConfig
from driftpy.user_map.userstats_map import UserStatsMap


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
            if not prefix in newest_files or slot > newest_files[prefix][1]:
                newest_files[prefix] = (directory + "/" + filename, slot)

    # mapping e.g { 'spotoracles' : 'spotoracles_272636137.pkl' }
    prefix_to_filename = {
        prefix: filename for prefix, (filename, _) in newest_files.items()
    }

    return prefix_to_filename


# function assumes that you have already subscribed
# the use of websocket configs in here doesn't matter because the maps are never subscribed to
async def load_vat(dc: DriftClient, pickle_map: dict[str, str]) -> Vat:
    perp = MarketMap(
        MarketMapConfig(
            dc.program, MarketType.Perp(), MarketMapWebsocketConfig(), dc.connection
        )
    )

    spot = MarketMap(
        MarketMapConfig(
            dc.program, MarketType.Spot(), MarketMapWebsocketConfig(), dc.connection
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
