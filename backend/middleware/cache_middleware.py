import asyncio
import hashlib
import os
import pickle
from typing import Any, Callable, Dict, Optional

from backend.state import BackendRequest
from backend.state import BackendState
from fastapi import BackgroundTasks
from fastapi import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class CacheMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, state: BackendState, cache_dir: str = "cache"):
        super().__init__(app)
        self.state = state
        self.cache_dir = cache_dir
        self.revalidation_locks: Dict[str, asyncio.Lock] = {}
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

    async def dispatch(self, request: BackendRequest, call_next: Callable):
        if request.url.path.startswith("/api/snapshot"):
            return await call_next(request)
        if request.url.path.startswith("/api/price_shock"):
            return await call_next(request)
        if not request.url.path.startswith("/api"):
            return await call_next(request)
        if self.state.current_pickle_path == "bootstrap":
            return await call_next(request)

        current_pickle = self.state.current_pickle_path
        previous_pickle = self._get_previous_pickle(current_pickle)

        # Try to serve data from the current (latest) pickle first
        current_cache_key = self._generate_cache_key(request, current_pickle)
        current_cache_file = os.path.join(self.cache_dir, f"{current_cache_key}.pkl")

        if os.path.exists(current_cache_file):
            print(f"Serving latest data for {request.url.path}")
            with open(current_cache_file, "rb") as f:
                response_data = pickle.load(f)

            return Response(
                content=response_data["content"],
                status_code=response_data["status_code"],
                headers=dict(response_data["headers"], **{"X-Cache-Status": "Fresh"}),
            )

        # If no data in current pickle, try the previous pickle
        if previous_pickle:
            previous_cache_key = self._generate_cache_key(request, previous_pickle)
            previous_cache_file = os.path.join(
                self.cache_dir, f"{previous_cache_key}.pkl"
            )

            if os.path.exists(previous_cache_file):
                print(f"Serving stale data for {request.url.path}")
                with open(previous_cache_file, "rb") as f:
                    response_data = pickle.load(f)

                # Prepare background task
                background_tasks = BackgroundTasks()
                background_tasks.add_task(
                    self._fetch_and_cache,
                    request,
                    call_next,
                    current_cache_key,
                    current_cache_file,
                )

                response = Response(
                    content=response_data["content"],
                    status_code=response_data["status_code"],
                    headers=dict(
                        response_data["headers"], **{"X-Cache-Status": "Stale"}
                    ),
                )
                response.background = background_tasks
                return response

        # If no data available, return an empty response and fetch fresh data in the background
        print(f"No data available for {request.url.path}")
        background_tasks = BackgroundTasks()
        background_tasks.add_task(
            self._fetch_and_cache,
            request,
            call_next,
            current_cache_key,
            current_cache_file,
        )

        # Return an empty response immediately
        response = Response(
            content='{"result": "miss"}',
            status_code=200,  # No Content
            headers={"X-Cache-Status": "Miss"},
        )
        response.background = background_tasks
        return response

    async def _fetch_and_cache(
        self,
        request: BackendRequest,
        call_next: Callable,
        cache_key: str,
        cache_file: str,
    ):
        if cache_key not in self.revalidation_locks:
            self.revalidation_locks[cache_key] = asyncio.Lock()

        async with self.revalidation_locks[cache_key]:
            try:
                response = await call_next(request)

                if response.status_code == 200:
                    response_body = b""
                    async for chunk in response.body_iterator:
                        response_body += chunk
                    response_data = {
                        "content": response_body,
                        "status_code": response.status_code,
                        "headers": dict(response.headers),
                    }

                    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
                    with open(cache_file, "wb") as f:
                        pickle.dump(response_data, f)
                    print(f"Cached fresh data for {request.url.path}")
                else:
                    print(
                        f"Failed to cache data for {request.url.path}. Status code: {response.status_code}"
                    )
            except Exception as e:
                print(f"Error in background task for {request.url.path}: {str(e)}")

    def _generate_cache_key(self, request: BackendRequest, pickle_path: str) -> str:
        hash_input = (
            f"{pickle_path}:{request.method}:{request.url.path}:{request.url.query}"
        )
        print("Hash input: ", hash_input)
        return hashlib.md5(hash_input.encode()).hexdigest()

    def _get_previous_pickle(self, current_pickle: str) -> Optional[str]:
        print("Attempting previous pickle")
        pickle_dir = os.path.dirname(current_pickle)
        pickles = sorted(
            [f for f in os.listdir(pickle_dir)],
            key=lambda x: os.path.getmtime(os.path.join(pickle_dir, x)),
            reverse=True,
        )

        if len(pickles) > 1:
            print("Previous pickle: ", os.path.join(pickle_dir, pickles[1]))
            return os.path.join(pickle_dir, pickles[1])

        print("No previous pickle found")
        return None
