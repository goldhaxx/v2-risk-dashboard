import functools
from typing import Optional

from backend.state import BackendRequest
from backend.state import BackendState
from backend.utils.user_metrics import get_user_leverages_for_price_shock
from driftpy.drift_client import DriftClient
from driftpy.pickle.vat import Vat
from fastapi import APIRouter


router = APIRouter()


@functools.lru_cache()
async def _get_price_shock(
    snapshot_path: str,
    vat: Vat,
    drift_client: DriftClient,
    oracle_distortion: float = 0.1,
    asset_group: Optional[str] = None,
    n_scenarios: int = 5,
) -> dict:
    return get_user_leverages_for_price_shock(
        drift_client,
        vat.users,
        oracle_distortion,
        asset_group,
        n_scenarios,
    )


@router.get("/usermap")
async def get_price_shock(
    request: BackendRequest,
    oracle_distortion: float = 0.1,
    asset_group: Optional[str] = None,
    n_scenarios: int = 5,
):
    return await _get_price_shock(
        request.state.backend_state.current_pickle_path,
        request.state.backend_state.vat,
        request.state.backend_state.dc,
        oracle_distortion,
        asset_group,
        n_scenarios,
    )
