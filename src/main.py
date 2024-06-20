import asyncio
import heapq
import time
import os

import plotly.express as px  # type: ignore
import pandas as pd  # type: ignore

from typing import Any

from solana.rpc.async_api import AsyncClient

from anchorpy import Wallet

import streamlit as st

from driftpy.drift_client import DriftClient
from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.constants.numeric_constants import (
    BASE_PRECISION,
    SPOT_BALANCE_PRECISION,
    PRICE_PRECISION,
)
from driftpy.types import is_variant
from driftpy.pickle.vat import Vat

from utils import load_newest_files, load_vat, to_financial
from scenario import get_usermap_df

def get_largest_perp_positions(vat: Vat):
    top_positions: list[Any] = []

    for user in vat.users.values():
        for position in user.get_user_account().perp_positions:
            if position.base_asset_amount > 0:
                market_price = vat.perp_oracles.get(position.market_index)
                if market_price is not None:
                    market_price_ui = market_price.price / PRICE_PRECISION
                    base_asset_value = (
                        position.base_asset_amount / BASE_PRECISION
                    ) * market_price_ui
                    heap_item = (
                        to_financial(base_asset_value),
                        user.user_public_key,
                        position.market_index,
                        position.base_asset_amount / BASE_PRECISION,
                    )

                    if len(top_positions) < 10:
                        heapq.heappush(top_positions, heap_item)
                    else:
                        heapq.heappushpop(top_positions, heap_item)

    positions = sorted(
        (value, pubkey, market_idx, amt)
        for value, pubkey, market_idx, amt in top_positions
    )

    positions.reverse()

    data = {
        "Market Index": [pos[2] for pos in positions],
        "Value": [f"${pos[0]:,.2f}" for pos in positions],
        "Base Asset Amount": [f"{pos[3]:,.2f}" for pos in positions],
        "Public Key": [pos[1] for pos in positions],
    }

    return data


def get_largest_spot_borrows(vat: Vat):
    top_borrows: list[Any] = []

    for user in vat.users.values():
        for position in user.get_user_account().spot_positions:
            if position.scaled_balance > 0 and is_variant(
                position.balance_type, "Borrow"
            ):
                market_price = vat.spot_oracles.get(position.market_index)
                if market_price is not None:
                    market_price_ui = market_price.price / PRICE_PRECISION
                    borrow_value = (
                        position.scaled_balance / SPOT_BALANCE_PRECISION
                    ) * market_price_ui
                    heap_item = (
                        to_financial(borrow_value),
                        user.user_public_key,
                        position.market_index,
                        position.scaled_balance / SPOT_BALANCE_PRECISION,
                    )

                    if len(top_borrows) < 10:
                        heapq.heappush(top_borrows, heap_item)
                    else:
                        heapq.heappushpop(top_borrows, heap_item)

    borrows = sorted(
        (value, pubkey, market_idx, amt)
        for value, pubkey, market_idx, amt in top_borrows
    )

    borrows.reverse()

    data = {
        "Market Index": [pos[2] for pos in borrows],
        "Value": [f"${pos[0]:,.2f}" for pos in borrows],
        "Scaled Balance": [f"{pos[3]:,.2f}" for pos in borrows],
        "Public Key": [pos[1] for pos in borrows],
    }

    return data


