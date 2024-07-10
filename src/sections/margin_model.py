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

from utils import aggregate_perps
from driftpy.drift_user import DriftUser

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

margin_scalars = {
    "USDC": 1.3,
    "USDT": 1.3,
    "SOL": 1.1,
    "mSOL": 1.1,
    "jitoSOL": 1.1,
    "bSOL": 1.1,
    "INF": 1.1,
    "dSOL": 1.1,
}

DEFAULT_MARGIN_SCALAR = 0.5

stables = [0, 5, 18]
sol_and_lst = [1, 2, 6, 8, 16, 17]
sol_eco = [7, 9, 11, 12, 13, 14, 15, 19]
wrapped = [3, 4]

spot_market_indexes = [market.market_index for market in mainnet_spot_market_configs]

index_options = {}
index_options["All"] = spot_market_indexes
index_options["Stables"] = stables
index_options["Solana and LST"] = sol_and_lst
index_options["Solana Ecosystem"] = sol_eco
index_options["Wrapped"] = wrapped
index_options.update(
    {market.symbol: [market.market_index] for market in mainnet_spot_market_configs}
)


def margin_model(loop: AbstractEventLoop, dc: DriftClient):
    st.header("Margin Model")
    if "vat" not in st.session_state:
        st.write("No Vat loaded.")
        return

    vat: Vat = st.session_state["vat"]
    agg_df, aggregated_users = aggregate_perps(vat, loop)

    # st.dataframe(df)

    spot_df = get_spot_df(vat.spot_markets.values(), vat)

    stable_df = spot_df[spot_df.index.isin(stables)]

    col1, col2, col3 = st.columns([1, 1, 1])
    total_deposits = spot_df["deposit_balance"].sum()
    total_stable_deposits_notional = stable_df["deposit_balance"].sum()
    total_stable_borrows_notional = stable_df["borrow_balance"].sum()
    total_stable_utilization = (
        total_stable_borrows_notional / total_stable_deposits_notional
    )
    total_margin_available = spot_df["max_margin_extended"].sum()
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

    st.markdown("#### Spot Market Overview ####")

    col1, col2 = st.columns([1, 1])

    default_index = list(index_options.keys()).index("All")
    with col1:
        selected_option = st.selectbox(
            "Select Markets", options=list(index_options.keys()), index=default_index
        )

    # TODO BROKEN
    with col2:
        oracle_liquidation_offset = st.text_input("Oracle Liquidation Offset (%)", 50)

        liqs_long, liqs_short = get_liquidations_offset(
            agg_df, aggregated_users, vat, int(oracle_liquidation_offset)
        )

        totals_long = {}
        users_long = {}

        for market_index, notional, user_public_key, scaled_balance in liqs_long:
            # notional_pos = -notional if notional < 0 else notional
            print(f"notional long: {notional}")
            totals_long[market_index] = totals_long.get(market_index, 0) + notional
            users_long[user_public_key] = (
                notional,
                scaled_balance / SPOT_BALANCE_PRECISION,
            )

        totals_short = {}
        users_short = {}
        print("\n\n\n")

        for market_index, notional, user_public_key, scaled_balance in liqs_short:
            # notional_pos = -notional if notional < 0 else notional
            print(f"notional short: {notional}")
            totals_short[market_index] = totals_short.get(market_index, 0) + notional
            users_short[user_public_key] = (
                notional,
                scaled_balance / SPOT_BALANCE_PRECISION,
            )

        long_users_list = pd.DataFrame.from_dict(users_long, orient="index")
        short_users_list = pd.DataFrame.from_dict(users_short, orient="index")

        long_users_list.columns = ["liquidation_notional", "scaled_balance"]
        short_users_list.columns = ["liquidation_notional", "scaled_balance"]

        long_liq_notional = pd.Series(totals_long, name="long_liq_notional")
        short_liq_notional = pd.Series(totals_short, name="short_liq_notional")

        print(totals_long)
        print("\n\n\n")
        print(totals_short)

        long_liq_notional = long_liq_notional.reindex(spot_df.index, fill_value=0)
        short_liq_notional = short_liq_notional.reindex(spot_df.index, fill_value=0)

        spot_df = spot_df.join(long_liq_notional)
        spot_df = spot_df.join(short_liq_notional)

    spot_df.insert(6, "long_liq_notional", spot_df.pop("long_liq_notional"))
    spot_df.insert(7, "short_liq_notional", spot_df.pop("short_liq_notional"))

    selected_indexes = index_options[selected_option]  # type: ignore

    filtered_df = spot_df.loc[spot_df.index.isin(selected_indexes)]

    st.dataframe(display_formatted_df(filtered_df))

    st.markdown("#### Spot Market Analysis ####")

    index_options_list = list(index_options.values())

    all_analytics_df = get_analytics_df(index_options_list[0], spot_df)
    sol_and_lst_basis_df = get_analytics_df(index_options_list[2], spot_df)
    wrapped_basis_df = get_analytics_df(index_options_list[4], spot_df)
    wif_df = get_analytics_df([10], spot_df)

    total_margin_available = all_analytics_df["target_margin_extended"].sum()

    st.markdown(
        f"##### Total Target Margin Extended: `${total_margin_available:,.2f}` #####"
    )

    tabs = st.tabs(list(index_options.keys()))

    for idx, tab in enumerate(tabs):
        with tab:
            if idx == 0:
                current_analytics_df = all_analytics_df
                st.dataframe(display_formatted_df(current_analytics_df))
            elif idx == 2:
                st.dataframe(display_formatted_df(sol_and_lst_basis_df))
            elif idx == 4:
                st.dataframe(display_formatted_df(wrapped_basis_df))
            elif set(index_options_list[idx]).issubset(set(sol_and_lst)):
                filtered_df = sol_and_lst_basis_df[
                    sol_and_lst_basis_df.index == index_options_list[idx][0]
                ]
                st.dataframe(display_formatted_df(filtered_df))
            elif set(index_options_list[idx]).issubset(wrapped):
                filtered_df = wrapped_basis_df[
                    wrapped_basis_df.index == index_options_list[idx][0]
                ]
                st.dataframe(display_formatted_df(filtered_df))
            elif set(index_options_list[idx]).issubset(set([10])):  # WIF
                st.dataframe(display_formatted_df(wif_df))
            else:
                analytics_df = get_analytics_df(index_options_list[idx], spot_df)
                st.dataframe(display_formatted_df(analytics_df))

    (levs_none, _, _) = st.session_state["asset_liab_data"][0]
    user_keys = st.session_state["asset_liab_data"][1]

    df = pd.DataFrame(levs_none, index=user_keys)

    lev, size = get_size_and_lev(df, selected_indexes)

    col1, col2 = st.columns([1, 1])

    with col1:
        with st.expander("users by size (selected overview category)"):
            st.dataframe(size)

    with col2:
        with st.expander("users by lev (selected overview category)"):
            st.dataframe(lev)

    col1, col2 = st.columns([1, 1])

    with col1:
        with st.expander("users long liquidation (offset)"):
            st.dataframe(display_formatted_df(long_users_list))

    with col2:
        with st.expander("users short liquidation (offset)"):
            st.dataframe(display_formatted_df(short_users_list))


