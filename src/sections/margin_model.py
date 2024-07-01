from asyncio import AbstractEventLoop
from typing import Iterator
from driftpy.pickle.vat import Vat

import streamlit as st
import pandas as pd  # type: ignore

from sections.asset_liab_matrix import get_matrix, NUMBER_OF_SPOT  # type: ignore
from driftpy.market_map.market_map import SpotMarketAccount
from driftpy.accounts.types import DataAndSlot
from driftpy.constants.numeric_constants import (
    SPOT_BALANCE_PRECISION,
    PERCENTAGE_PRECISION,
    QUOTE_PRECISION,
    PRICE_PRECISION,
)
from driftpy.drift_client import DriftClient
from driftpy.constants.spot_markets import mainnet_spot_market_configs

from sections.liquidation_curves import get_liquidation_curve, get_liquidation_list

spot_fields = [
    "deposit_balance",
    "borrow_balance",
    "initial_asset_weight",
    "maintenance_asset_weight",
    "initial_liability_weight",
    "maintenance_liability_weight",
    "optimal_utilization",
    "optimal_borrow_rate",
    "max_borrow_rate",
    "market_index",
    "scale_initial_asset_weight_start",
]

stables = [0, 5, 18]
sol_and_lst = [1, 2, 6, 8, 16, 17]
sol_eco = [7, 9, 11, 12, 13, 14, 15, 19]

spot_market_indexes = [market.market_index for market in mainnet_spot_market_configs]

index_options = {}
index_options["All"] = spot_market_indexes
index_options["Stables"] = stables
index_options["Solana and LST"] = sol_and_lst
index_options["Solana Ecosystem"] = sol_eco
index_options.update(
    {market.symbol: [market.market_index] for market in mainnet_spot_market_configs}
)


def margin_model(loop: AbstractEventLoop, dc: DriftClient):
    st.header("Margin Model")
    if "vat" not in st.session_state:
        st.write("No Vat loaded.")
        return

    vat: Vat = st.session_state["vat"]

    spot_df = get_spot_df(vat.spot_markets.values(), vat)

    stable_df = spot_df[spot_df.index.isin(stables)]

    col1, col2, col3 = st.columns([1, 1, 1])
    total_deposits = spot_df["deposit_balance"].sum()
    total_stable_deposits_notional = stable_df["deposit_balance"].sum()
    total_stable_borrows_notional = stable_df["borrow_balance"].sum()
    total_stable_utilization = (
        total_stable_borrows_notional / total_stable_deposits_notional
    )
    total_margin_available = spot_df["scale_initial_asset_weight_start"].sum()
    # numerator = max(total_deposits, total_margin_available)
    # denominator = min(total_deposits, total_margin_available)
    maximum_exchange_leverage = total_margin_available / total_deposits

    with col1:
        st.markdown(
            f"##### Total Stable Collateral: `${total_stable_deposits_notional:,.2f}` #####"
        )

        st.markdown(
            f"##### Total Stable Liabilities: `${total_stable_borrows_notional:,.2f}` #####"
        )

        st.markdown(
            f"##### Total Stable Utilization: `{(total_stable_utilization * 100):,.2f}%` #####"
        )

    margin_df: pd.DataFrame
    res: pd.DataFrame
    if "margin" not in st.session_state:
        st.session_state["margin"] = get_matrix(loop, vat, dc)
        margin_df = st.session_state["margin"][1]
        res = st.session_state["margin"][0]
    else:
        margin_df = st.session_state["margin"][1]
        res = st.session_state["margin"][0]

    spot_df["all_liabilities"] = spot_df["symbol"].map(res["all_liabilities"])
    spot_df["all_liabilities"] = (
        spot_df["all_liabilities"].str.replace(r"[$,]", "", regex=True).astype(float)
    )

    spot_df.insert(3, "all_liabilities", spot_df.pop("all_liabilities"))

    spot_df["perp_leverage"] = spot_df["all_liabilities"] / spot_df["deposit_balance"]

    spot_df.insert(6, "perp_leverage", spot_df.pop("perp_leverage"))

    spot_df.rename(columns={"leverage": "actual_utilization"}, inplace=True)

    spot_df.insert(4, "optimal_utilization", spot_df.pop("optimal_utilization"))
    total_margin_utilized_notional = sum(
        margin_df[f"spot_{i}_all"].sum() for i in range(NUMBER_OF_SPOT)
    )
    total_margin_utilized = total_margin_utilized_notional / total_margin_available

    actual_exchange_leverage = total_margin_utilized_notional / total_deposits

    with col2:
        st.markdown(
            f"##### Total Margin Extended: `${total_margin_available:,.2f}` #####"
        )

        st.markdown(
            f"##### Total Margin Utilized: `${total_margin_utilized_notional:,.2f}` #####"
        )

        st.markdown(
            f"##### Total Margin Utilized: `{(total_margin_utilized * 100):,.2f}%` #####"
        )

    with col3:
        st.markdown(f"##### Total Collateral: `${total_deposits:,.2f}` #####")

        st.markdown(
            f"##### Maximum Exchange Leverage: `{maximum_exchange_leverage:,.2f}` #####"
        )

        st.markdown(
            f"##### Actual Exchange Leverage: `{actual_exchange_leverage:,.2f}` #####"
        )

    st.markdown("#### Spot Markets ####")

    col1, col2 = st.columns([1, 1])

    default_index = list(index_options.keys()).index("All")
    with col1:
        selected_option = st.selectbox(
            "Select Markets", options=list(index_options.keys()), index=default_index
        )

    with col2:
        oracle_liquidation_offset = st.text_input("Oracle Liquidation Offset (%)", 50)

        def apply_liquidations(row, vat, oracle_liquidation_offset):
            long_liq, short_liq = get_liquidations_offset_from_oracle(
                row, vat, oracle_liquidation_offset
            )
            return pd.Series(
                {"long_liq_notional": long_liq, "short_liq_notional": short_liq}
            )

        spot_df[["long_liq_notional", "short_liq_notional"]] = spot_df.apply(
            lambda row: apply_liquidations(row, vat, int(oracle_liquidation_offset)),
            axis=1,
        )

        spot_df.insert(6, "long_liq_notional", spot_df.pop("long_liq_notional"))
        spot_df.insert(7, "short_liq_notional", spot_df.pop("short_liq_notional"))

    selected_indexes = index_options[selected_option]  # type: ignore

    filtered_df = spot_df.loc[spot_df.index.isin(selected_indexes)]

    st.dataframe(display_formatted_df(filtered_df))


