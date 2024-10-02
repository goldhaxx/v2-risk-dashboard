from backend.state import BackendRequest
from driftpy.constants import BASE_PRECISION
from driftpy.constants import PRICE_PRECISION
from driftpy.pickle.vat import Vat
from fastapi import APIRouter


router = APIRouter()


@router.get("/liquidation-curve/{market_index}")
def get_liquidation_curve(request: BackendRequest, market_index: int):
    vat: Vat = request.state.backend_state.vat
    liquidations_long: list[tuple[float, float]] = []
    liquidations_short: list[tuple[float, float]] = []
    market_price = vat.perp_oracles.get(market_index)
    market_price_ui = market_price.price / PRICE_PRECISION
    for user in vat.users.user_map.values():
        perp_position = user.get_perp_position(market_index)
        if perp_position is not None:
            liquidation_price = user.get_perp_liq_price(market_index)
            if liquidation_price is not None:
                liquidation_price_ui = liquidation_price / PRICE_PRECISION
                position_size = abs(perp_position.base_asset_amount) / BASE_PRECISION
                position_notional = position_size * market_price_ui
                is_zero = round(position_notional) == 0
                is_short = perp_position.base_asset_amount < 0
                is_long = perp_position.base_asset_amount > 0
                if is_zero:
                    continue
                if is_short and liquidation_price_ui > market_price_ui:
                    liquidations_short.append((liquidation_price_ui, position_notional))
                elif is_long and liquidation_price_ui < market_price_ui:
                    liquidations_long.append((liquidation_price_ui, position_notional))
                else:
                    pass

    liquidations_long.sort(key=lambda x: x[0])
    liquidations_short.sort(key=lambda x: x[0])

    return {
        "liquidations_long": liquidations_long,
        "liquidations_short": liquidations_short,
        "market_price_ui": market_price_ui,
    }