def get_size_and_lev(df: pd.DataFrame, market_indexes: list[int]):
    def has_target(net_v, market_indexes):
        if isinstance(net_v, dict):
            return any(net_v.get(idx, 0) != 0 for idx in market_indexes)
        return False

    lev = df.sort_values(by="leverage", ascending=False)

    lev = lev[lev.apply(lambda row: has_target(row["net_v"], market_indexes), axis=1)]

    lev["selected_assets"] = lev["net_v"].apply(
        lambda net_v: {
            idx: net_v.get(idx, 0) for idx in market_indexes if net_v.get(idx, 0) != 0
        }
    )

    size = df.sort_values(by="spot_asset", ascending=False)
    size = size[
        size.apply(lambda row: has_target(row["net_v"], market_indexes), axis=1)
    ]

    size["selected_assets"] = size["net_v"].apply(
        lambda net_v: {
            idx: net_v.get(idx, 0) for idx in market_indexes if net_v.get(idx, 0) != 0
        }
    )

    lev.pop("user_key")
    size.pop("user_key")

    lev.insert(2, "selected_assets", lev.pop("selected_assets"))
    size.insert(2, "selected_assets", size.pop("selected_assets"))

    return lev, size


def get_analytics_df(market_indexes: list[int], spot_df: pd.DataFrame):
    (levs_none, _, _) = st.session_state["asset_liab_data"][0]
    user_keys = st.session_state["asset_liab_data"][1]

    df = pd.DataFrame(levs_none, index=user_keys)

    analytics_df = pd.DataFrame()
    analytics_df.index = spot_df.index
    columns = [
        "symbol",
        "deposit_balance",
        "borrow_balance",
        "all_liabilities",
        "perp_leverage",
        "max_margin_extended",
    ]
    analytics_df[columns] = spot_df[columns]

    def is_basis(market_indexes):
        sol_lst_set = set(sol_and_lst)
        wrapped_set = set(wrapped)
        wif_set = set([10])

        is_sol_lst = market_indexes.issubset(sol_lst_set)
        is_wrapped = market_indexes.issubset(wrapped_set)
        is_wif = market_indexes.issubset(wif_set)

        return is_sol_lst or is_wrapped or is_wif

    if is_basis(set(market_indexes)):
        analytics_df["basis_short"] = spot_df.apply(
            lambda row: get_basis_trade_notional(row, df), axis=1
        )

    def get_margin_scalar(symbol):
        return margin_scalars.get(symbol, DEFAULT_MARGIN_SCALAR)

    import numpy as np

    new_target_margin = np.where(
        analytics_df["perp_leverage"] > analytics_df["deposit_balance"],
        (1 / analytics_df["perp_leverage"])
        * analytics_df["deposit_balance"]
        * analytics_df["symbol"].map(get_margin_scalar),
        analytics_df["max_margin_extended"],
    )

    analytics_df["target_margin_extended"] = new_target_margin
    return analytics_df.loc[analytics_df.index.isin(market_indexes)]


