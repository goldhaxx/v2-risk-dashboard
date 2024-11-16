import functools

from backend.state import BackendRequest
from backend.state import BackendState
from backend.utils.matrix import get_matrix
from backend.utils.waiting_for import waiting_for
from driftpy.pickle.vat import Vat
from fastapi import APIRouter


router = APIRouter()


async def _get_asset_liability_matrix(
    slot: int,
    vat: Vat,
    mode: int,
    perp_market_index: int,
) -> dict:
    print("==> Getting asset liability matrix...")
    res, df = await get_matrix(vat, mode, perp_market_index)
    res_dict = res.to_dict()
    df_dict = df.to_dict()
    print("==> Asset liability matrix fetched")

    return {
        "slot": slot,
        "res": res_dict,
        "df": df_dict,
    }


@router.get("/matrix")
async def get_asset_liability_matrix(
    request: BackendRequest, mode: int, perp_market_index: int
):
    return await _get_asset_liability_matrix(
        request.state.backend_state.last_oracle_slot,
        request.state.backend_state.vat,
        mode,
        perp_market_index,
    )
