import hashlib
import os
import pickle

from backend.state import BackendRequest
from backend.state import BackendState
from fastapi import HTTPException
from fastapi import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class CacheMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, state: BackendState, cache_dir: str = "cache"):
        super().__init__(app)
        self.state = state
        self.cache_dir = cache_dir
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

    async def dispatch(self, request: BackendRequest, call_next):
        if not request.url.path.startswith("/api"):
            return await call_next(request)
        if self.state.current_pickle_path == "bootstrap":
            return await call_next(request)

        cache_key = self._generate_cache_key(request)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.pkl")

        if os.path.exists(cache_file):
            print(f"Cache hit for {request.url.path}")
            with open(cache_file, "rb") as f:
                response_data = pickle.load(f)
                return Response(
                    content=response_data["content"],
                    status_code=response_data["status_code"],
                    headers=response_data["headers"],
                )

        print(f"Cache miss for {request.url.path}")
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

            return Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
            )

        return response

    def _generate_cache_key(self, request: BackendRequest) -> str:
        current_pickle_path = self.state.current_pickle_path
        hash_input = f"{current_pickle_path}:{request.method}:{request.url.path}:{request.url.query}"
        print("Hash input: ", hash_input)
        return hashlib.md5(hash_input.encode()).hexdigest()
