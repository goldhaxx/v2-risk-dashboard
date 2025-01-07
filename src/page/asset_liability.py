import pandas as pd
import streamlit as st
import json
import requests
import logging
from enum import Enum
from driftpy.constants.perp_markets import mainnet_perp_market_configs
from driftpy.constants.spot_markets import mainnet_spot_market_configs

from lib.api import api2
from utils import get_current_slot

# Configure logging
logging.basicConfig(
    filename='logs/price_impact.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class PriceImpactStatus(str, Enum):
    PASS = "✅"  # Price impact is below threshold
    NO_BALANCE = "ℹ️"  # No balance to check
    QUOTE_TOKEN = "�"  # USDC or quote token
    FAIL = "❌"  # Price impact above threshold

def calculate_effective_leverage(assets: float, liabilities: float) -> float:
    """Calculate the effective leverage ratio (liabilities/assets)."""
    return liabilities / assets if assets != 0 else 0

def format_metric(
    value: float, should_highlight: bool, mode: int, financial: bool = False
) -> str:
    """Format a metric value with optional highlighting and financial notation.
    
    Args:
        value: The numeric value to format
        should_highlight: Whether to add a checkmark
        mode: The current display mode
        financial: Whether to use financial notation (commas for thousands)
    """
    formatted = f"{value:,.2f}" if financial else f"{value:.2f}"
    return f"{formatted} ✅" if should_highlight and mode > 0 else formatted

def get_jupiter_quote(input_mint: str, output_mint: str, amount: int) -> float:
    """Get price impact quote from Jupiter DEX API.
    
    Args:
        input_mint: Token being sold
        output_mint: Token being bought
        amount: Amount in base units (lamports)
    
    Returns:
        Price impact as a decimal (e.g., 0.01 = 1%)
    """
    # Skip if trying to swap same token
    if input_mint == output_mint:
        logging.info("Input and output mints are the same, skipping Jupiter quote")
        return 0
        
    base_url = "https://quote-api.jup.ag/v6/quote"
    params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": str(amount),
        "slippageBps": 50  # 0.5% slippage tolerance
    }
    
    logging.info(f"Requesting Jupiter quote with params: {params}")
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if "error" in data:
            logging.error(f"Jupiter API error: {data.get('error')} (code: {data.get('errorCode')})")
            return 0
            
        price_impact = float(data.get("priceImpactPct", 0))
        logging.info(f"Jupiter quote received. Price impact: {price_impact}")
        return price_impact
    except requests.RequestException as e:
        logging.error(f"Error fetching Jupiter quote: {str(e)}")
        return 0

def get_largest_spot_borrow_per_market():
    """Fetch the largest spot borrow for each market from the API.
    
    Returns:
        Dictionary containing:
        - market_indices: List of market indices
        - scaled_balances: List of borrow amounts in token units
        - values: List of USD values of the borrows
        - public_keys: List of borrower public keys
    """
    logging.info("Fetching largest spot borrows per market")
    try:
        response = api2("health/largest_spot_borrow_per_market")
        result = {
            "market_indices": response["Market Index"],
            "scaled_balances": [float(bal.replace(",", "")) for bal in response["Scaled Balance"]],
            "values": [float(val.replace("$", "").replace(",", "")) for val in response["Value"]],
            "public_keys": response["Public Key"]
        }
        logging.info(f"Largest spot borrows per market received: {result}")
        return result
    except Exception as e:
        logging.error(f"Error fetching largest spot borrows per market: {str(e)}")
        return {
            "market_indices": [], 
            "scaled_balances": [],
            "values": [],
            "public_keys": []
        }

def get_maintenance_asset_weight(market_index: int) -> float:
    """Get the maintenance asset weight for a market from the market data file."""
    logging.info(f"Getting maintenance asset weight for market {market_index}")
    try:
        with open("Full_Transposed_Market_Data_improved.json", "r") as f:
            market_data = json.load(f)
            for market in market_data.values():
                if market.get("spot_market.market_index") == market_index:
                    weight = float(market.get("spot_market.maintenance_asset_weight", 0.9))
                    logging.info(f"Found maintenance asset weight for market {market_index}: {weight}")
                    return weight
        logging.warning(f"Market {market_index} not found in market data, using default weight")
        return 0.9
    except Exception as e:
        logging.error(f"Error reading market data: {str(e)}")
        return 0.9

