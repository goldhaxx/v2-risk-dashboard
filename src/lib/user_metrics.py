import copy
from typing import List, Optional

from driftpy.constants.numeric_constants import MARGIN_PRECISION
from driftpy.constants.numeric_constants import QUOTE_PRECISION
from driftpy.constants.perp_markets import mainnet_perp_market_configs
from driftpy.constants.spot_markets import mainnet_spot_market_configs
from driftpy.drift_client import DriftClient
from driftpy.drift_user import DriftUser
from driftpy.math.margin import MarginCategory
from driftpy.types import OraclePriceData
from driftpy.user_map.user_map import UserMap


def get_init_health(user: DriftUser):
    """
    Returns the initial health of the user.
    """
    if user.is_being_liquidated():
        return 0

    total_collateral = user.get_total_collateral(MarginCategory.INITIAL)
    maintenance_margin_req = user.get_margin_requirement(MarginCategory.INITIAL)

    if maintenance_margin_req == 0 and total_collateral >= 0:
        return 100
    elif total_collateral <= 0:
        return 0
    else:
        return round(
            min(100, max(0, (1 - maintenance_margin_req / total_collateral) * 100))
        )


def comb_asset_liab(a_l_tup):
    return a_l_tup[0] - a_l_tup[1]


def get_collateral_composition(x: DriftUser, margin_category, n):
    net_v = {
        i: comb_asset_liab(
            x.get_spot_market_asset_and_liability_value(i, margin_category)
        )
        / QUOTE_PRECISION
        for i in range(n)
    }
    return net_v


def get_perp_liab_composition(x: DriftUser, margin_category, n):
    net_p = {
        i: x.get_perp_market_liability(i, margin_category, signed=True)
        / QUOTE_PRECISION
        for i in range(n)
    }
    return net_p


def get_user_metrics(x: DriftUser, margin_category: MarginCategory, all_fields=False):
    """
    Returns a dictionary of the user's health, leverage, and other metrics.
    """
    NUMBER_OF_SPOT = len(mainnet_spot_market_configs)
    NUMBER_OF_PERP = len(mainnet_perp_market_configs)

    metrics = {
        "user_key": x.user_public_key,
        "leverage": x.get_leverage() / MARGIN_PRECISION,
        "perp_liability": x.get_total_perp_position_liability(margin_category)
        / QUOTE_PRECISION,
        "spot_asset": x.get_spot_market_asset_value(None, margin_category)
        / QUOTE_PRECISION,
        "spot_liability": x.get_spot_market_liability_value(None, margin_category)
        / QUOTE_PRECISION,
        "upnl": x.get_unrealized_pnl(True) / QUOTE_PRECISION,
        "net_usd_value": (
            x.get_net_spot_market_value(None) + x.get_unrealized_pnl(True)
        )
        / QUOTE_PRECISION,
    }
    metrics["health"] = (
        get_init_health(x)
        if margin_category == MarginCategory.INITIAL
        else x.get_health()
    )

    if all_fields:
        metrics["net_v"] = get_collateral_composition(
            x, margin_category, NUMBER_OF_SPOT
        )
        metrics["net_p"] = get_perp_liab_composition(x, margin_category, NUMBER_OF_PERP)

    return metrics


def get_skipped_oracles(cov_matrix: Optional[str]) -> List[str]:
    """
    Determine which oracles to skip based on the cov_matrix parameter.
    """
    groups = {
        "sol only": ["SOL"],
        "sol lst only": ["mSOL", "jitoSOL", "bSOL"],
        "sol ecosystem only": ["PYTH", "JTO", "WIF", "JUP", "TNSR", "DRIFT"],
        "meme": ["WIF"],
        "wrapped only": ["wBTC", "wETH"],
        "stables only": ["USD"],
    }
    if cov_matrix in groups:
        return [
            str(x.oracle)
            for x in mainnet_spot_market_configs
            if x.symbol not in groups[cov_matrix]
        ]
    elif cov_matrix == "ignore stables":
        return [str(x.oracle) for x in mainnet_spot_market_configs if "USD" in x.symbol]
    else:
        return []


