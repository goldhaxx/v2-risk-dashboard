import asyncio
import glob
import hashlib
import json
import os
from typing import Callable, Dict, Optional

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
        if not request.url.path.startswith("/api"):
            return await call_next(request)

        current_pickle = self.state.current_pickle_path
        previous_pickle = self._get_previous_pickle()

        current_cache_key = self._generate_cache_key(request, current_pickle)
        current_cache_file = os.path.join(self.cache_dir, f"{current_cache_key}.json")

        if os.path.exists(current_cache_file):
            return self._serve_cached_response(current_cache_file, "Fresh")

        if previous_pickle:
            previous_cache_key = self._generate_cache_key(request, previous_pickle)
            previous_cache_file = os.path.join(
                self.cache_dir, f"{previous_cache_key}.json"
            )

            if os.path.exists(previous_cache_file):
                return await self._serve_stale_response(
                    previous_cache_file,
                    request,
                    call_next,
                    current_cache_key,
                    current_cache_file,
                )

        return await self._serve_miss_response(
            request, call_next, current_cache_key, current_cache_file
        )

    def _serve_cached_response(self, cache_file: str, cache_status: str):
        print(f"Serving {cache_status.lower()} data")
        with open(cache_file, "r") as f:
            response_data = json.load(f)

        content = json.dumps(response_data["content"]).encode("utf-8")
        headers = {
            k: v
            for k, v in response_data["headers"].items()
            if k.lower() != "content-length"
        }
        headers["Content-Length"] = str(len(content))
        headers["X-Cache-Status"] = cache_status

        return Response(
            content=content,
            status_code=response_data["status_code"],
            headers=headers,
            media_type="application/json",
        )

    async def _serve_stale_response(
        self,
        cache_file: str,
        request: BackendRequest,
        call_next: Callable,
        current_cache_key: str,
        current_cache_file: str,
    ):
        response = self._serve_cached_response(cache_file, "Stale")
        background_tasks = BackgroundTasks()
        background_tasks.add_task(
            self._fetch_and_cache,
            request,
            call_next,
            current_cache_key,
            current_cache_file,
        )
        response.background = background_tasks
        return response

    async def _serve_miss_response(
        self,
        request: BackendRequest,
        call_next: Callable,
        cache_key: str,
        cache_file: str,
    ):
        print(f"No data available for {request.url.path}")
        background_tasks = BackgroundTasks()
        background_tasks.add_task(
            self._fetch_and_cache,
            request,
            call_next,
            cache_key,
            cache_file,
        )
        content = json.dumps({"result": "miss"}).encode("utf-8")

        response = Response(
            content=content,
            status_code=200,
            headers={"X-Cache-Status": "Miss", "Content-Length": str(len(content))},
            media_type="application/json",
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

                    body_content = json.loads(response_body.decode())
                    response_data = {
                        "content": body_content,
                        "status_code": response.status_code,
                        "headers": {
                            k: v
                            for k, v in response.headers.items()
                            if k.lower() != "content-length"
                        },
                    }

                    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
                    with open(cache_file, "w") as f:
                        json.dump(response_data, f)
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

    def _get_previous_pickle(self) -> Optional[str]:
        print("Attempting previous pickle")
        _pickle_paths = glob.glob(f"{self.state.current_pickle_path}/../*")
        pickle_paths = sorted([os.path.realpath(dir) for dir in _pickle_paths])
        print("Pickle paths: ", pickle_paths)

        if len(pickle_paths) > 1:
            previous_pickle_path = pickle_paths[-2]
            print("Previous pickle: ", previous_pickle_path)
            return previous_pickle_path

        print("No previous pickle found")
        return None
