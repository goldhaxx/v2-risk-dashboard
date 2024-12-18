from fastapi import APIRouter, BackgroundTasks

from backend.state import BackendRequest, BackendState

router = APIRouter()


@router.get("/pickle")
async def pickle(request: BackendRequest, background_tasks: BackgroundTasks):
    backend_state: BackendState = request.state.backend_state
    background_tasks.add_task(backend_state.take_pickle_snapshot)
    return {"result": "background task added"}
