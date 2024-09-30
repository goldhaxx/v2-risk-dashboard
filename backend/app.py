from asyncio import create_task
from asyncio import gather
from contextlib import asynccontextmanager
from datetime import datetime
import glob
import os

from anchorpy import Wallet
from backend.middleware.readiness import ReadinessMiddleware
from backend.state import BackendState
from backend.utils.vat import load_newest_files
from backend.utils.waiting_for import waiting_for
from dotenv import load_dotenv
from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.drift_client import DriftClient
from driftpy.market_map.market_map import MarketMap
from driftpy.market_map.market_map_config import (
    WebsocketConfig as MarketMapWebsocketConfig,
)
from driftpy.market_map.market_map_config import MarketMapConfig
from driftpy.pickle.vat import Vat
from driftpy.types import MarketType
from driftpy.user_map.user_map import UserMap
from driftpy.user_map.user_map_config import (
    WebsocketConfig as UserMapWebsocketConfig,
)
from driftpy.user_map.user_map_config import UserMapConfig
from driftpy.user_map.user_map_config import UserStatsMapConfig
from driftpy.user_map.userstats_map import UserStatsMap
from fastapi import FastAPI
import pandas as pd
from solana.rpc.async_api import AsyncClient


load_dotenv()
state = BackendState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global state
    url = os.getenv("RPC_URL")
    if not url:
        raise ValueError("RPC_URL environment variable is not set.")

    state.connection = AsyncClient(url)
    state.dc = DriftClient(
        state.connection,
        Wallet.dummy(),
        "mainnet",
        account_subscription=AccountSubscriptionConfig("cached"),
    )
    state.perp_map = MarketMap(
        MarketMapConfig(
            state.dc.program,
            MarketType.Perp(),
            MarketMapWebsocketConfig(),
            state.dc.connection,
        )
    )
    state.spot_map = MarketMap(
        MarketMapConfig(
            state.dc.program,
            MarketType.Spot(),
            MarketMapWebsocketConfig(),
            state.dc.connection,
        )
    )
    state.user_map = UserMap(UserMapConfig(state.dc, UserMapWebsocketConfig()))
    state.stats_map = UserStatsMap(UserStatsMapConfig(state.dc))
    state.vat = Vat(
        state.dc,
        state.user_map,
        state.stats_map,
        state.spot_map,
        state.perp_map,
    )

    print("Checking if cached vat exists")
    cached_vat_path = sorted(glob.glob("pickles/*"))
    if len(cached_vat_path) > 0:
        print("Loading cached vat")
        directory = cached_vat_path[-1]
        pickle_map = load_newest_files(directory)
        with waiting_for("unpickling"):
            await state.vat.unpickle(
                users_filename=pickle_map["usermap"],
                user_stats_filename=pickle_map["userstats"],
                spot_markets_filename=pickle_map["spot"],
                perp_markets_filename=pickle_map["perp"],
                spot_oracles_filename=pickle_map["spotoracles"],
                perp_oracles_filename=pickle_map["perporacles"],
            )
    else:
        print("No cached vat found")

    # with waiting_for("drift client"):
    #     await state.dc.subscribe()
    with waiting_for("subscriptions"):
        await gather(
            create_task(state.spot_map.subscribe()),
            create_task(state.perp_map.subscribe()),
            create_task(state.user_map.subscribe()),
            create_task(state.stats_map.subscribe()),
        )

    state.some_df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    state.ready = True
    print("Starting app")
    yield

    # Cleanup
    state.some_df = pd.DataFrame()
    state.ready = False
    await state.dc.unsubscribe()
    await state.connection.close()


app = FastAPI(lifespan=lifespan)
app.add_middleware(ReadinessMiddleware, state=state)


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/df")
async def get_df():
    return state.some_df.to_dict(orient="records")


@app.get("/users")
async def get_users():
    users = [user.user_public_key for user in state.user_map.values()]
    return users


@app.get("/pickle")
async def pickle():
    now = datetime.now()
    folder_name = now.strftime("vat-%Y-%m-%d-%H-%M-%S")
    if not os.path.exists("pickles"):
        os.makedirs("pickles")
    path = os.path.join("pickles", folder_name, "")

    os.makedirs(path, exist_ok=True)
    with waiting_for("pickling"):
        result = await state.vat.pickle(path)

    return {"result": result}


@app.get("/health")
async def health_check():
    return {"status": "healthy" if state.ready else "initializing"}