def calculate_leverages(
    user_vals: list[DriftUser], maintenance_category: MarginCategory
):
    """
    Calculate the leverages for all users at a given maintenance category
    """
    return list(get_user_metrics(x, maintenance_category) for x in user_vals)


async def get_usermap_df(
    _drift_client: DriftClient,
    user_map: UserMap,
    mode: str,
    oracle_distortion: float = 0.1,
    only_one_index: Optional[str] = None,
    cov_matrix: Optional[str] = None,
    n_scenarios: int = 5,
):
    user_keys = list(user_map.user_map.keys())
    user_vals = list(user_map.values())

    skipped_oracles = get_skipped_oracles(cov_matrix)

    if only_one_index is None or len(only_one_index) > 12:
        only_one_index_key = only_one_index
    else:
        only_one_index_key = (
            [
                str(x.oracle)
                for x in mainnet_perp_market_configs
                if x.base_asset_symbol == only_one_index
            ]
            + [
                str(x.oracle)
                for x in mainnet_spot_market_configs
                if x.symbol == only_one_index
            ]
        )[0]

    if mode == "margins":
        leverages_none = calculate_leverages(user_vals, None)
        leverages_initial = calculate_leverages(user_vals, MarginCategory.INITIAL)
        leverages_maintenance = calculate_leverages(
            user_vals, MarginCategory.MAINTENANCE
        )
        return (leverages_none, leverages_initial, leverages_maintenance), user_keys
    else:
        num_entrs = n_scenarios
        new_oracles_dat_up = []
        new_oracles_dat_down = []

        for i in range(num_entrs):
            new_oracles_dat_up.append({})
            new_oracles_dat_down.append({})

        assert len(new_oracles_dat_down) == num_entrs
        print("skipped oracles:", skipped_oracles)
        distorted_oracles = []
        cache_up = copy.deepcopy(_drift_client.account_subscriber.cache)
        cache_down = copy.deepcopy(_drift_client.account_subscriber.cache)
        for i, (key, val) in enumerate(
            _drift_client.account_subscriber.cache["oracle_price_data"].items()
        ):
            for i in range(num_entrs):
                new_oracles_dat_up[i][key] = copy.deepcopy(val)
                new_oracles_dat_down[i][key] = copy.deepcopy(val)
            if cov_matrix is not None and key in skipped_oracles:
                continue
            if only_one_index is None or only_one_index_key == key:
                distorted_oracles.append(key)
                for i in range(num_entrs):
                    oracle_distort_up = max(1 + oracle_distortion * (i + 1), 1)
                    oracle_distort_down = max(1 - oracle_distortion * (i + 1), 0)

                    if isinstance(new_oracles_dat_up[i][key], OraclePriceData):
                        new_oracles_dat_up[i][key].price *= oracle_distort_up
                        new_oracles_dat_down[i][key].price *= oracle_distort_down
                    else:
                        new_oracles_dat_up[i][key].data.price *= oracle_distort_up
                        new_oracles_dat_down[i][key].data.price *= oracle_distort_down

        levs_none = calculate_leverages(user_vals, None)
        levs_up = []
        levs_down = []

        for i in range(num_entrs):
            cache_up["oracle_price_data"] = new_oracles_dat_up[i]
            cache_down["oracle_price_data"] = new_oracles_dat_down[i]
            levs_up_i = list(get_user_metrics(x, None, cache_up) for x in user_vals)
            levs_down_i = list(get_user_metrics(x, None, cache_down) for x in user_vals)
            levs_up.append(levs_up_i)
            levs_down.append(levs_down_i)

        return (
            (levs_none, tuple(levs_up), tuple(levs_down)),
            user_keys,
            distorted_oracles,
        )
