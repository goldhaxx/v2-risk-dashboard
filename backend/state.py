from typing import Optional

from anchorpy import Wallet
from driftpy.drift_client import DriftClient
from driftpy.market_map.market_map import MarketMap
from driftpy.pickle.vat import Vat
from driftpy.user_map.user_map import UserMap
from driftpy.user_map.userstats_map import UserStatsMap
import pandas as pd
from solana.rpc.async_api import AsyncClient


class BackendState:
    some_df: pd.DataFrame
    connection: AsyncClient
    dc: DriftClient
    spot_map: MarketMap
    perp_map: MarketMap
    user_map: UserMap
    stats_map: UserStatsMap
    vat: Vat
    ready: bool
