from backend.state import BackendRequest
from backend.state import BackendState
from backend.utils.matrix import get_matrix
from backend.utils.user_metrics import get_usermap_df
from driftpy.drift_client import DriftClient
from driftpy.pickle.vat import Vat
from fastapi import APIRouter


router = APIRouter()


@router.get("/matrix/{mode}/{perp_market_index}")
async def get_asset_liability_matrix(
    request: BackendRequest, mode: int, perp_market_index: int
):
    backend_state: BackendState = request.state.backend_state
    vat: Vat = backend_state.vat
    drift_client: DriftClient = backend_state.dc

    res, df = await get_matrix(drift_client, vat, mode, perp_market_index)

    return {
        "res": res.to_dict(),
        "df": df.to_dict(),
    }
