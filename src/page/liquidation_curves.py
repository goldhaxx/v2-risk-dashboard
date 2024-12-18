from collections import defaultdict
import time

from lib.api import api
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from utils import fetch_result_with_retry


def plot_liquidation_curves(liquidation_data):
    liquidations_long = liquidation_data["liquidations_long"]
    liquidations_short = liquidation_data["liquidations_short"]
    market_price_ui = liquidation_data["market_price_ui"]

    def filter_outliers(
        liquidations, upper_bound_multiplier=2.0, lower_bound_multiplier=0.5
    ):
        """Filter out liquidations based on a range multiplier of the market price."""
        return [
            (price, notional, pubkey)
            for price, notional, pubkey in liquidations
            if lower_bound_multiplier * market_price_ui
            <= price
            <= upper_bound_multiplier * market_price_ui
        ]

    def aggregate_liquidations(liquidations):
        """Aggregate liquidations to calculate cumulative notional amounts and track pubkeys with their sizes."""
        price_to_data = defaultdict(lambda: {"notional": 0.0, "positions": []})
        for price, notional, pubkey in liquidations:
            price_to_data[price]["notional"] += notional
            price_to_data[price]["positions"].append(
                (pubkey, notional)
            )  # Store tuple of (pubkey, size)
        return price_to_data

    def prepare_data_for_plot(aggregated_data, reverse=False):
        """Prepare and sort data for plotting, optionally reversing the cumulative sum for descending plots."""
        sorted_prices = sorted(aggregated_data.keys(), reverse=reverse)
        cumulative_notional = np.cumsum(
            [aggregated_data[price]["notional"] for price in sorted_prices]
        )
        # Accumulate positions (pubkey and size) for each price point
        cumulative_positions = []
        current_positions = []
        for price in sorted_prices:
            current_positions.extend(aggregated_data[price]["positions"])
            cumulative_positions.append(list(current_positions))
        return sorted_prices, cumulative_notional, cumulative_positions

    # Filter outliers based on defined criteria
    liquidations_long = filter_outliers(
        liquidations_long, 2, 0.2
    )  # Example multipliers for long positions
    liquidations_short = filter_outliers(
        liquidations_short, 5, 0.5
    )  # Example multipliers for short positions

    # Aggregate and prepare data
    aggregated_long = aggregate_liquidations(liquidations_long)
    aggregated_short = aggregate_liquidations(liquidations_short)

    long_prices, long_cum_notional, long_pubkeys = prepare_data_for_plot(
        aggregated_long, reverse=True
    )
    short_prices, short_cum_notional, short_pubkeys = prepare_data_for_plot(
        aggregated_short
    )

    if not long_prices or not short_prices:
        return None

    # Create Plotly figures
    long_fig = go.Figure()
    short_fig = go.Figure()

    # Add traces for long and short positions
    long_fig.add_trace(
        go.Scatter(
            x=long_prices,
            y=long_cum_notional,
            mode="lines",
            name="Long Positions",
            line=dict(color="purple", width=2),
            hovertemplate="Price: %{x}<br>Cumulative Notional: %{y}<br>Accounts: %{text}<extra></extra>",
            text=[f"{len(pubkeys)} accounts" for pubkeys in long_pubkeys],
        )
    )
    short_fig.add_trace(
        go.Scatter(
            x=short_prices,
            y=short_cum_notional,
            mode="lines",
            name="Short Positions",
            line=dict(color="turquoise", width=2),
            hovertemplate="Price: %{x}<br>Cumulative Notional: %{y}<br>Accounts: %{text}<extra></extra>",
            text=[f"{len(pubkeys)} accounts" for pubkeys in short_pubkeys],
        )
    )

    # Update layout with axis titles and grid settings
    long_fig.update_layout(
        title="Long Liquidation Curve",
        xaxis_title="Asset Price",
        yaxis_title="Liquidations (Notional)",
        xaxis=dict(showgrid=True),
        yaxis=dict(showgrid=True),
    )

    short_fig.update_layout(
        title="Short Liquidation Curve",
        xaxis_title="Asset Price",
        yaxis_title="Liquidations (Notional)",
        xaxis=dict(showgrid=True),
        yaxis=dict(showgrid=True),
    )

    return long_fig, short_fig, long_pubkeys, short_pubkeys, long_prices, short_prices