def get_account_health_distribution(vat: Vat):
    health_notional_distributions = {
        "0-10%": 0,
        "10-20%": 0,
        "20-30%": 0,
        "30-40%": 0,
        "40-50%": 0,
        "50-60%": 0,
        "60-70%": 0,
        "70-80%": 0,
        "80-90%": 0,
        "90-100%": 0,
    }
    health_counts = {
        "0-10%": 0,
        "10-20%": 0,
        "20-30%": 0,
        "30-40%": 0,
        "40-50%": 0,
        "50-60%": 0,
        "60-70%": 0,
        "70-80%": 0,
        "80-90%": 0,
        "90-100%": 0,
    }

    for user in vat.users.values():
        total_collateral = user.get_total_collateral() / PRICE_PRECISION
        current_health = user.get_health()
        match current_health:
            case _ if current_health < 10:
                health_notional_distributions["0-10%"] += total_collateral
                health_counts["0-10%"] += 1
            case _ if current_health < 20:
                health_notional_distributions["10-20%"] += total_collateral
                health_counts["10-20%"] += 1
            case _ if current_health < 30:
                health_notional_distributions["20-30%"] += total_collateral
                health_counts["20-30%"] += 1
            case _ if current_health < 40:
                health_notional_distributions["30-40%"] += total_collateral
                health_counts["30-40%"] += 1
            case _ if current_health < 50:
                health_notional_distributions["40-50%"] += total_collateral
                health_counts["40-50%"] += 1
            case _ if current_health < 60:
                health_notional_distributions["50-60%"] += total_collateral
                health_counts["50-60%"] += 1
            case _ if current_health < 70:
                health_notional_distributions["60-70%"] += total_collateral
                health_counts["60-70%"] += 1
            case _ if current_health < 80:
                health_notional_distributions["70-80%"] += total_collateral
                health_counts["70-80%"] += 1
            case _ if current_health < 90:
                health_notional_distributions["80-90%"] += total_collateral
                health_counts["80-90%"] += 1
            case _:
                health_notional_distributions["90-100%"] += total_collateral
                health_counts["90-100%"] += 1
    df = pd.DataFrame(
        {
            "Health Range": list(health_counts.keys()),
            "Counts": list(health_counts.values()),
            "Notional Values": list(health_notional_distributions.values()),
        }
    )

    fig = px.bar(
        df,
        x="Health Range",
        y="Counts",
        title="Health Distribution",
        hover_data={"Notional Values": ":,"},  # Custom format for notional values
        labels={"Counts": "Num Users", "Notional Values": "Notional Value ($)"},
    )

    fig.update_traces(
        hovertemplate="<b>Health Range: %{x}</b><br>Count: %{y}<br>Notional Value: $%{customdata[0]:,.0f}<extra></extra>"
    )

    return fig


def get_most_levered_perp_positions_above_1m(vat: Vat):
    top_positions: list[Any] = []

    for user in vat.users.values():
        total_collateral = user.get_total_collateral() / PRICE_PRECISION
        if total_collateral > 0:
            for position in user.get_user_account().perp_positions:
                if position.base_asset_amount > 0:
                    market_price = vat.perp_oracles.get(position.market_index)
                    if market_price is not None:
                        market_price_ui = market_price.price / PRICE_PRECISION
                        base_asset_value = (
                            position.base_asset_amount / BASE_PRECISION
                        ) * market_price_ui
                        leverage = base_asset_value / total_collateral
                        if base_asset_value > 1_000_000:
                            heap_item = (
                                to_financial(base_asset_value),
                                user.user_public_key,
                                position.market_index,
                                position.base_asset_amount / BASE_PRECISION,
                                leverage,
                            )

                            if len(top_positions) < 10:
                                heapq.heappush(top_positions, heap_item)
                            else:
                                heapq.heappushpop(top_positions, heap_item)

    positions = sorted(
        top_positions,  # We can sort directly the heap result
        key=lambda x: x[
            4
        ],  # Sort by leverage, which is the fifth element in your tuple
    )

    positions.reverse()

    data = {
        "Market Index": [pos[2] for pos in positions],
        "Value": [f"${pos[0]:,.2f}" for pos in positions],
        "Base Asset Amount": [f"{pos[3]:,.2f}" for pos in positions],
        "Leverage": [f"{pos[4]:,.2f}" for pos in positions],
        "Public Key": [pos[1] for pos in positions],
    }

    return data


