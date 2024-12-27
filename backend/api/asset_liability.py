from driftpy.pickle.vat import Vat
from fastapi import APIRouter

from backend.state import BackendRequest
from backend.utils.matrix import get_matrix

router = APIRouter()


async def _get_asset_liability_matrix(
    slot: int,
    vat: Vat,
    mode: int,
    perp_market_index: int,
    high_leverage_only: bool = False,
) -> dict:
    print("==> Getting asset liability matrix...")
    df = await get_matrix(vat, mode, perp_market_index)
    
    if high_leverage_only:
        # Filter for only high leverage mode users if requested
        df = df[df["is_high_leverage"]]
    
    df_dict = df.to_dict()
    print("==> Asset liability matrix fetched")

    return {
        "slot": slot,
        "df": df_dict,
    }


@router.get("/matrix")
async def get_asset_liability_matrix(
    request: BackendRequest, 
    mode: int, 
    perp_market_index: int,
    high_leverage_only: bool = False
):
    return await _get_asset_liability_matrix(
        request.state.backend_state.last_oracle_slot,
        request.state.backend_state.vat,
        mode,
        perp_market_index,
        high_leverage_only
    )
