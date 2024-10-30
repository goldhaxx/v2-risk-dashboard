import os

from dotenv import load_dotenv
from lib.page import header
from lib.page import needs_backend
from lib.page import sidebar
from page.asset_liability import asset_liab_matrix_page
from page.asset_liability_cached import asset_liab_matrix_cached_page
from page.backend import backend_page
from page.health import health_page
from page.health_cached import health_cached_page
from page.liquidation_curves import liquidation_curves_page
from page.orderbook import orderbook_page
from page.price_shock import price_shock_page
from page.price_shock_cached import price_shock_cached_page
from sections.welcome import welcome_page
import streamlit as st


load_dotenv()

if __name__ == "__main__":
    st.set_page_config(layout="wide")
    header()
    sidebar()

    pages = [
        st.Page(
            welcome_page,
            url_path="welcome",
            title="Welcome",
            icon=":material/home:",
        ),
        st.Page(
            orderbook_page,
            url_path="orderbook",
            title="Orderbook",
            icon="📈",
        ),
        st.Page(
            needs_backend(health_page),
            url_path="health",
            title="Health",
            icon="🏥",
        ),
        st.Page(
            needs_backend(price_shock_page),
            url_path="price-shock",
            title="Price Shock",
            icon="💸",
        ),
        st.Page(
            needs_backend(asset_liab_matrix_page),
            url_path="asset-liab-matrix",
            title="Asset-Liab Matrix",
            icon="📊",
        ),
        st.Page(
            needs_backend(liquidation_curves_page),
            url_path="liquidation-curves",
            title="Liquidation Curves",
            icon="🌊",
        ),
        st.Page(
            health_cached_page,
            url_path="health-cached",
            title="Health (Cached)",
            icon="🏥",
        ),
        st.Page(
            price_shock_cached_page,
            url_path="price-shock-cached",
            title="Price Shock (Cached)",
            icon="💸",
        ),
        st.Page(
            asset_liab_matrix_cached_page,
            url_path="asset-liab-matrix-cached",
            title="Asset-Liab Matrix (Cached)",
            icon="📊",
        ),
    ]
    if os.getenv("DEV"):
        pages.append(
            st.Page(
                needs_backend(backend_page),
                url_path="backend",
                title="Control Backend",
                icon="🧪",
            )
        )

    pg = st.navigation(pages)
    pg.run()