def get_perp_short(df, market_index, basis_index):
    new_column_name = f"perp_{basis_index}_short"

    def calculate_perp_short(row):
        net_v = row["net_v"][market_index]
        net_p = row["net_p"][basis_index]
        spot_asset = row["spot_asset"]

        condition = net_v > 0 and net_p < 0
        value = net_v / spot_asset * net_p if condition else 0

        return value

    df[new_column_name] = df.apply(calculate_perp_short, axis=1)

    return df[new_column_name]


def get_basis_trade_notional(row, df):
    basis_index = -1
    market_index = row.name
    if market_index in sol_and_lst and market_index != 0:
        basis_index = 0
    elif market_index == 3:
        basis_index = 1
    elif market_index == 4:
        basis_index = 2

    if basis_index == -1:
        return 0

    perp_short_series = get_perp_short(df, market_index, basis_index)
    total_perp_short = perp_short_series.sum()
    print(
        f"Total perp short for market_index {market_index} basis_index {basis_index}: {total_perp_short}"
    )
    return abs(total_perp_short)


def get_liquidations_offset(
    df: pd.DataFrame,
    aggregated_users: list[DriftUser],
    vat: Vat,
    oracle_liquidation_offset,
):
    import copy

    long_liquidations = []
    short_liquidations = []
    curr_sol_perp_price = vat.perp_oracles.get(0).price / PRICE_PRECISION  # type: ignore
    from driftpy.account_subscription_config import AccountSubscriptionConfig

    for user in aggregated_users:
        user_total_spot_value = df.loc[user.user_public_key, "spot_asset"]
        if user_total_spot_value == 0:
            continue
        for position in user.get_user_account().spot_positions:
            # ignore borrows
            if position.scaled_balance < 0:
                continue
            fake_user_account = user.get_user_account()
            spot_market_index = position.market_index
            # proportion their perp position according to the spot value
            isolated_collateral_usd = df.loc[user.user_public_key, "net_v"][
                spot_market_index
            ]
            proportion = isolated_collateral_usd / user_total_spot_value
            pp = [
                pos for pos in fake_user_account.perp_positions if pos.market_index == 0
            ][0]
            perp_position = copy.deepcopy(pp)
            if proportion > 1:
                raise ValueError("Proportion should be less than 1: ", proportion)
            perp_position.base_asset_amount = int(
                perp_position.base_asset_amount * proportion
            )
            perp_position.quote_asset_amount = int(
                perp_position.quote_asset_amount * proportion
            )

            # create a fake drift user with the proportioned perp position & isolated spot position
            fake_user_account.spot_positions = [position]
            fake_user_account.perp_positions = [perp_position]
            prev_user = DriftUser(
                user.drift_client,
                user.user_public_key,
                AccountSubscriptionConfig("cached"),
            )
            prev_user.account_subscriber.user_and_slot = (
                user.account_subscriber.user_and_slot
            )
            user.account_subscriber.user_and_slot.data = fake_user_account

            # insert a fake price into the user account
            spot_oracle_pubkey = vat.spot_markets.get(position.market_index).data.oracle  # type: ignore
            prev_price_data = vat.spot_oracles.get(position.market_index)
            prev_price = prev_price_data.price  # type: ignore

            # up move by oracle_liquidation_offset %
            up_price = int(prev_price * (1 + (int(oracle_liquidation_offset) / 100)))
            user.drift_client.account_subscriber.cache["oracle_price_data"][
                str(spot_oracle_pubkey)
            ].price = up_price
            # get notional of position after price increase
            long_position_notional = (
                user.get_margin_requirement(liquidation_buffer=100)
                - user.get_total_collateral()
            ) / QUOTE_PRECISION

            # get liquidation price of the perp if spot price increases by oracle_liquidation_offset &
            up_move_liquidation_price = user.get_perp_liq_price(0) / PRICE_PRECISION

            # down move by oracle_liquidation_offset %
            down_price = int(prev_price * (1 - (int(oracle_liquidation_offset) / 100)))
            user.drift_client.account_subscriber.cache["oracle_price_data"][
                str(spot_oracle_pubkey)
            ].price = down_price
            # get notional of position after price decrease
            short_position_notional = (
                user.get_margin_requirement(liquidation_buffer=100)
                - user.get_total_collateral()
            ) / QUOTE_PRECISION

            down_move_liquidation_price = user.get_perp_liq_price(0) / PRICE_PRECISION

            user.drift_client.account_subscriber.cache["oracle_price_data"][
                str(spot_oracle_pubkey)
            ].price = prev_price
            user = prev_user

            is_short = perp_position.base_asset_amount < 0
            is_long = perp_position.base_asset_amount > 0

            if is_short and down_move_liquidation_price > curr_sol_perp_price:
                short_liquidations.append(
                    (
                        spot_market_index,
                        abs(short_position_notional),
                        user.user_public_key,
                        position.scaled_balance,
                    )
                )
            elif is_long and up_move_liquidation_price < curr_sol_perp_price:
                long_liquidations.append(
                    (
                        spot_market_index,
                        abs(long_position_notional),
                        user.user_public_key,
                        position.scaled_balance,
                    )
                )

    return long_liquidations, short_liquidations


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

    df.rename(
        columns={"scale_initial_asset_weight_start": "max_margin_extended"},
        inplace=True,
    )
    df = df.sort_index()

    return df


def display_formatted_df(df):
    format_dict = {
        "deposit_balance": "${:,.2f}",
        "borrow_balance": "${:,.2f}",
        "perp_liabilities": "${:,.2f}",
        "initial_asset_weight": "{:.2%}",
        "maintenance_asset_weight": "{:.2%}",
        "initial_liability_weight": "{:.2%}",
        "maintenance_liability_weight": "{:.2%}",
        "optimal_utilization": "{:.2%}",
        "actual_utilization": "{:.2%}",
        "optimal_borrow_rate": "{:.2%}",
        "max_borrow_rate": "{:.2%}",
        "market_index": "{:}",
        "max_margin_extended": "${:,.2f}",
        "perp_leverage": "{:.2f}",
        "target_margin_extended": "${:,.2f}",
        "basis_short": "${:,.2f}",
        "leverage": "{:.2f}",
        "health": "{:.2%}%",
        "short_liq_notional": "${:,.2f}",
        "long_liq_notional": "${:,.2f}",
        "liquidation_notional": "${:,.2f}",
        "scaled_balance": "{:,.2f}",
    }

    df.rename(columns={"all_liabilities": "perp_liabilities"}, inplace=True)

    styled_df = df.style.format(format_dict)

    return styled_df
