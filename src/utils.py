from asyncio import AbstractEventLoop
import pandas as pd
import numpy as np

import os
from typing import Optional

from driftpy.drift_client import DriftClient
from driftpy.pickle.vat import Vat
from driftpy.drift_user_stats import DriftUserStats, UserStatsSubscriptionConfig
from driftpy.user_map.user_map_config import (
    UserMapConfig,
    UserStatsMapConfig,
    WebsocketConfig as UserMapWebsocketConfig,
)
from driftpy.user_map.user_map import UserMap
from driftpy.user_map.userstats_map import UserStatsMap

from driftpy.market_map.market_map_config import (
    MarketMapConfig,
    WebsocketConfig as MarketMapWebsocketConfig,
)
from driftpy.market_map.market_map import MarketMap

from driftpy.types import MarketType, PerpPosition, PerpMarketAccount
from driftpy.drift_user import DriftUser
from driftpy.math.margin import MarginCategory
from driftpy.constants.numeric_constants import (
    PRICE_PRECISION,
    MARGIN_PRECISION,
    QUOTE_PRECISION,
)
from driftpy.math.margin import calculate_size_premium_liability_weight
from scenario import (
    NUMBER_OF_SPOT,
    get_collateral_composition,
    get_perp_liab_composition,
)


def calculate_market_margin_ratio(
    market: PerpMarketAccount, size, margin_category, custom_margin_ratio=0
):
    market_margin_ratio = (
        market.margin_ratio_initial
        if margin_category == MarginCategory.INITIAL
        else market.margin_ratio_maintenance
    )

    margin_ratio = max(
        calculate_size_premium_liability_weight(
            size, market.imf_factor, market_margin_ratio, MARGIN_PRECISION
        ),
        custom_margin_ratio,
    )

    return margin_ratio


def to_financial(num):
    num_str = str(num)
    decimal_pos = num_str.find(".")
    if decimal_pos != -1:
        return float(num_str[: decimal_pos + 3])
    return num


def load_newest_files(directory: Optional[str] = None) -> dict[str, str]:
    directory = directory or os.getcwd()

    newest_files: dict[str, tuple[str, int]] = {}

    prefixes = ["perp", "perporacles", "spot", "spotoracles", "usermap", "userstats"]

    for filename in os.listdir(directory):
        if filename.endswith(".pkl") and any(
            filename.startswith(prefix + "_") for prefix in prefixes
        ):
            start = filename.index("_") + 1
            prefix = filename[: start - 1]
            end = filename.index(".")
            slot = int(filename[start:end])
            if not prefix in newest_files or slot > newest_files[prefix][1]:
                newest_files[prefix] = (directory + "/" + filename, slot)

    # mapping e.g { 'spotoracles' : 'spotoracles_272636137.pkl' }
    prefix_to_filename = {
        prefix: filename for prefix, (filename, _) in newest_files.items()
    }

    return prefix_to_filename


# function assumes that you have already subscribed
# the use of websocket configs in here doesn't matter because the maps are never subscribed to
async def load_vat(
    dc: DriftClient,
    pickle_map: dict[str, str],
    loop: AbstractEventLoop,
    env: str = "prod",
) -> Vat:
    perp = MarketMap(
        MarketMapConfig(
            dc.program, MarketType.Perp(), MarketMapWebsocketConfig(), dc.connection
        )
    )

    spot = MarketMap(
        MarketMapConfig(
            dc.program, MarketType.Spot(), MarketMapWebsocketConfig(), dc.connection
        )
    )

    user = UserMap(UserMapConfig(dc, UserMapWebsocketConfig()))

    stats = UserStatsMap(UserStatsMapConfig(dc))

    user_filename = pickle_map["usermap"]
    stats_filename = pickle_map["userstats"]
    perp_filename = pickle_map["perp"]
    spot_filename = pickle_map["spot"]
    perp_oracles_filename = pickle_map["perporacles"]
    spot_oracles_filename = pickle_map["spotoracles"]

    vat = Vat(dc, user, stats, spot, perp)

    await vat.unpickle(
        user_filename,
        stats_filename,
        spot_filename,
        perp_filename,
        spot_oracles_filename,
        perp_oracles_filename,
    )

    if env == "dev":
        users = []
        for user in vat.users.values():
            value = user.get_net_spot_market_value(None) + user.get_unrealized_pnl(True)
            users.append(
                (value, user.user_public_key, user.get_user_account_and_slot())
            )
        users.sort(key=lambda x: x[0], reverse=True)
        vat.users.clear()
        for user in users[:100]:
            await vat.users.add_pubkey(user[1], user[2])

    print(vat.users.values())

    return vat


