from contextlib import asynccontextmanager
import glob
import os

from backend.api import asset_liability
from backend.api import health
from backend.api import liquidation
from backend.api import metadata
from backend.api import price_shock
from backend.middleware.cache_middleware import CacheMiddleware
from backend.middleware.readiness import ReadinessMiddleware
from backend.state import BackendState
from dotenv import load_dotenv
from fastapi import BackgroundTasks
from fastapi import FastAPI
import pandas as pd


load_dotenv()
state = BackendState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    url = os.getenv("RPC_URL")
    if not url:
        raise ValueError("RPC_URL environment variable is not set.")
    global state
    state.initialize(url)

    print("Checking if cached vat exists")
    cached_vat_path = sorted(glob.glob("pickles/*"))
    if len(cached_vat_path) > 0:
        print("Loading cached vat")
        await state.load_pickle_snapshot(cached_vat_path[-1])
    else:
        print("No cached vat found, bootstrapping")
        await state.bootstrap()

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
app.add_middleware(CacheMiddleware, state=state, cache_dir="cache")

app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(metadata.router, prefix="/api/metadata", tags=["metadata"])
app.include_router(liquidation.router, prefix="/api/liquidation", tags=["liquidation"])
app.include_router(price_shock.router, prefix="/api/price-shock", tags=["price-shock"])
app.include_router(
    asset_liability.router, prefix="/api/asset-liability", tags=["asset-liability"]
)


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/pickle")
async def pickle(background_tasks: BackgroundTasks):
    background_tasks.add_task(state.take_pickle_snapshot)
    return {"result": "background task added"}
