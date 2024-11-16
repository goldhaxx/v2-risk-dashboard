import functools

from backend.state import BackendRequest
from backend.state import BackendState
from fastapi import APIRouter
from fastapi.responses import FileResponse


router = APIRouter()


@router.get("/{file_name}")
async def get_ucache_file(request: BackendRequest, file_name: str):
    print("Backend: Serving from local cache")
    return FileResponse(f"ucache/{file_name}")
