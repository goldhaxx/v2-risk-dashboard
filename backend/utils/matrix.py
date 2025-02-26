import pandas as pd
from driftpy.constants.spot_markets import mainnet_spot_market_configs
from driftpy.pickle.vat import Vat

from backend.utils.user_metrics import (
    get_user_metrics_initial,
    get_user_metrics_maintenance,
    get_user_metrics_none,
)


def calculate_effective_leverage(assets: float, liabilities: float) -> float:
    return liabilities / assets if assets != 0 else 0


def format_metric(
    value: float,
    should_highlight: bool,
    mode: int,
    financial: bool = False,
) -> str:
    formatted = f"{value:,.2f}" if financial else f"{value:.2f}"
    return f"{formatted} ✅" if should_highlight and mode > 0 else formatted


async def get_matrix(
    vat: Vat, mode: int = 0, perp_market_index: int = 0, toggle_upnl: bool = True
):
    NUMBER_OF_SPOT = len(mainnet_spot_market_configs)

    # The modes are:
    # 0: None
    # 1: liq within 50% of oracle
    # 2: maint. health < 10%
    # 3: init. health < 10%

    if mode == 0 or mode == 1:
        res = get_user_metrics_none(vat.users)
        metrics_data = res["metrics_none"]
        user_keys = res["user_keys"]
    elif mode == 2:
        res = get_user_metrics_initial(vat.users)
        metrics_data = [x for x in res["metrics_initial"] if int(x["health"]) <= 10]
        user_keys = [x["user_key"] for x in metrics_data]
    elif mode == 3:
        res = get_user_metrics_maintenance(vat.users)
        metrics_data = [x for x in res["metrics_maintenance"] if int(x["health"]) <= 10]
        user_keys = [x["user_key"] for x in metrics_data]
    else:
        raise ValueError(f"Invalid mode: {mode}")

    df = pd.DataFrame(metrics_data, index=user_keys)

    new_columns = {}
    for i in range(NUMBER_OF_SPOT):
        prefix = f"spot_{i}"
        column_names = [
            f"{prefix}_all_assets",
            f"{prefix}_all",
            f"{prefix}_all_perp",
            f"{prefix}_all_spot",
            f"{prefix}_perp_{perp_market_index}_long",
            f"{prefix}_perp_{perp_market_index}_short",
        ]
        for col in column_names:
            new_columns[col] = pd.Series(0.0, index=df.index)

    for idx, row in df.iterrows():
        spot_asset = row["spot_asset"]

        for market_id, value in row["net_v"].items():
            value_mod = value
            if toggle_upnl and "upnl" in row and market_id == 0:
                value_mod = row["upnl"] + value

            if value_mod < 0:
                # print(f"value: {value}, type: {type(value)}")
                continue

            if value_mod == 0:
                continue

            base_name = f"spot_{market_id}"

            if row["spot_asset"] == 0:
                continue

            metrics = {
                f"{base_name}_all_assets": value_mod,
                f"{base_name}_all": value_mod
                / spot_asset
                * (row["perp_liability"] + row["spot_liability"]),
                f"{base_name}_all_perp": value_mod / spot_asset * row["perp_liability"],
                f"{base_name}_all_spot": value_mod / spot_asset * row["spot_liability"],
            }

            net_perp = float(row["net_p"][perp_market_index])
            # print(f"net_perp value: {net_perp}")

            if net_perp > 0:
                metrics[f"{base_name}_perp_{perp_market_index}_long"] = (
                    value / spot_asset * net_perp
                )
            if net_perp < 0:
                metrics[f"{base_name}_perp_{perp_market_index}_short"] = (
                    value / spot_asset * net_perp
                )

            for col, val in metrics.items():
                new_columns[col][idx] = val

    df = pd.concat([df, pd.DataFrame(new_columns)], axis=1)
    return df