def get_liquidations_offset_from_oracle(row, vat, oracle_liquidation_offset: int):
    market_index = row.name
    liquidations_long, liquidations_short, oracle_price = get_liquidation_list(
        vat, int(market_index), True
    )

    def get_liqs(liqs):
        liq_notional = 0
        for liq_price, notional, _ in liqs:
            diff = abs(liq_price - oracle_price)
            threshold = liq_price * (oracle_liquidation_offset / 100)
            if diff < threshold:
                liq_notional += notional

        return liq_notional

    long_liq_notional = get_liqs(liquidations_long)
    short_liq_notional = get_liqs(liquidations_short)

    return (long_liq_notional, short_liq_notional)


def get_spot_df(accounts: Iterator[DataAndSlot[SpotMarketAccount]], vat: Vat):
    transformations = {
        "deposit_balance": lambda x: x / SPOT_BALANCE_PRECISION,
        "borrow_balance": lambda x: x / SPOT_BALANCE_PRECISION,
        "initial_asset_weight": lambda x: x / PERCENTAGE_PRECISION * 100,
        "maintenance_asset_weight": lambda x: x / PERCENTAGE_PRECISION * 100,
        "initial_liability_weight": lambda x: x / PERCENTAGE_PRECISION * 100,
        "maintenance_liability_weight": lambda x: x / PERCENTAGE_PRECISION * 100,
        "optimal_utilization": lambda x: x / PERCENTAGE_PRECISION,
        "optimal_borrow_rate": lambda x: x / PERCENTAGE_PRECISION,
        "max_borrow_rate": lambda x: x / PERCENTAGE_PRECISION,
        "scale_initial_asset_weight_start": lambda x: x / QUOTE_PRECISION,
    }

    data = [
        {field: getattr(account.data, field) for field in spot_fields}
        for account in accounts
    ]

    df = pd.DataFrame(data)

    if "market_index" in spot_fields:
        df.set_index("market_index", inplace=True)

    for column, transformation in transformations.items():
        if column in df.columns:
            df[column] = df[column].apply(transformation)

    df["leverage"] = df["borrow_balance"] / df["deposit_balance"]

    df["symbol"] = df.index.map(lambda idx: mainnet_spot_market_configs[idx].symbol)

    def notional(row, balance_type):
        market_price = vat.spot_oracles.get(row.name).price / PRICE_PRECISION  # type: ignore
        size = row[balance_type]
        notional_value = size * market_price
        return notional_value

    df["deposit_balance"] = df.apply(notional, balance_type="deposit_balance", axis=1)
    df["borrow_balance"] = df.apply(notional, balance_type="borrow_balance", axis=1)

    df.insert(0, "symbol", df.pop("symbol"))
    df.insert(1, "deposit_balance", df.pop("deposit_balance"))
    df.insert(2, "borrow_balance", df.pop("borrow_balance"))
    df.insert(4, "leverage", df.pop("leverage"))
    df.insert(
        5,
        "scale_initial_asset_weight_start",
        df.pop("scale_initial_asset_weight_start"),
    )

    df = df.sort_index()

    return df


def display_formatted_df(df):
    format_dict = {
        "deposit_balance": "${:,.2f}",
        "borrow_balance": "${:,.2f}",
        "all_liabilities": "${:,.2f}",
        "initial_asset_weight": "{:.2%}",
        "maintenance_asset_weight": "{:.2%}",
        "initial_liability_weight": "{:.2%}",
        "maintenance_liability_weight": "{:.2%}",
        "optimal_utilization": "{:.2%}",
        "actual_utilization": "{:.2%}",
        "optimal_borrow_rate": "{:.2%}",
        "max_borrow_rate": "{:.2%}",
        "market_index": "{:}",
        "scale_initial_asset_weight_start": "${:,.2f}",
        "perp_leverage": "{:.2f}",
        "short_liq_notional": "${:,.2f}",
        "long_liq_notional": "${:,.2f}",
    }

    styled_df = df.style.format(format_dict)

    return styled_df
