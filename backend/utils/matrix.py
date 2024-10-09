from backend.utils.user_metrics import get_user_leverages_for_asset_liability
from driftpy.constants.spot_markets import mainnet_spot_market_configs
from driftpy.drift_client import DriftClient
from driftpy.pickle.vat import Vat
import pandas as pd


async def get_matrix(
    vat: Vat,
    mode: int = 0,
    perp_market_index: int = 0,
):
    NUMBER_OF_SPOT = len(mainnet_spot_market_configs)

    res = get_user_leverages_for_asset_liability(vat.users)
    levs_none = res["leverages_none"]
    levs_init = res["leverages_initial"]
    levs_maint = res["leverages_maintenance"]
    user_keys = res["user_keys"]

    levs_maint = [x for x in levs_maint if int(x["health"]) <= 10]
    levs_init = [x for x in levs_init if int(x["health"]) <= 10]

    df: pd.DataFrame
    match mode:
        case 0:  # nothing
            df = pd.DataFrame(levs_none, index=user_keys)
        case 1:  # liq within 50% of oracle
            df = pd.DataFrame(levs_none, index=user_keys)
        case 2:  # maint. health < 10%
            user_keys = [x["user_key"] for x in levs_init]
            df = pd.DataFrame(levs_init, index=user_keys)
        case 3:  # init. health < 10%
            user_keys = [x["user_key"] for x in levs_maint]
            df = pd.DataFrame(levs_maint, index=user_keys)

    def get_rattt(row):
        calculations = [
            (
                "all_assets",
                lambda v: v if v > 0 else 0,
            ),  # Simplified from v / row['spot_asset'] * row['spot_asset']
            (
                "all",
                lambda v: (
                    v
                    / row["spot_asset"]
                    * (row["perp_liability"] + row["spot_liability"])
                    if v > 0
                    else 0
                ),
            ),
            (
                "all_perp",
                lambda v: v / row["spot_asset"] * row["perp_liability"] if v > 0 else 0,
            ),
            (
                "all_spot",
                lambda v: v / row["spot_asset"] * row["spot_liability"] if v > 0 else 0,
            ),
            (
                f"perp_{perp_market_index}_long",
                lambda v: (
                    v / row["spot_asset"] * row["net_p"][perp_market_index]
                    if v > 0 and row["net_p"][0] > 0
                    else 0
                ),
            ),
            (
                f"perp_{perp_market_index}_short",
                lambda v: (
                    v / row["spot_asset"] * row["net_p"][perp_market_index]
                    if v > 0 and row["net_p"][perp_market_index] < 0
                    else 0
                ),
            ),
        ]

        series_list = []
        for suffix, calc_func in calculations:
            series = pd.Series([calc_func(val) for key, val in row["net_v"].items()])
            series.index = [f"spot_{x}_{suffix}" for x in series.index]
            series_list.append(series)

        return pd.concat(series_list)

    df = pd.concat([df, df.apply(get_rattt, axis=1)], axis=1)

    def calculate_effective_leverage(group):
        assets = group["all_assets"]
        liabilities = group["all_liabilities"]
        return liabilities / assets if assets != 0 else 0

    def format_with_checkmark(value, condition, mode, financial=False):
        if financial:
            formatted_value = f"{value:,.2f}"
        else:
            formatted_value = f"{value:.2f}"

        if condition and mode > 0:
            return f"{formatted_value} ✅"
        return formatted_value

    res = pd.DataFrame(
        {
            ("spot" + str(i)): (
                df[f"spot_{i}_all_assets"].sum(),
                format_with_checkmark(
                    df[f"spot_{i}_all"].sum(),
                    0 < df[f"spot_{i}_all"].sum() < 1_000_000,
                    mode,
                    financial=True,
                ),
                format_with_checkmark(
                    calculate_effective_leverage(
                        {
                            "all_assets": df[f"spot_{i}_all_assets"].sum(),
                            "all_liabilities": df[f"spot_{i}_all"].sum(),
                        }
                    ),
                    0
                    < calculate_effective_leverage(
                        {
                            "all_assets": df[f"spot_{i}_all_assets"].sum(),
                            "all_liabilities": df[f"spot_{i}_all"].sum(),
                        }
                    )
                    < 2,
                    mode,
                ),
                df[f"spot_{i}_all_spot"].sum(),
                df[f"spot_{i}_all_perp"].sum(),
                df[f"spot_{i}_perp_{perp_market_index}_long"].sum(),
                df[f"spot_{i}_perp_{perp_market_index}_short"].sum(),
            )
            for i in range(NUMBER_OF_SPOT)
        },
        index=[
            "all_assets",
            "all_liabilities",
            "effective_leverage",
            "all_spot",
            "all_perp",
            f"perp_{perp_market_index}_long",
            f"perp_{perp_market_index}_short",
        ],
    ).T

    res["all_liabilities"] = res["all_liabilities"].astype(str)
    res["effective_leverage"] = res["effective_leverage"].astype(str)

    return res, df
