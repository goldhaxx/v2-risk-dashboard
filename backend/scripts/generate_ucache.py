import asyncio
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
import glob
from itertools import islice
import json
import multiprocessing
import os
from typing import Optional

from backend.api.asset_liability import _get_asset_liability_matrix
from backend.api.price_shock import _get_price_shock
from backend.state import BackendState
from backend.utils.waiting_for import waiting_for
from dotenv import load_dotenv
from fastapi.responses import JSONResponse


def chunk_list(lst, n):
    """Split list into n chunks"""
    size = len(lst)
    chunk_size = (size + n - 1) // n
    it = iter(lst)
    return [list(islice(it, chunk_size)) for _ in range(n)]


@dataclass
class Endpoint:
    endpoint: str
    params: dict


def process_multiple_endpoints(state_pickle_path: str, endpoints: list[Endpoint]):
    """Process a single endpoint in its own process"""
    state = BackendState()
    state.initialize(os.getenv("RPC_URL"))
    asyncio.run(state.load_pickle_snapshot(state_pickle_path))

    results = []

    for endpoint_object in endpoints:
        endpoint = endpoint_object.endpoint
        query_params = endpoint_object.params

        class MockRequest:
            def __init__(self, path: str, query_params: dict):
                self.method = "GET"
                query_string = "&".join([f"{k}={v}" for k, v in query_params.items()])
                self.url = type("URL", (), {"path": path, "query": query_string})()

        request = MockRequest(f"/api/{endpoint}", query_params)

        async def mock_call_next(request):
            if endpoint == "price-shock/usermap":
                content = await _get_price_shock(
                    state.vat,
                    state.dc,
                    oracle_distortion=query_params["oracle_distortion"],
                    asset_group=query_params["asset_group"],
                    n_scenarios=query_params["n_scenarios"],
                )

            if endpoint == "asset-liability/matrix":
                content = await _get_asset_liability_matrix(
                    state.last_oracle_slot,
                    state.vat,
                    mode=query_params["mode"],
                    perp_market_index=query_params["perp_market_index"],
                )

            return JSONResponse(content=content)

        print(request.url.path)
        print(request.url.query)

        ucache_key = f"{request.method}{request.url.path}"
        if request.url.query:
            safe_query = request.url.query.replace("&", "_").replace("=", "-")
            ucache_key = f"{ucache_key}__{safe_query}"
        ucache_key = ucache_key.replace("/", "_")
        ucache_file = os.path.join("ucache", f"{ucache_key}.json")

        async def run_request():
            response = await mock_call_next(request)
            if response.status_code == 200:
                response_data = {
                    "content": json.loads(response.body.decode()),
                    "status_code": response.status_code,
                    "headers": {"content-type": "application/json"},
                }

                with open(ucache_file, "w") as f:
                    json.dump(response_data, f)
                return f"Generated cache for {endpoint}"

        asyncio.run(run_request())

    return results


async def generate_ucache(state: BackendState, endpoints: list[Endpoint]):
    """Generate ucache files by splitting endpoints across processes"""
    ucache_dir = "ucache"
    if not os.path.exists(ucache_dir):
        os.makedirs(ucache_dir)

    state_pickle_path = sorted(glob.glob("pickles/*"))[-1]
    # n_processes = max(1, multiprocessing.cpu_count() - 1)
    n_processes = 1
    with ProcessPoolExecutor(max_workers=n_processes) as executor:
        futures = [
            executor.submit(process_multiple_endpoints, state_pickle_path, list(chunk))
            for chunk in chunk_list(endpoints, n_processes)
        ]

        for future in futures:
            for result in future.result():
                print(result)


async def main():
    load_dotenv()
    state = BackendState()
    state.initialize(os.getenv("RPC_URL"))
    use_snapshot = True

    # if use_snapshot:
    #     cached_vat_path = sorted(glob.glob("pickles/*"))
    #     print(f"Loading cached vat from {cached_vat_path[-1]}")
    #     await state.load_pickle_snapshot(cached_vat_path[-1])
    # else:
    #     await state.bootstrap()
    #     await state.take_pickle_snapshot()

    endpoints = [
        # Endpoint(
        #     endpoint="price-shock/usermap",
        #     params={
        #         "asset_group": "ignore+stables",
        #         "oracle_distortion": 0.05,
        #         "n_scenarios": 5,
        #     },
        # ),
        Endpoint(
            endpoint="asset-liability/matrix",
            params={"mode": 0, "perp_market_index": 0},
        ),
        # Endpoint(
        #     endpoint="asset-liability/matrix",
        #     params={"mode": 0, "perp_market_index": 2},
        # ),
        # Endpoint(
        #     endpoint="asset-liability/matrix",
        #     params={"mode": 0, "perp_market_index": 3},
        # ),
        # Endpoint(
        #     endpoint="asset-liability/matrix",
        #     params={"mode": 0, "perp_market_index": 4},
        # ),
        # Endpoint(
        #     endpoint="asset-liability/matrix",
        #     params={"mode": 2, "perp_market_index": 30},
        # ),
    ]

    await generate_ucache(state, endpoints)


if __name__ == "__main__":
    asyncio.run(main())