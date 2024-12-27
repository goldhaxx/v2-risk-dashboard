import copy
from typing import List, Optional

from driftpy.accounts.cache import DriftClientCache
from driftpy.constants.numeric_constants import MARGIN_PRECISION, QUOTE_PRECISION
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


def get_user_metrics_for_asset_liability(
    x: DriftUser,
    margin_category: MarginCategory,
):
    """
    Returns a dictionary of the user's health, leverage, and other metrics,
    plus columns for four safety checks and the resulting Target Scale IAW.
    """

    # Basic existing metrics
    asset_value = x.get_spot_market_asset_value(None, margin_category) / QUOTE_PRECISION
    liability_value = (
        x.get_spot_market_liability_value(None, margin_category) / QUOTE_PRECISION
    )
    perp_liability = (
        x.get_total_perp_position_liability(margin_category) / QUOTE_PRECISION
    )
    unrealized_pnl = x.get_unrealized_pnl(True)
    net_spot_market_value = x.get_net_spot_market_value(None)
    net_usd_value = (net_spot_market_value + unrealized_pnl) / QUOTE_PRECISION

    metrics = {
        "user_key": x.user_public_key,
        "is_high_leverage": x.is_high_leverage_mode(),
        "leverage": x.get_leverage() / MARGIN_PRECISION,
        "upnl": unrealized_pnl / QUOTE_PRECISION,
        "net_usd_value": net_usd_value,
        "perp_liability": perp_liability,
        "spot_asset": asset_value,
        "spot_liability": liability_value,
    }

    # Existing health logic
    if margin_category == MarginCategory.INITIAL:
        metrics["health"] = get_init_health(x)
    else:
        metrics["health"] = x.get_health()

    # Collateral composition
    NUMBER_OF_SPOT = len(mainnet_spot_market_configs)
    NUMBER_OF_PERP = len(mainnet_perp_market_configs)
    metrics["net_v"] = get_collateral_composition(x, margin_category, NUMBER_OF_SPOT)
    metrics["net_p"] = get_perp_liab_composition(x, margin_category, NUMBER_OF_PERP)

    # -------------------------
    # NEW COLUMNS: Pass/Fail checks + Target Scale IAW
    # -------------------------
    #
    # For demonstration, we use placeholders or simplified calculations:
    # 1) On-Chain Liquidity Check
    #    - Placeholder for a Jupiter price impact. We simulate price_impact=0.05.
    #    - Maint asset weight is assumed 0.9 => if price_impact < (1 - 0.9)=0.1 => pass
    # 2) Effective Leverage (Spot Positions)
    #    - pass if user's "leverage" < (0.5 * 0.9)=0.45 (simple placeholder).
    # 3) Effective Leverage (Perp Positions)
    #    - pass if 1.0 <= user's "leverage" <= 2.0
    # 4) Excess Leverage Coverage (Perp Market Insurance)
    #    - pass if leverage <= 2.0 or if "excess coverage" is enough (placeholder).
    #    - We'll assume the "insurance_fund=5_000_000" and if user has (leverage-2)*whatever, coverage is pass if < insurance_fund.

    # 1) On-Chain Liquidity Check
    price_impact = 0.05  # placeholder
    pass_on_chain_liq = price_impact < (1 - 0.9)

    # 2) Effective Leverage (Spot)
    pass_spot_eff_lev = (metrics["leverage"] < 0.45)

    # 3) Effective Leverage (Perp)
    pass_perp_eff_lev = (1.0 <= metrics["leverage"] <= 2.0)

    # 4) Excess Leverage Coverage
    insurance_fund = 5_000_000  # placeholder
    # We'll assume "excess notional" is (net_usd_value - (net_usd_value / 2 if leverage>2 else 0)), purely for example
    # In reality, you'd handle each user's actual coverage logic.
    if metrics["leverage"] > 2.0:
        excess_notional = (metrics["leverage"] - 2.0) * asset_value
        pass_excess_lev_coverage = (excess_notional < insurance_fund)
    else:
        pass_excess_lev_coverage = True

    metrics["on_chain_liquidity_pass"] = "Pass" if pass_on_chain_liq else "Fail"
    metrics["spot_eff_lev_pass"] = "Pass" if pass_spot_eff_lev else "Fail"
    metrics["perp_eff_lev_pass"] = "Pass" if pass_perp_eff_lev else "Fail"
    metrics["excess_lev_coverage_pass"] = "Pass" if pass_excess_lev_coverage else "Fail"

    # If all pass => target_scale_iaw = 1.2 * net_usd_value
    # else => "N/A"
    if all([pass_on_chain_liq, pass_spot_eff_lev, pass_perp_eff_lev, pass_excess_lev_coverage]):
        metrics["target_scale_iaw"] = 1.2 * net_usd_value
    else:
        metrics["target_scale_iaw"] = "N/A"

    return metrics


def get_user_metrics_for_price_shock(
    x: DriftUser,
    margin_category: MarginCategory,
    oracle_cache: Optional[DriftClientCache] = None,
):
    """
    Returns a dictionary of the user's health, leverage, and other metrics.
    """
    if oracle_cache is not None:
        x.drift_client.account_subscriber.cache = oracle_cache

    asset_value = x.get_spot_market_asset_value(None, margin_category) / QUOTE_PRECISION
    liability_value = (
        x.get_spot_market_liability_value(None, margin_category) / QUOTE_PRECISION
    )
    perp_liability = (
        x.get_total_perp_position_liability(margin_category) / QUOTE_PRECISION
    )
    unrealized_pnl = x.get_unrealized_pnl(True)
    net_spot_market_value = x.get_net_spot_market_value(None)
    net_usd_value = (net_spot_market_value + unrealized_pnl) / QUOTE_PRECISION

    metrics_stable = {
        "user_key": x.user_public_key,
        "leverage": x.get_leverage() / MARGIN_PRECISION,
        "upnl": unrealized_pnl / QUOTE_PRECISION,
        "net_usd_value": net_usd_value,
    }
    metrics_unstable = {
        "perp_liability": perp_liability,
        "spot_asset": asset_value,
        "spot_liability": liability_value,
    }

    metrics = {
        **metrics_stable,
        **metrics_unstable,
    }

    if margin_category == MarginCategory.INITIAL:
        metrics["health"] = get_init_health(x)
    else:
        metrics["health"] = x.get_health()

    return metrics