def clear_local_pickles(directory: str):
    for filename in os.listdir(directory):
        os.remove(directory + "/" + filename)


def aggregate_perps(vat: Vat, loop: AbstractEventLoop):
    print("aggregating perps")

    def aggregate_perp(user: DriftUser) -> DriftUser:
        agg_perp = PerpPosition(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        sol_price = vat.perp_oracles.get(0).price
        user_account = user.get_user_account()
        sol_market = vat.perp_markets.get(0).data
        for perp_position in user_account.perp_positions:
            if perp_position.base_asset_amount == 0:
                continue
            asset_price = vat.perp_oracles.get(perp_position.market_index).price  # type: ignore

            market = vat.perp_markets.get(perp_position.market_index)
            # ratio transform
            sol_margin_ratio = calculate_market_margin_ratio(
                sol_market, agg_perp.base_asset_amount, MarginCategory.INITIAL
            )
            margin_ratio = calculate_market_margin_ratio(
                market.data, perp_position.base_asset_amount, MarginCategory.INITIAL
            )
            sol_margin_scalar = 1 / (sol_margin_ratio / MARGIN_PRECISION)
            curr_margin_scalar = 1 / (margin_ratio / MARGIN_PRECISION)

            # simple price conversion
            exchange_rate = sol_price / asset_price
            exchange_rate_normalized = exchange_rate / PRICE_PRECISION
            new_baa = perp_position.base_asset_amount * exchange_rate_normalized

            # apply margin ratio transofmr
            new_baa_adjusted = new_baa * (sol_margin_scalar / curr_margin_scalar)

            # aggregate
            agg_perp.base_asset_amount += new_baa_adjusted
            agg_perp.quote_asset_amount += perp_position.quote_asset_amount * (
                sol_margin_scalar / curr_margin_scalar
            )

        if agg_perp.base_asset_amount == 0:
            return None

        # force use this new fake user account for all sdk functions
        user_account.perp_positions = [agg_perp]
        ds = user.account_subscriber.user_and_slot
        ds.data = user_account
        user.account_subscriber.user_and_slot = ds
        return user

    users_list = list(vat.users.values())

    import copy

    # deep copy usermap
    # required or else aggregation affects vat.users which breaks stuff p bad
    usermap = UserMap(UserMapConfig(vat.drift_client, UserMapWebsocketConfig()))
    for user in users_list:
        loop.run_until_complete(
            usermap.add_pubkey(
                copy.deepcopy(user.user_public_key),
                copy.deepcopy(user.get_user_account_and_slot()),
            )
        )

    aggregated_users = [
        user
        for user in (aggregate_perp(user) for user in usermap.values())
        if user is not None
    ]

    aggregated_users = sorted(
        aggregated_users,
        key=lambda x: x.get_total_collateral(MarginCategory.MAINTENANCE)
        + x.get_total_perp_position_value(MarginCategory.MAINTENANCE),
    )

    return aggregated_users

import copy
from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.accounts.types import DataAndSlot

def drift_client_deep_copy(dc: DriftClient) -> DriftClient:
    from solana.rpc.async_api import AsyncClient
    perp_markets = []
    spot_markets = []
    oracle_price_data = {}
    state_account = None
    for market in dc.get_perp_market_accounts():
        perp_markets.append(DataAndSlot(0, copy.deepcopy(market)))
    
    for market in dc.get_spot_market_accounts():
        spot_markets.append(DataAndSlot(0, copy.deepcopy(market)))

    for pubkey, oracle in dc.account_subscriber.cache["oracle_price_data"].items():
        oracle_price_data[copy.deepcopy(pubkey)] = copy.deepcopy(oracle)

    if dc.get_state_account() is not None:
        state_account = copy.deepcopy(dc.account_subscriber.get_state_account_and_slot())

    new_wallet = copy.deepcopy(dc.wallet)
    new_connection = AsyncClient(copy.deepcopy(dc.connection._provider.endpoint_uri))

    new_drift_client = DriftClient(
        new_connection,
        new_wallet,
        account_subscription=AccountSubscriptionConfig("cached"),
    )

    new_drift_client.account_subscriber.cache["perp_markets"] = sorted(perp_markets, key=lambda x: x.data.market_index)
    new_drift_client.account_subscriber.cache["spot_markets"] = sorted(spot_markets, key=lambda x: x.data.market_index)
    new_drift_client.account_subscriber.cache["oracle_price_data"] = oracle_price_data
    new_drift_client.account_subscriber.cache["state_account"] = state_account

    return new_drift_client

def drift_user_deep_copy(user: DriftUser, drift_client: DriftClient) -> DriftUser:
    user_account_and_slot = copy.deepcopy(user.get_user_account_and_slot())
    new_user = DriftUser(
        drift_client,
        copy.deepcopy(user.user_public_key),
        account_subscription=AccountSubscriptionConfig("cached"),
    )
    new_user.account_subscriber.user_and_slot = user_account_and_slot
    return new_user

def drift_user_stats_deep_copy(stats: DriftUserStats, drift_client: DriftClient) -> DriftUserStats:
    new_user_stats = DriftUserStats(
        drift_client,
        copy.deepcopy(stats.user_public_key),
        config=UserStatsSubscriptionConfig(
            initial_data=copy.deepcopy(stats.get_account_and_slot())
        ),
    )

    return new_user_stats

def vat_deep_copy(vat: Vat) -> Vat:
    import time
    start = time.time()
    new_drift_client = drift_client_deep_copy(vat.drift_client)
    print(f"copied drift client in {time.time() - start}")

    new_user_map = UserMap(UserMapConfig(new_drift_client, UserMapWebsocketConfig()))
    new_spot_map = MarketMap(
        MarketMapConfig(
            new_drift_client.program, MarketType.Spot(), MarketMapWebsocketConfig(), new_drift_client.connection
        )
    )
    new_perp_map = MarketMap(
        MarketMapConfig(
            new_drift_client.program, MarketType.Perp(), MarketMapWebsocketConfig(), new_drift_client.connection
        )
    )
    new_perp_oracles = {}
    new_spot_oracles = {}

    start = time.time()
    for market_index, oracle in vat.perp_oracles.items():
        new_perp_oracles[copy.deepcopy(market_index)] = copy.deepcopy(oracle)
    print(f"copied perp oracles in {time.time() - start}")

    start = time.time()
    for market_index, oracle in vat.spot_oracles.items():
        new_spot_oracles[copy.deepcopy(market_index)] = copy.deepcopy(oracle)
    print(f"copied spot oracles in {time.time() - start}")

    start = time.time()
    for pubkey, market in vat.perp_markets.market_map.items():
        new_perp_map.market_map[copy.deepcopy(pubkey)] = copy.deepcopy(market)
    print(f"copied perp markets in {time.time() - start}")

    start = time.time()
    for pubkey, market in vat.spot_markets.market_map.items():
        new_spot_map.market_map[copy.deepcopy(pubkey)] = copy.deepcopy(market)
    print(f"copied spot markets in {time.time() - start}")

    start = time.time()
    for pubkey, user in vat.users.user_map.items():
        new_user_map.user_map[str(copy.deepcopy(pubkey))] = drift_user_deep_copy(user, new_drift_client)
    print(f"copied users in {time.time() - start}")

    new_vat = Vat(new_drift_client, new_user_map, vat.user_stats, new_spot_map, new_perp_map)
    new_vat.perp_oracles = new_perp_oracles
    new_vat.spot_oracles = new_spot_oracles

    return new_vat
