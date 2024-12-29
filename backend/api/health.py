import heapq

import pandas as pd
from driftpy.constants import BASE_PRECISION, PRICE_PRECISION, SPOT_BALANCE_PRECISION
from driftpy.pickle.vat import Vat
from driftpy.types import is_variant
from fastapi import APIRouter
from pydantic import BaseModel

from backend.state import BackendRequest

router = APIRouter()


def to_financial(num: float):
    """
    Helper function to format a number to a financial format.
    """
    num_str = str(num)
    decimal_pos = num_str.find(".")
    if decimal_pos != -1:
        return float(num_str[: decimal_pos + 3])
    return num


@router.get("/health_distribution")
def get_account_health_distribution(request: BackendRequest):
    """
    Get the distribution of account health across different ranges.

    This endpoint calculates the distribution of account health for all users,
    categorizing them into health ranges and summing up the total collateral
    in each range.

    Returns:
        list[dict]: A list of dictionaries containing the health distribution data.
        Each dictionary has the following keys:
        - Health Range (str): The health percentage range (e.g., '0-10%')
        - Counts (int): The number of accounts in this range
        - Notional Values (float): The total collateral value in this range
    """
    vat: Vat = request.state.backend_state.vat
    health_notional_distributions = {
        "0-10%": 0.0,
        "10-20%": 0.0,
        "20-30%": 0.0,
        "30-40%": 0.0,
        "40-50%": 0.0,
        "50-60%": 0.0,
        "60-70%": 0.0,
        "70-80%": 0.0,
        "80-90%": 0.0,
        "90-100%": 0.0,
    }
    health_counts = {
        "0-10%": 0.0,
        "10-20%": 0.0,
        "20-30%": 0.0,
        "30-40%": 0.0,
        "40-50%": 0.0,
        "50-60%": 0.0,
        "60-70%": 0.0,
        "70-80%": 0.0,
        "80-90%": 0.0,
        "90-100%": 0.0,
    }

    for user in vat.users.values():
        try:
            total_collateral = user.get_total_collateral() / PRICE_PRECISION
            current_health = user.get_health()
        except Exception as e:
            print(f"==> Error from health [{user.user_public_key}] ", e)
            continue
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

    return df.to_dict(orient="records")


