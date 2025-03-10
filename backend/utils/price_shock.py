from typing import Any, TypedDict

import pandas as pd
from driftpy.drift_client import DriftClient
from driftpy.pickle.vat import Vat

from backend.utils.user_metrics import get_user_leverages_for_price_shock
from shared.types import PriceShockAssetGroup


class UserLeveragesResponse(TypedDict):
    leverages_none: list[Any]
    leverages_up: list[Any]
    leverages_down: list[Any]
    user_keys: list[str]
    distorted_oracles: list[str]


def create_dataframes(leverages):
    return [pd.DataFrame(lev) for lev in leverages]


def calculate_spot_bankruptcies(df):
    spot_bankrupt = df[
        (df["spot_asset"] < df["spot_liability"]) & (df["net_usd_value"] < 0)
    ]
    return (spot_bankrupt["spot_liability"] - spot_bankrupt["spot_asset"]).sum()


def calculate_total_bankruptcies(df):
    return -df[df["net_usd_value"] < 0]["net_usd_value"].sum()


def generate_oracle_moves(num_scenarios, oracle_distort):
    return (
        [-oracle_distort * (i + 1) * 100 for i in range(num_scenarios)]
        + [0]
        + [oracle_distort * (i + 1) * 100 for i in range(num_scenarios)]
    )


def get_price_shock_df(
    slot: int,
    drift_client: DriftClient,
    vat: Vat,
    oracle_distortion: float,
    asset_group: PriceShockAssetGroup,
    n_scenarios: int,
):
    user_leverages = get_user_leverages_for_price_shock(
        slot,
        drift_client,
        vat.users,
        oracle_distortion,
        asset_group,
        n_scenarios,
    )
    levs = user_leverages
    dfs = (
        create_dataframes(levs["leverages_down"])
        + [pd.DataFrame(levs["leverages_none"])]
        + create_dataframes(levs["leverages_up"])
    )

    spot_bankruptcies = [calculate_spot_bankruptcies(df) for df in dfs]
    total_bankruptcies = [calculate_total_bankruptcies(df) for df in dfs]

    oracle_moves = generate_oracle_moves(n_scenarios, oracle_distortion)

    df_plot = pd.DataFrame(
        {
            "Oracle Move (%)": oracle_moves,
            "Total Bankruptcy ($)": total_bankruptcies,
            "Spot Bankruptcy ($)": spot_bankruptcies,
        }
    )

    df_plot = df_plot.sort_values("Oracle Move (%)")

    df_plot["Perpetual Bankruptcy ($)"] = (
        df_plot["Total Bankruptcy ($)"] - df_plot["Spot Bankruptcy ($)"]
    )
    oracle_down_max = pd.DataFrame(levs["leverages_down"][-1])
    oracle_up_max = pd.DataFrame(levs["leverages_up"][-1], index=levs["user_keys"])

    return {
        "slot": slot,
        "result": df_plot.to_json(),
        "distorted_oracles": levs["distorted_oracles"],
        "oracle_down_max": oracle_down_max.to_json(),
        "oracle_up_max": oracle_up_max.to_json(),
    }