def check_price_impact(market_index: int, scaled_balance: float) -> PriceImpactStatus:
    """Check if liquidating a position would have too much price impact."""
    logging.info(f"Checking price impact for market {market_index} with scaled balance {scaled_balance}")
    try:
        market_config = next(
            (m for m in mainnet_spot_market_configs if m.market_index == market_index),
            None
        )
        if not market_config:
            logging.warning(f"Market config not found for index {market_index}")
            return PriceImpactStatus.PASS
            
        if market_config.symbol == "USDC":
            logging.info("USDC market detected, skipping price impact check")
            return PriceImpactStatus.QUOTE_TOKEN
            
        if scaled_balance == 0:
            logging.info("Scaled balance is 0, skipping price impact check")
            return PriceImpactStatus.NO_BALANCE
            
        usdc_config = next(
            (m for m in mainnet_spot_market_configs if m.symbol == "USDC"),
            None
        )
        if not usdc_config:
            logging.warning("USDC market config not found")
            return PriceImpactStatus.PASS
            
        maint_asset_weight = get_maintenance_asset_weight(market_index)
        threshold = 1 - maint_asset_weight
        logging.info(f"Threshold calculated: {threshold} (1 - {maint_asset_weight})")
        
        # Read decimals
        try:
            with open("Full_Transposed_Market_Data_improved.json", "r") as f:
                market_data = json.load(f)
                decimals = 6
                for market in market_data.values():
                    if market.get("spot_market.market_index") == market_index:
                        decimals = int(market.get("spot_market.decimals", 6))
                        break
        except Exception as e:
            logging.error(f"Error reading decimals from market data: {str(e)}")
            decimals = 6
            
        amount = int(scaled_balance * (10 ** decimals))
        logging.info(f"Calculated amount in base units: {amount} (using {decimals} decimals)")
        
        price_impact = get_jupiter_quote(
            market_config.mint,
            usdc_config.mint,
            amount
        )
        
        result = price_impact < threshold
        logging.info(f"Price impact check result: {result} (impact: {price_impact} < threshold: {threshold})")
        return PriceImpactStatus.PASS if result else PriceImpactStatus.FAIL
    except Exception as e:
        logging.error(f"Error in price impact check: {str(e)}")
        return PriceImpactStatus.PASS


def check_spot_leverage(market_index: int, assets: float, liabilities: float, maintenance_asset_weight: float) -> str:
    """
    Criterion 2: Effective Leverage (Spot Positions)
    Pass if (liabilities / assets) < (0.5 * maintenance_asset_weight).
    """
    if assets <= 0:
        return "ℹ️"  # No assets case
    spot_effective_leverage = liabilities / assets
    threshold = 0.5 * maintenance_asset_weight
    return "✅" if spot_effective_leverage < threshold else "❌"


def generate_summary_data(
    df: pd.DataFrame, mode: int, perp_market_index: int
) -> pd.DataFrame:
    """Generate summary statistics for each market."""
    logging.info("Generating summary data")
    summary_data = {}
    
    # Largest spot borrows
    largest_borrows = get_largest_spot_borrow_per_market()
    
    for i in range(len(mainnet_spot_market_configs)):
        prefix = f"spot_{i}"
        assets = df[f"{prefix}_all_assets"].sum()
        liabilities = df[f"{prefix}_all"].sum()
        
        # find scaled_balance for this market
        try:
            idx = largest_borrows["market_indices"].index(i)
            scaled_balance = largest_borrows["scaled_balances"][idx]
        except (ValueError, IndexError):
            scaled_balance = 0
        
        # Price impact check
        price_impact_status = check_price_impact(i, scaled_balance)
        tooltip_map = {
            PriceImpactStatus.PASS: "Price impact is below threshold - safe to liquidate",
            PriceImpactStatus.NO_BALANCE: "No balance to check - informational only",
            PriceImpactStatus.QUOTE_TOKEN: "USDC or quote token - no price impact check needed",
            PriceImpactStatus.FAIL: "Price impact above threshold - unsafe to liquidate"
        }
        tooltip = tooltip_map.get(price_impact_status, "Unknown")
        price_impact_check = f'<span title="{tooltip}">{price_impact_status}</span>'
        
        # Get maintenance asset weight
        maint_asset_weight = get_maintenance_asset_weight(i)
        
        # Check #2: Effective Leverage (Spot Positions)
        spot_leverage_result = check_spot_leverage(i, assets, liabilities, maint_asset_weight)
        spot_leverage_tooltip = (
            "Spot Effective Leverage must be < 0.5 * maint_asset_weight to PASS."
        )
        spot_leverage_check = f'<span title="{spot_leverage_tooltip}">{spot_leverage_result}</span>'
        
        # Optionally set "Target Scale IAW" example if both checks pass
        # (Real logic for all 4 criteria would go here eventually)
        if price_impact_status == PriceImpactStatus.PASS and spot_leverage_result == "✅":
            target_scale_iaw_value = 1.2 * assets
        else:
            target_scale_iaw_value = 0.0  # or "N/A"
        
        # Build summary
        summary_data[f"spot{i}"] = {
            "all_assets": assets,
            "all_liabilities": format_metric(
                liabilities, 0 < liabilities < 1_000_000, mode, financial=True
            ),
            "effective_leverage": format_metric(
                calculate_effective_leverage(assets, liabilities),
                0 < calculate_effective_leverage(assets, liabilities) < 2,
                mode,
            ),
            "all_spot": df[f"{prefix}_all_spot"].sum(),
            "all_perp": df[f"{prefix}_all_perp"].sum(),
            f"perp_{perp_market_index}_long": df[f"{prefix}_perp_{perp_market_index}_long"].sum(),
            f"perp_{perp_market_index}_short": df[f"{prefix}_perp_{perp_market_index}_short"].sum(),
            "price_impact_check": price_impact_check,
            "spot_leverage_check": spot_leverage_check,
            "target_scale_iaw": f"{target_scale_iaw_value:,.2f}" if target_scale_iaw_value else "N/A"
        }
    
    logging.info("Summary data generation complete")
    return pd.DataFrame(summary_data).T