@router.get("/largest_perp_positions")
def get_largest_perp_positions(request: BackendRequest):
    """
    Get the top 10 largest perpetual positions by value.

    This endpoint retrieves the largest perpetual positions across all users,
    calculated based on the current market prices.

    Returns:
        dict: A dictionary containing lists of data for the top 10 positions:
        - Market Index (list[int]): The market indices of the top positions
        - Value (list[str]): The formatted dollar values of the positions
        - Base Asset Amount (list[str]): The formatted base asset amounts
        - Public Key (list[str]): The public keys of the position holders
    """
    vat: Vat = request.state.backend_state.vat
    top_positions: list[tuple[float, str, int, float]] = []

    for user in vat.users.values():
        for position in user.get_user_account().perp_positions:
            if position.base_asset_amount > 0:
                market_price = vat.perp_oracles.get(position.market_index)
                if market_price is not None:
                    market_price_ui = market_price.price / PRICE_PRECISION
                    base_asset_value = (
                        abs(position.base_asset_amount) / BASE_PRECISION
                    ) * market_price_ui
                    heap_item = (
                        base_asset_value,
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


@router.get("/most_levered_perp_positions_above_1m")
def get_most_levered_perp_positions_above_1m(request: BackendRequest):
    """
    Get the top 10 most leveraged perpetual positions with value above $1 million.

    This endpoint calculates the leverage of each perpetual position with a value
    over $1 million and returns the top 10 most leveraged positions.

    Returns:
        dict: A dictionary containing lists of data for the top 10 leveraged positions:
        - Market Index (list[int]): The market indices of the top positions
        - Value (list[str]): The formatted dollar values of the positions
        - Base Asset Amount (list[str]): The formatted base asset amounts
        - Leverage (list[str]): The formatted leverage ratios
        - Public Key (list[str]): The public keys of the position holders
    """
    vat: Vat = request.state.backend_state.vat
    top_positions: list[tuple[float, str, int, float, float]] = []

    for user in vat.users.values():
        try:
            total_collateral = user.get_total_collateral() / PRICE_PRECISION
        except Exception as e:
            print(
                f"==> Error from get_most_levered_perp_positions_above_1m [{user.user_public_key}] ",
                e,
            )
            continue
        if total_collateral > 0:
            for position in user.get_user_account().perp_positions:
                if position.base_asset_amount > 0:
                    market_price = vat.perp_oracles.get(position.market_index)
                    if market_price is not None:
                        market_price_ui = market_price.price / PRICE_PRECISION
                        base_asset_value = (
                            abs(position.base_asset_amount) / BASE_PRECISION
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


@router.get("/largest_spot_borrows")
def get_largest_spot_borrows(request: BackendRequest):
    """
    Get the top 10 largest spot borrowing positions by value.

    This endpoint retrieves the largest spot borrowing positions across all users,
    calculated based on the current market prices.

    Returns:
        dict: A dictionary containing lists of data for the top 10 borrowing positions:
        - Market Index (list[int]): The market indices of the top borrows
        - Value (list[str]): The formatted dollar values of the borrows
        - Scaled Balance (list[str]): The formatted scaled balances of the borrows
        - Public Key (list[str]): The public keys of the borrowers
    """
    vat: Vat = request.state.backend_state.vat
    top_borrows: list[tuple[float, str, int, float]] = []

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


@router.get("/most_levered_spot_borrows_above_1m")
def get_most_levered_spot_borrows_above_1m(request: BackendRequest):
    """
    Get the top 10 most leveraged spot borrowing positions with value above $750,000.

    This endpoint calculates the leverage of each spot borrowing position with a value
    over $750,000 and returns the top 10 most leveraged positions.

    Returns:
        dict: A dictionary containing lists of data for the top 10 leveraged borrowing positions:
        - Market Index (list[int]): The market indices of the top borrows
        - Value (list[str]): The formatted dollar values of the borrows
        - Scaled Balance (list[str]): The formatted scaled balances of the borrows
        - Leverage (list[str]): The formatted leverage ratios
        - Public Key (list[str]): The public keys of the borrowers
    """
    vat: Vat = request.state.backend_state.vat
    top_borrows: list[tuple[float, str, int, float, float]] = []

    for user in vat.users.values():
        try:
            total_collateral = user.get_total_collateral() / PRICE_PRECISION
        except Exception as e:
            print(
                f"==> Error from get_most_levered_spot_borrows_above_1m [{user.user_public_key}] ",
                e,
            )
            raise e
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


@router.get("/spot_asset_value/{wallet_address}")
async def get_spot_asset_value(request: BackendRequest, wallet_address: str):
    """
    Get the spot asset value for a specific wallet address.

    Args:
        wallet_address (str): The public key/wallet address to query as URL parameter

    Returns:
        dict: A dictionary containing the spot asset value for the wallet:
        - spot_asset_value (float): The total spot asset value in USD
        - wallet_address (str): The queried wallet address
    """
    vat: Vat = request.state.backend_state.vat
    
    # Try to find the user in the vat
    user = vat.users.get(wallet_address)
    if user is None:
        return {
            "error": "Wallet address not found",
            "wallet_address": wallet_address,
            "spot_asset_value": 0
        }

    try:
        spot_asset_value = user.get_spot_market_asset_value(None, None) / PRICE_PRECISION
        return {
            "wallet_address": wallet_address,
            "spot_asset_value": spot_asset_value
        }
    except Exception as e:
        return {
            "error": str(e),
            "wallet_address": wallet_address,
            "spot_asset_value": 0
        }
