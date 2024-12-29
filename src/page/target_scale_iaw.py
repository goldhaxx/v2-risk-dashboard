import plotly.express as px
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from lib.api import api
from utils import fetch_result_with_retry

def target_scale_iaw_page():
    # Introduction Section
    st.title("Target Scale IAW Analysis")
    
    with st.expander("ℹ️ What is Target Scale IAW?"):
        st.markdown("""
        Target Scale IAW (Initial Asset Weight) is a crucial risk management metric that determines the maximum collateral scaling potential based on predefined safety criteria. 
        It helps ensure the stability and safety of positions while optimizing capital efficiency.
        
        **Key Terms:**
        - **Total Deposits Notional**: The total value of deposits in USD
        - **Maintenance Asset Weight**: The weight applied to assets for maintenance margin calculations
        - **Effective Leverage**: The actual leverage being used considering all positions
        """)

    # Fetch data from API endpoints
    largest_perp_positions = fetch_result_with_retry(
        api, "health", "largest_perp_positions"
    )
    most_levered_positions = fetch_result_with_retry(
        api, "health", "most_levered_perp_positions_above_1m"
    )
    largest_spot_borrows = fetch_result_with_retry(
        api, "health", "largest_spot_borrows"
    )
    most_levered_borrows = fetch_result_with_retry(
        api, "health", "most_levered_spot_borrows_above_1m"
    )

    # Convert Leverage columns to numeric
    most_levered_positions = pd.DataFrame(most_levered_positions)
    most_levered_positions["Leverage"] = pd.to_numeric(most_levered_positions["Leverage"], errors="coerce")
    
    most_levered_borrows = pd.DataFrame(most_levered_borrows)
    most_levered_borrows["Leverage"] = pd.to_numeric(most_levered_borrows["Leverage"], errors="coerce")

    # Create tabs for different sections
    tab1, tab2, tab3 = st.tabs(["Position Analysis", "Leverage Analysis", "Risk Insights"])

    with tab1:
        st.header("Position Analysis")
        
        # Perp Positions
        with st.container():
            st.subheader("Largest Perpetual Positions")
            st.markdown("""
            <small>Displays the largest perpetual positions by notional value. Hover over values for more details.</small>
            """, unsafe_allow_html=True)
            
            # Add tooltips for column explanations
            with st.expander("Column Explanations"):
                st.markdown("""
                - **Public Key**: Unique identifier for the position holder
                - **Market Index**: The market identifier for the perpetual contract
                - **Value**: Total USD value of the position
                - **Base Asset Amount**: Quantity of the base asset
                """)
            
            st.dataframe(
                largest_perp_positions,
                hide_index=True,
                column_config={
                    "Value": st.column_config.NumberColumn(
                        "Value",
                        help="Total USD value of the position",
                        format="$%d"
                    )
                }
            )

        # Spot Borrows
        with st.container():
            st.subheader("Largest Spot Borrows")
            st.dataframe(
                largest_spot_borrows,
                hide_index=True,
                column_config={
                    "Value": st.column_config.NumberColumn(
                        "Value",
                        help="Total USD value of the borrow",
                        format="$%d"
                    )
                }
            )

    with tab2:
        st.header("Leverage Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Most Levered Perpetual Positions")
            st.dataframe(
                most_levered_positions,
                hide_index=True,
                column_config={
                    "Leverage": st.column_config.NumberColumn(
                        "Leverage",
                        help="Current leverage ratio",
                        format="%.2fx"
                    )
                }
            )
        
        with col2:
            st.subheader("Most Levered Spot Borrows")
            st.dataframe(
                most_levered_borrows,
                hide_index=True,
                column_config={
                    "Leverage": st.column_config.NumberColumn(
                        "Leverage",
                        help="Current leverage ratio",
                        format="%.2fx"
                    )
                }
            )

        # Scatter plot of leverage vs value
        fig = px.scatter(
            most_levered_positions,
            x="Value",
            y="Leverage",
            title="Leverage vs Position Value (Perpetuals)",
            hover_data=["Public Key"],
            labels={"Value": "Position Value ($)", "Leverage": "Leverage Ratio"}
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.header("Risk Insights")
        
        # Calculate some basic risk metrics
        high_leverage_count = len(most_levered_positions[most_levered_positions["Leverage"] > 3])
        total_positions = len(most_levered_positions)
        
        # Risk metrics display
        metrics_col1, metrics_col2 = st.columns(2)
        with metrics_col1:
            st.metric(
                "High Leverage Positions (>3x)",
                f"{high_leverage_count}",
                f"{(high_leverage_count/total_positions)*100:.1f}% of total"
            )
        
        with metrics_col2:
            st.metric(
                "Average Leverage",
                f"{most_levered_positions['Leverage'].mean():.2f}x"
            )

        # Risk alerts
        st.subheader("Risk Alerts")
        alert_container = st.container()
        with alert_container:
            if high_leverage_count > 0:
                st.warning(f"⚠️ {high_leverage_count} positions have leverage above 3x")
            
            # Add more sophisticated alerts based on your risk criteria
            st.info("ℹ️ Monitor positions with leverage above 2x for potential risk management actions") 