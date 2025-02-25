import pandas as pd
import streamlit as st
from driftpy.constants.perp_markets import mainnet_perp_market_configs
from driftpy.constants.spot_markets import mainnet_spot_market_configs

from lib.api import fetch_cached_data
from utils import get_current_slot

options = [0, 1, 2, 3]
labels = [
    "none",
    "liq within 50% of oracle",
    "maint. health < 10%",
    "init. health < 10%",
]


def calculate_effective_leverage(assets: float, liabilities: float) -> float:
    return liabilities / assets if assets != 0 else 0


def format_metric(
    value: float, should_highlight: bool, mode: int, financial: bool = False
) -> str:
    formatted = f"{value:,.2f}" if financial else f"{value:.2f}"
    return f"{formatted} ✅" if should_highlight and mode > 0 else formatted


def generate_summary_data(
    df: pd.DataFrame, mode: int, perp_market_index: int
) -> pd.DataFrame:
    summary_data = {}
    for i in range(len(mainnet_spot_market_configs)):
        prefix = f"spot_{i}"
        assets = df[f"{prefix}_all_assets"].sum()
        liabilities = df[f"{prefix}_all"].sum()

        summary_data[f"spot{i} ({mainnet_spot_market_configs[i].symbol})"] = {
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
            f"perp_{perp_market_index}_long": df[
                f"{prefix}_perp_{perp_market_index}_long"
            ].sum(),
            f"perp_{perp_market_index}_short": df[
                f"{prefix}_perp_{perp_market_index}_short"
            ].sum(),
        }
    return pd.DataFrame(summary_data).T


def asset_liab_matrix_cached_page():
    if "only_high_leverage_mode_users" not in st.session_state:
        st.session_state.only_high_leverage_mode_users = False
    if "min_leverage" not in st.session_state:
        st.session_state.min_leverage = 0.0

    params = st.query_params
    mode = int(params.get("mode", 0))
    perp_market_index = int(params.get("perp_market_index", 0))

    mode = st.selectbox(
        "Options", options, format_func=lambda x: labels[x], index=options.index(mode)
    )
    st.query_params.update({"mode": str(mode)})

    perp_market_index = st.selectbox(
        "Market index",
        [x.market_index for x in mainnet_perp_market_configs],
        index=[x.market_index for x in mainnet_perp_market_configs].index(
            perp_market_index
        ),
        format_func=lambda x: f"{x} ({mainnet_perp_market_configs[int(x)].symbol})",
    )
    st.query_params.update({"perp_market_index": str(perp_market_index)})

    result = fetch_cached_data(
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
        key="min_leverage",
    )
    st.write(summary_df)

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
        filtered_df["Link"] = filtered_df["user_key"].apply(
            lambda x: f"https://app.drift.trade/overview?userAccount={x}"
        )
        toshow = filtered_df[
            ["user_key", "Link", "spot_asset", "net_usd_value"] + important_cols
        ]
        toshow = toshow[toshow[important_cols].abs().sum(axis=1) != 0].sort_values(
            by="spot_" + str(idx) + "_all", ascending=False
        )
        tab.write(
            f"{len(toshow)} users with this asset to cover liabilities (with {st.session_state.min_leverage}x leverage or more)"
        )
        tab.dataframe(
            toshow,
            hide_index=True,
            column_config={
                "Link": st.column_config.LinkColumn("Link", display_text="View"),
            },
        )
