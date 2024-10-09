from backend.state import BackendRequest
from backend.state import BackendState
from backend.utils.matrix import get_matrix
from backend.utils.waiting_for import waiting_for
from driftpy.pickle.vat import Vat
from fastapi import APIRouter


router = APIRouter()


@router.get("/matrix/{mode}/{perp_market_index}")
async def get_asset_liability_matrix(
    request: BackendRequest, mode: int, perp_market_index: int
):
    backend_state: BackendState = request.state.backend_state
    vat: Vat = backend_state.vat

    with waiting_for("Getting asset liability matrix"):
        res, df = await get_matrix(vat, mode, perp_market_index)

    return {
        "res": res.to_dict(),
        "df": df.to_dict(),
    }
