from typing import Any, TypedDict

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.api import fetch_cached_data
from utils import get_current_slot


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


def get_df_plot(user_leverages, oracle_distort: float):
    levs = user_leverages
    dfs = (
        create_dataframes(levs["leverages_down"])
        + [pd.DataFrame(levs["leverages_none"])]
        + create_dataframes(levs["leverages_up"])
    )

    spot_bankruptcies = [calculate_spot_bankruptcies(df) for df in dfs]
    total_bankruptcies = [calculate_total_bankruptcies(df) for df in dfs]

    num_scenarios = len(levs["leverages_down"])
    oracle_moves = generate_oracle_moves(num_scenarios, oracle_distort)

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

    return df_plot


@st.cache_data(ttl=20)
def price_shock_plot(user_leverages, oracle_distort: float):
    df_plot = get_df_plot(user_leverages, oracle_distort)

    fig = go.Figure()
    for column in [
        "Total Bankruptcy ($)",
        "Spot Bankruptcy ($)",
        "Perpetual Bankruptcy ($)",
    ]:
        fig.add_trace(
            go.Scatter(
                x=df_plot["Oracle Move (%)"],
                y=df_plot[column],
                mode="lines+markers",
                name=column,
            )
        )

    fig.update_layout(
        title="Bankruptcies in Cryptocurrency Price Scenarios",
        xaxis_title="Oracle Move (%)",
        yaxis_title="Bankruptcy ($)",
        legend_title="Bankruptcy Type",
        template="plotly_dark",
    )

    return fig


def price_shock_cached_page():
    params = st.query_params
    asset_group = params.get("asset_group", "ignore stables")

    asset_group = st.selectbox(
        "Asset Group",
        ["ignore stables", "jlp only"],
        index=["ignore stables", "jlp only"].index(asset_group),
    )
    st.query_params.update({"asset_group": asset_group})  # type: ignore

    n_scenarios = [5, 10]

    # Create a list with the second option labeled as experimental
    scenario_options = [5, "10 (experimental)"]
    radio = st.radio("Scenarios", scenario_options, index=0, key="n_scenarios")
    # Convert back to integer if the experimental option is selected
    n_scenarios = 10 if radio == "10 (experimental)" else radio

    if n_scenarios == 5:
        oracle_distort = 0.05
    else:
        oracle_distort = 0.1
    try:
        result = fetch_cached_data(
            "price-shock/usermap",
            _params={
                "asset_group": asset_group,
                "oracle_distortion": oracle_distort,
                "n_scenarios": n_scenarios,
            },
            key=f"price-shock/usermap_{asset_group}_{oracle_distort}_{n_scenarios}",
        )
    except Exception as e:
        print("HIT AN EXCEPTION...", e)
        st.error("Failed to fetch data")
        return

    if "result" in result and result["result"] == "miss":
        st.write("Fetching data for the first time...")
        st.image(
            "https://i.gifer.com/origin/8a/8a47f769c400b0b7d81a8f6f8e09a44a_w200.gif"
        )
        st.write("Check again in one minute!")
        st.stop()

    current_slot = get_current_slot()
    st.info(
        f"This data is for slot {result['slot']}, which is now {int(current_slot) - int(result['slot'])} slots old"
    )
    fig = price_shock_plot(result, oracle_distort)
    st.plotly_chart(fig)

    df_summary = get_df_plot(result, oracle_distort)

    col1, col2 = st.columns(2)
    with col1:
        df_liquidations = df_summary.drop(
            columns=["Spot Bankruptcy ($)", "Total Bankruptcy ($)"]
        )
        df_liquidations.rename(
            columns={
                "Perpetual Bankruptcy ($)": "Liquidations ($)",
                "Oracle Move (%)": "Oracle Move (%)",
            },
            inplace=True,
        )
        st.dataframe(df_liquidations)

    with col2:
        df_bad_debts = df_summary.drop(
            columns=["Perpetual Bankruptcy ($)", "Total Bankruptcy ($)"]
        )
        df_bad_debts.rename(
            columns={
                "Spot Bankruptcy ($)": "Bad Debts ($)",
                "Oracle Move (%)": "Oracle Move (%)",
            },
            inplace=True,
        )
        st.dataframe(df_bad_debts)

    oracle_down_max = pd.DataFrame(result["leverages_down"][-1])
    with st.expander(
        str("oracle down max bankrupt count=")
        + str(len(oracle_down_max[oracle_down_max.net_usd_value < 0]))
    ):
        st.dataframe(oracle_down_max)

    oracle_up_max = pd.DataFrame(result["leverages_up"][-1], index=result["user_keys"])
    with st.expander(
        str("oracle up max bankrupt count=")
        + str(len(oracle_up_max[oracle_up_max.net_usd_value < 0]))
    ):
        st.dataframe(oracle_up_max)

    with st.expander("distorted oracle keys"):
        st.write(result["distorted_oracles"])