def get_most_levered_spot_borrows_above_1m(vat: Vat):
    top_borrows: list[Any] = []

    for user in vat.users.values():
        total_collateral = user.get_total_collateral() / PRICE_PRECISION
        if total_collateral > 0:
            for position in user.get_user_account().spot_positions:
                if (
                    is_variant(position.balance_type, "Borrow")
                    and position.scaled_balance > 0
                ):
                    market_price = vat.spot_oracles.get(position.market_index)
                    if market_price is not None:
                        market_price_ui = market_price.price / PRICE_PRECISION
                        borrow_value = (
                            position.scaled_balance / SPOT_BALANCE_PRECISION
                        ) * market_price_ui
                        leverage = borrow_value / total_collateral
                        if borrow_value > 750_000:
                            heap_item = (
                                to_financial(borrow_value),
                                user.user_public_key,
                                position.market_index,
                                position.scaled_balance / SPOT_BALANCE_PRECISION,
                                leverage,
                            )

                            if len(top_borrows) < 10:
                                heapq.heappush(top_borrows, heap_item)
                            else:
                                heapq.heappushpop(top_borrows, heap_item)

    borrows = sorted(
        top_borrows,
        key=lambda x: x[4],
    )

    borrows.reverse()

    data = {
        "Market Index": [pos[2] for pos in borrows],
        "Value": [f"${pos[0]:,.2f}" for pos in borrows],
        "Scaled Balance": [f"{pos[3]:,.2f}" for pos in borrows],
        "Leverage": [f"{pos[4]:,.2f}" for pos in borrows],
        "Public Key": [pos[1] for pos in borrows],
    }

    return data


def price_shock_plot(levs, oracle_distort):
    # perp_market_inspect = 0 # sol-perp
    # def get_rattt(row):
    #     # st.write(row)
    #     df1 = pd.Series([val/row['spot_asset'] * (row['perp_liability']+row['spot_liability']) 
    #                     if val > 0 else 0 for key,val in row['net_v'].items()]
    #                     )
    #     df1.index = ['spot_'+str(x)+'_all' for x in df1.index]

    #     df2 = pd.Series([val/(row['spot_asset']) * (row['perp_liability']) 
    #                     if val > 0 else 0 for key,val in row['net_v'].items()]
    #                     )
    #     df2.index = ['spot_'+str(x)+'_all_perp' for x in df2.index]

    #     df3 = pd.Series([val/(row['spot_asset']) * (row['spot_liability']) 
    #                     if val > 0 else 0 for key,val in row['net_v'].items()]
    #                     )
    #     df3.index = ['spot_'+str(x)+'_all_spot' for x in df3.index]
        
    #     df4 = pd.Series([val/(row['spot_asset']) * (row['net_p'][perp_market_inspect]) 
    #                     if val > 0 and row['net_p'][0] > 0 else 0 for key,val in row['net_v'].items()]
    #                     )
    #     df4.index = ['spot_'+str(x)+'_perp_'+str(perp_market_inspect)+'_long' for x in df4.index]

    #     df5 = pd.Series([val/(row['spot_asset']) * (row['net_p'][perp_market_inspect]) 
    #                     if val > 0 and row['net_p'][perp_market_inspect] < 0 else 0 for key,val in row['net_v'].items()]
    #                     )
    #     df5.index = ['spot_'+str(x)+'_perp_'+str(perp_market_inspect)+'_short' for x in df5.index]
        
    #     dffin = pd.concat([
    #         df1,
    #         df2,
    #         df3,
    #         df4,
    #         df5,
    #     ])
    #     return dffin
    # df = pd.concat([df, df.apply(get_rattt, axis=1)],axis=1)
    # res = pd.DataFrame({('spot'+str(i)): (df["spot_"+str(i)+'_all'].sum(), 
    #                                     df["spot_"+str(i)+'_all_spot'].sum(),
    #                                     df["spot_"+str(i)+'_all_perp'].sum() ,
    #                                     df["spot_"+str(i)+'_perp_'+str(perp_market_inspect)+'_long'].sum(),
    #                                     df["spot_"+str(i)+'_perp_'+str(perp_market_inspect)+'_short'].sum())
    #                                     for i in range(NUMBER_OF_SPOT)},
                                        
                    
    #                 index=['all_liabilities', 'all_spot', 'all_perp', 'perp_0_long', 'perp_0_short'])
    # levs = [df, [df], [df]]
    dfs = [pd.DataFrame(levs[2][i]) for i in range(len(levs[2]))] \
    + [pd.DataFrame(levs[0])] \
    + [pd.DataFrame(levs[1][i]) for i in range(len(levs[1]))]
    
    spot_bankrs = []
    for df in dfs:
        spot_b_t1 = -(df[(df['spot_asset']<df['spot_liability']) & (df['net_usd_value']<0)])
        spot_bankrs.append(-(spot_b_t1['spot_liability'] - spot_b_t1['spot_asset']).sum())

    xdf = [[-df[df['net_usd_value']<0]['net_usd_value'].sum() for df in dfs],
            spot_bankrs
        ]
    toplt_fig = pd.DataFrame(xdf, 
                                index=['bankruptcy', 'spot bankrupt'],
                                columns=[oracle_distort*(i+1)*-100 for i in range(len(levs[2]))]\
                                +[0]\
                                +[oracle_distort*(i+1)*100 for i in range(len(levs[1]))]).T
    toplt_fig['perp bankrupt'] = toplt_fig['bankruptcy'] - toplt_fig['spot bankrupt']
    toplt_fig = toplt_fig.sort_index()
    toplt_fig = toplt_fig.plot()
        # Customize the layout if needed
    toplt_fig.update_layout(title='Bankruptcies in crypto price scenarios',
                    xaxis_title='Oracle Move (%)',
                    yaxis_title='Bankruptcy ($)')
    st.plotly_chart(toplt_fig)
    # st.write(df[df['spot_asset']<df['spot_liability']])
        

