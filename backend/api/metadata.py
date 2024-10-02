from backend.state import BackendRequest
from backend.state import BackendState
from fastapi import APIRouter


router = APIRouter()


@router.get("/")
def get_metadata(request: BackendRequest):
    backend_state: BackendState = request.state.backend_state
    return {
        "pickle_file": backend_state.current_pickle_path,
        "last_oracle_slot": backend_state.vat.register_oracle_slot,
    }