def asset_liab_matrix_cached_page():
    """Main Streamlit page for displaying the asset-liability matrix."""
    if "min_leverage" not in st.session_state:
        st.session_state.min_leverage = 0.0
    if "only_high_leverage_mode_users" not in st.session_state:
        st.session_state.only_high_leverage_mode_users = False

    params = st.query_params
    mode = int(params.get("mode", 0))
    perp_market_index = int(params.get("perp_market_index", 0))

    mode_labels = [
        "none",
        "liq within 50% of oracle",
        "maint. health < 10%",
        "init. health < 10%",
    ]
    mode_options = [0, 1, 2, 3]

    mode = st.selectbox(
        "Options", mode_options, format_func=lambda x: mode_labels[x], index=mode_options.index(mode)
    )
    st.query_params.update({"mode": str(mode)})

    perp_market_index = st.selectbox(
        "Market index",
        [x.market_index for x in mainnet_perp_market_configs],
        index=[x.market_index for x in mainnet_perp_market_configs].index(perp_market_index),
        format_func=lambda x: f"{x} ({mainnet_perp_market_configs[int(x)].symbol})",
    )
    st.query_params.update({"perp_market_index": str(perp_market_index)})

    result = api2(
        "asset-liability/matrix",
        _params={"mode": mode, "perp_market_index": perp_market_index},
        key=f"asset-liability/matrix_{mode}_{perp_market_index}",
    )
    df = pd.DataFrame(result["df"])

    if st.session_state.only_high_leverage_mode_users:
        df = df[df["is_high_leverage"]]

    filtered_df = df[df["leverage"] >= st.session_state.min_leverage].sort_values(
        "leverage", ascending=False
    )

    summary_df = generate_summary_data(filtered_df, mode, perp_market_index)
    slot = result["slot"]
    current_slot = get_current_slot()

    st.info(
        f"This data is for slot {slot}, which is now {int(current_slot) - int(slot)} slots old"
    )
    st.write(f"{df.shape[0]} users")
    st.checkbox(
        "Only show high leverage mode users", key="only_high_leverage_mode_users"
    )
    st.slider(
        "Filter by minimum leverage",
        0.0,
        110.0,
        0.0,
        key="min_leverage",
    )

    # Add tooltip to price_impact_check column header
    price_impact_check_header = '<span title="Indicates if liquidating a position would have too much price impact. Calculated based on the largest spot borrow per market and compared against the maintenance asset weight.">Price Impact Check</span>'
    spot_leverage_check_header = '<span title="Pass if (Spot Liabilities/Spot Assets) < 0.5 * maintenance_asset_weight.">Spot Leverage Check</span>'

    # Also rename the last column with a tooltip about how "Target Scale IAW" is set
    target_scale_iaw_header = '<span title="If both price impact and spot leverage checks pass, we set 1.2x of spot assets for demonstration.">Target Scale IAW</span>'

    rename_map = {}
    for col in summary_df.columns:
        if col == "price_impact_check":
            rename_map[col] = price_impact_check_header
        elif col == "spot_leverage_check":
            rename_map[col] = spot_leverage_check_header
        elif col == "target_scale_iaw":
            rename_map[col] = target_scale_iaw_header

    summary_df = summary_df.rename(columns=rename_map)

    st.write(summary_df.to_html(escape=False), unsafe_allow_html=True)

    tabs = st.tabs(["FULL"] + [x.symbol for x in mainnet_spot_market_configs])

    with tabs[0]:
        if st.session_state.only_high_leverage_mode_users:
            st.write(
                f"There are **{len(filtered_df)}** users with high leverage mode and {st.session_state.min_leverage}x leverage or more"
            )
        else:
            st.write(
                f"There are **{len(filtered_df)}** users with this **{st.session_state.min_leverage}x** leverage or more"
            )
        st.write(f"Total USD value: **{filtered_df['net_usd_value'].sum():,.2f}**")
        st.write(f"Total collateral: **{filtered_df['spot_asset'].sum():,.2f}**")
        st.write(f"Total liabilities: **{filtered_df['spot_liability'].sum():,.2f}**")
        st.dataframe(filtered_df, hide_index=True)

    for idx, tab in enumerate(tabs[1:]):
        important_cols = [x for x in filtered_df.columns if "spot_" + str(idx) in x]
        toshow = filtered_df[["user_key", "spot_asset", "net_usd_value"] + important_cols]
        toshow = toshow[toshow[important_cols].abs().sum(axis=1) != 0].sort_values(
            by="spot_" + str(idx) + "_all", ascending=False
        )
        tab.write(
            f"{len(toshow)} users with this asset to cover liabilities (with {st.session_state.min_leverage}x leverage or more)"
        )
        tab.dataframe(toshow, hide_index=True)