def get_skipped_oracles(cov_matrix: Optional[str]) -> List[str]:
    """
    Determine which oracles to skip based on the cov_matrix parameter.
    """
    if cov_matrix is None:
        return []
    if "+" in cov_matrix:
        cov_matrix = cov_matrix.replace("+", " ")
    groups = {
        "sol only": ["SOL"],
        "sol lst only": ["mSOL", "jitoSOL", "bSOL"],
        "sol ecosystem only": ["PYTH", "JTO", "WIF", "JUP", "TNSR", "DRIFT"],
        "meme": ["WIF"],
        "wrapped only": ["wBTC", "wETH"],
        "stables only": ["USD"],
        "jlp only": ["JLP"],
    }
    if cov_matrix in groups:
        print("COV MATRIX found", cov_matrix)
        oracles = [
            str(x.oracle)
            for x in mainnet_spot_market_configs
            if x.symbol not in groups[cov_matrix]
        ]
        print("ORACLES", oracles)
        return oracles
    elif cov_matrix == "ignore stables":
        return [str(x.oracle) for x in mainnet_spot_market_configs if "USD" in x.symbol]
    else:
        return []


def calculate_leverages_for_asset_liability(
    user_values: list[DriftUser], maintenance_category: MarginCategory
):
    """
    Calculate the leverages for all users at a given maintenance category
    """
    return [
        get_user_metrics_for_asset_liability(x, maintenance_category)
        for x in user_values
    ]


def calculate_leverages_for_price_shock(
    user_values: list[DriftUser],
    maintenance_category: MarginCategory,
    oracle_cache: Optional[DriftClientCache] = None,
):
    """
    Calculate the leverages for all users at a given maintenance category
    """
    return [
        get_user_metrics_for_price_shock(x, maintenance_category, oracle_cache)
        for x in user_values
    ]


def get_user_leverages_for_asset_liability(user_map: UserMap):
    user_keys = list(user_map.user_map.keys())
    user_values = list(user_map.values())

    leverages_none = calculate_leverages_for_asset_liability(user_values, None)
    leverages_initial = calculate_leverages_for_asset_liability(
        user_values, MarginCategory.INITIAL
    )
    leverages_maintenance = calculate_leverages_for_asset_liability(
        user_values, MarginCategory.MAINTENANCE
    )
    return {
        "leverages_none": leverages_none,
        "leverages_initial": leverages_initial,
        "leverages_maintenance": leverages_maintenance,
        "user_keys": user_keys,
    }


def get_user_leverages_for_price_shock(
    slot: int,
    drift_client: DriftClient,
    user_map: UserMap,
    oracle_distortion: float = 0.1,
    oracle_group: Optional[str] = None,
    scenarios: int = 5,
):
    user_keys = list(user_map.user_map.keys())
    user_vals = list(user_map.values())

    print(f"User keys : {len(user_keys)}")
    new_oracles_dat_up = []
    new_oracles_dat_down = []
    skipped_oracles = get_skipped_oracles(oracle_group)

    for i in range(scenarios):
        new_oracles_dat_up.append({})
        new_oracles_dat_down.append({})

    print("Skipped oracles:", skipped_oracles)

    distorted_oracles = []
    cache_up = copy.deepcopy(drift_client.account_subscriber.cache)
    cache_down = copy.deepcopy(drift_client.account_subscriber.cache)

    for key, val in drift_client.account_subscriber.cache["oracle_price_data"].items():
        for i in range(scenarios):
            new_oracles_dat_up[i][key] = copy.deepcopy(val)
            new_oracles_dat_down[i][key] = copy.deepcopy(val)
        if oracle_group is not None and key in skipped_oracles:
            continue

        distorted_oracles.append(key)
        for i in range(scenarios):
            oracle_distort_up = max(1 + oracle_distortion * (i + 1), 1)
            oracle_distort_down = max(1 - oracle_distortion * (i + 1), 0)

            if isinstance(new_oracles_dat_up[i][key], OraclePriceData):
                new_oracles_dat_up[i][key].price *= oracle_distort_up
                new_oracles_dat_down[i][key].price *= oracle_distort_down
            else:
                new_oracles_dat_up[i][key].data.price *= oracle_distort_up
                new_oracles_dat_down[i][key].data.price *= oracle_distort_down

    leverages_none = calculate_leverages_for_price_shock(user_vals, None)
    leverages_up = []
    leverages_down = []

    for i in range(scenarios):
        cache_up["oracle_price_data"] = new_oracles_dat_up[i]
        cache_down["oracle_price_data"] = new_oracles_dat_down[i]
        leverages_up_i = calculate_leverages_for_price_shock(
            user_vals,
            None,
            cache_up,
        )
        leverages_down_i = calculate_leverages_for_price_shock(
            user_vals,
            None,
            cache_down,
        )
        leverages_up.append(leverages_up_i)
        leverages_down.append(leverages_down_i)

    return {
        "slot": slot,
        "leverages_none": leverages_none,
        "leverages_up": tuple(leverages_up),
        "leverages_down": tuple(leverages_down),
        "user_keys": user_keys,
        "distorted_oracles": distorted_oracles,
    }