def main():
    st.set_page_config(layout="wide")

    url = os.getenv("RPC_URL", "🤫")

    rpc = st.sidebar.text_input("RPC URL", value=url)

    if rpc == "🤫" or rpc == "":
        st.warning("Please enter a Solana RPC URL")
    else:
        drift_client = DriftClient(
            AsyncClient(rpc),
            Wallet.dummy(),
            account_subscription=AccountSubscriptionConfig("cached"),
        )

        # start_sub = time.time()
        loop = asyncio.new_event_loop()
        # loop.run_until_complete(dc.subscribe())
        # print(f"subscribed in {time.time() - start_sub}")

        newest_snapshot = load_newest_files(os.getcwd() + "/pickles")

        start_load_vat = time.time()
        vat = loop.run_until_complete(load_vat(drift_client, newest_snapshot))
        print(f"loaded vat in {time.time() - start_load_vat}")

        st.write(len([x for x in vat.users.values()]), 'users loaded')
        health_distribution = get_account_health_distribution(vat)

        with st.container():
            st.plotly_chart(health_distribution, use_container_width=True)

        perp_col, spot_col = st.columns([1, 1])

        with perp_col:
            largest_perp_positions = get_largest_perp_positions(vat)
            st.markdown("### **Largest perp positions:**")
            st.table(largest_perp_positions)
            most_levered_positions = get_most_levered_perp_positions_above_1m(vat)
            st.markdown("### **Most levered perp positions > $1m:**")
            st.table(most_levered_positions)

        with spot_col:
            largest_spot_borrows = get_largest_spot_borrows(vat)
            st.markdown("### **Largest spot borrows:**")
            st.table(largest_spot_borrows)
            most_levered_borrows = get_most_levered_spot_borrows_above_1m(vat)
            st.markdown("### **Most levered spot borrows > $750k:**")
            st.table(most_levered_borrows)


main()
