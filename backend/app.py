from contextlib import asynccontextmanager
import glob
import os
import shutil

from backend.api import asset_liability
from backend.api import health
from backend.api import liquidation
from backend.api import metadata
from backend.api import price_shock
from backend.api import snapshot
from backend.middleware.cache_middleware import CacheMiddleware
from backend.middleware.readiness import ReadinessMiddleware
from backend.state import BackendState
from backend.utils.repeat_every import repeat_every
from dotenv import load_dotenv
from fastapi import BackgroundTasks
from fastapi import FastAPI
from fastapi.testclient import TestClient


load_dotenv()
state = BackendState()


@repeat_every(seconds=60 * 15, wait_first=True)
async def repeatedly_retake_snapshot(state: BackendState) -> None:
    await state.take_pickle_snapshot()


def clean_cache(state: BackendState) -> None:
    if not os.path.exists("pickles"):
        print("pickles folder does not exist")
        return

    pickles = glob.glob("pickles/*")

    # check for pickle folders with less than 4 files (error in write)
    incomplete_pickles = []
    for pickle in pickles:
        if len(glob.glob(f"{pickle}/*")) < 4:
            incomplete_pickles.append(pickle)

    for incomplete_pickle in incomplete_pickles:
        print(f"deleting {incomplete_pickle}")
        shutil.rmtree(incomplete_pickle)

    pickles = glob.glob("pickles/*")

    if len(pickles) > 5:
        print("pickles folder has more than 5 pickles, deleting old ones")
        pickles.sort(key=os.path.getmtime)
        for pickle in pickles[:-5]:
            print(f"deleting {pickle}")
            shutil.rmtree(pickle)

    cache_files = glob.glob("cache/*")
    if len(cache_files) > 35:
        print("cache folder has more than 35 files, deleting old ones")
        cache_files.sort(key=os.path.getmtime)
        for cache_file in cache_files[:-35]:
            print(f"deleting {cache_file}")
            os.remove(cache_file)


@repeat_every(seconds=60 * 8, wait_first=True)
async def repeatedly_clean_cache(state: BackendState) -> None:
    clean_cache(state)


@asynccontextmanager
async def lifespan(app: FastAPI):
    url = os.getenv("RPC_URL")
    if not url:
        raise ValueError("RPC_URL environment variable is not set.")
    global state
    state.initialize(url)

    print("Checking if cached vat exists")
    clean_cache(state)
    cached_vat_path = sorted(glob.glob("pickles/*"))
    if len(cached_vat_path) > 0:
        print("Loading cached vat")
        await state.load_pickle_snapshot(cached_vat_path[-1])
        await repeatedly_clean_cache(state)
        await repeatedly_retake_snapshot(state)
    else:
        print("No cached vat found, bootstrapping")
        await state.bootstrap()
        await state.take_pickle_snapshot()
        await repeatedly_clean_cache(state)
        await repeatedly_retake_snapshot(state)
    state.ready = True
    print("Starting app")
    yield

    # Cleanup
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
app.include_router(snapshot.router, prefix="/api/snapshot", tags=["snapshot"])


# NOTE: All other routes should be in /api/* within the /api folder. Routes outside of /api are not exposed in k8s
@app.get("/")
async def root():
    return {"message": "risk dashboard backend is online"}
