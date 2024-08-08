import asyncio
import os 
import shutil
import glob
import time
import traceback

from anchorpy import Wallet

from solana.rpc.async_api import AsyncClient

from driftpy.drift_client import DriftClient
from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.user_map.user_map import UserMap
from driftpy.user_map.user_map_config import UserMapConfig, WebsocketConfig as Cfg1
from driftpy.user_map.userstats_map import UserStatsMap, UserStatsMapConfig
from driftpy.market_map.market_map_config import MarketMapConfig, WebsocketConfig as Cfg2
from driftpy.market_map.market_map import MarketMap
from driftpy.pickle.vat import Vat
from driftpy.types import MarketType


async def main():
    rpc = str(os.getenv("MAINNET_RPC_ENDPOINT"))
    wallet = Wallet.dummy()

    dc = DriftClient(
        AsyncClient(rpc),
        wallet,
        "mainnet",
        account_subscription=AccountSubscriptionConfig("cached")
    )

    await dc.subscribe()

    users = UserMap(UserMapConfig(dc, Cfg1))
    stats = UserStatsMap(UserStatsMapConfig(dc))
    spot = MarketMap(MarketMapConfig(dc.program, MarketType.Spot(), Cfg2, dc.connection))
    perp = MarketMap(MarketMapConfig(dc.program, MarketType.Perp(), Cfg2, dc.connection))

    vat = Vat(dc, users, stats, spot, perp)
    
    start = time.time()
    try:
        await vat.pickle()
    except:
        print("an error occurred during pickling:")
        traceback.print_exc()
        os._exit(0)
    print("pickled in:", time.time() - start)

    pkl_files = glob.glob("*.pkl")

    for file in pkl_files:
        shutil.move(file, "./pickles")


if __name__ == "__main__":
    asyncio.run(main())