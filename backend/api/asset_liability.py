from backend.state import BackendRequest
from backend.state import BackendState
from backend.utils.matrix import get_matrix
from backend.utils.waiting_for import waiting_for
from driftpy.pickle.vat import Vat
from fastapi import APIRouter


router = APIRouter()


async def get_asset_liability_matrix(
    snapshot_path: str, vat: Vat, mode: int, perp_market_index: int
) -> dict:
    print("==> Getting asset liability matrix...")
    res, df = await get_matrix(vat, mode, perp_market_index)
    res_dict = res.to_dict()
    df_dict = df.to_dict()
    print("==> Asset liability matrix fetched")

    return {
        "res": res_dict,
        "df": df_dict,
    }


@router.get("/matrix/{mode}/{perp_market_index}")
async def get_asset_liability_matrix(
    request: BackendRequest, mode: int, perp_market_index: int
):
    return await get_asset_liability_matrix(
        request.state.current_pickle_path,
        request.state.backend_state.vat,
        mode,
        perp_market_index,
    )
