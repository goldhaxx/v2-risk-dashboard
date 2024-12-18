from fastapi import APIRouter
from fastapi.responses import FileResponse

from backend.state import BackendRequest

router = APIRouter()


@router.get("/{file_name}")
async def get_ucache_file(request: BackendRequest, file_name: str):
    print("Backend: Serving from local cache")
    return FileResponse(f"ucache/{file_name}")