def liquidation_curves_page():
    options = [0, 1]
    labels = ["SOL-PERP", "BTC-PERP"]
    st.write("Liquidation Curves")

    # Get query parameters
    params = st.query_params
    market_index = int(params.get("market_index", 0))

    market_index = st.selectbox(
        "Market",
        options,
        format_func=lambda x: labels[x],
        index=options.index(market_index),
    )

    st.query_params.update({"market_index": market_index})

    try:
        liquidation_data = fetch_result_with_retry(
            api, "liquidation", "liquidation-curve", params=params, as_json=True
        )
        if liquidation_data is None:
            st.write("Fetching data for the first time...")
            st.image(
                "https://i.gifer.com/origin/8a/8a47f769c400b0b7d81a8f6f8e09a44a_w200.gif"
            )
            st.write("Check again in one minute!")
            st.stop()

    except Exception as e:
        st.write(e)
        st.stop()

    # Unpack all returned values
    (long_fig, short_fig, long_pubkeys, short_pubkeys, long_prices, short_prices) = (
        plot_liquidation_curves(liquidation_data)
    )

    long_col, short_col = st.columns([1, 1])

    with long_col:
        st.plotly_chart(long_fig, use_container_width=True)

        # Add accordion for long positions
        with st.expander("Long Position Accounts"):
            if long_pubkeys and len(long_pubkeys[-1]) > 0:
                st.write(f"Total Accounts: {len(long_pubkeys[-1])}")
                long_data = []
                for i, positions in enumerate(long_pubkeys):
                    if i > 0:
                        new_positions = set(positions) - set(long_pubkeys[i - 1])
                        if new_positions:
                            for pubkey, size in new_positions:
                                long_data.append(
                                    {
                                        "Price": f"{long_prices[i]:.2f}",
                                        "Size": f"{size:,.2f}",
                                        "Account": pubkey,
                                        "Link": f"https://app.drift.trade/overview?userAccount={pubkey}",
                                    }
                                )
                if long_data:
                    st.dataframe(
                        long_data,
                        column_config={
                            "Price": st.column_config.TextColumn("Price"),
                            "Size": st.column_config.TextColumn("Size"),
                            "Account": st.column_config.TextColumn(
                                "Account", width="large"
                            ),
                            "Link": st.column_config.LinkColumn(
                                "Link", display_text="View"
                            ),
                        },
                        hide_index=True,
                    )
            else:
                st.write("No long positions found")

    with short_col:
        st.plotly_chart(short_fig, use_container_width=True)

        with st.expander("Short Position Accounts"):
            if short_pubkeys and len(short_pubkeys[-1]) > 0:
                st.write(f"Total Accounts: {len(short_pubkeys[-1])}")
                short_data = []
                for i, positions in enumerate(short_pubkeys):
                    if i > 0:
                        new_positions = set(positions) - set(short_pubkeys[i - 1])
                        if new_positions:
                            for pubkey, size in new_positions:
                                short_data.append(
                                    {
                                        "Price": f"{short_prices[i]:.2f}",
                                        "Size": f"{size:,.2f}",
                                        "Account": pubkey,
                                        "Link": f"https://app.drift.trade/overview?userAccount={pubkey}",
                                    }
                                )
                if short_data:
                    st.dataframe(
                        short_data,
                        column_config={
                            "Price": st.column_config.TextColumn("Price"),
                            "Size": st.column_config.TextColumn("Size"),
                            "Account": st.column_config.TextColumn(
                                "Account", width="large"
                            ),
                            "Link": st.column_config.LinkColumn(
                                "Link", display_text="View"
                            ),
                        },
                        hide_index=True,
                    )
            else:
                st.write("No short positions found")
