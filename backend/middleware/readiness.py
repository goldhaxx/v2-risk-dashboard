from backend.state import BackendState
from fastapi import HTTPException
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class ReadinessMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, state: BackendState):
        super().__init__(app)
        self.state = state

    async def dispatch(self, request: Request, call_next):
        if not self.state.ready and request.url.path != "/health":
            raise HTTPException(status_code=503, detail="Service is not ready")
        response = await call_next(request)
        return response
