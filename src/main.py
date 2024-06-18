import asyncio
import heapq
import time
import os

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
from driftpy.types import OraclePriceData, is_variant
from driftpy.pickle.vat import Vat

from utils import load_newest_files, load_vat, to_financial


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


def main():
    st.set_page_config(layout="wide")
    env = st.sidebar.radio("env", ("mainnet-beta", "devnet"))

    url = "🤫"
    if env == "devnet":
        url = "https://api." + env + ".solana.com"
    else:
        url = "🤫"

    if url == "🤫" or url == "":
        url = os.getenv("RPC_URL")

    rpc = st.sidebar.text_input("rpc", url)

    dc = DriftClient(
        AsyncClient(rpc),
        Wallet.dummy(),
        account_subscription=AccountSubscriptionConfig("cached"),
    )

    start_sub = time.time()
    loop = asyncio.new_event_loop()
    loop.run_until_complete(dc.subscribe())
    print(f"subscribed in {time.time() - start_sub}")

    newest_snapshot = load_newest_files(os.getcwd() + "/pickles")

    start_load_vat = time.time()
    vat = loop.run_until_complete(load_vat(dc, newest_snapshot))
    print(f"loaded vat in {time.time() - start_load_vat}")

    perp_col, spot_col = st.columns([1, 1])

    largest_perp_positions = get_largest_perp_positions(vat)

    with perp_col:
        st.markdown("### **Largest perp positions:**")
        st.table(largest_perp_positions)

    largest_spot_borrows = get_largest_spot_borrows(vat)

    with spot_col:
        st.markdown("### **Largest spot borrows:**")
        st.table(largest_spot_borrows)


main()
