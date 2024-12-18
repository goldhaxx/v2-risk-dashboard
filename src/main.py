import os

import streamlit as st
from dotenv import load_dotenv

from lib.page import header, needs_backend, sidebar
from page.asset_liability_cached import asset_liab_matrix_cached_page
from page.backend import backend_page
from page.health import health_page
from page.health_cached import health_cached_page
from page.liquidation_curves import liquidation_curves_page
from page.orderbook import orderbook_page
from page.price_shock_cached import price_shock_cached_page
from sections.welcome import welcome_page

load_dotenv()

if __name__ == "__main__":
    path = os.path.join(os.path.dirname(__file__), "style.css")
    with open(path) as css:
        custom_css = css.read()

    def apply_custom_css(css):
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

    st.set_page_config(
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={"About": None, "Get help": None, "Report a bug": None},
    )
    apply_custom_css(custom_css)
    header()
    sidebar()

    main_pages = [
        st.Page(
            welcome_page,
            url_path="welcome",
            title="Welcome",
            icon="🏠",
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
        # st.Page(
        #     needs_backend(price_shock_page),
        #     url_path="price-shock",
        #     title="Price Shock",
        #     icon="💸",
        # ),
        # st.Page(
        #     needs_backend(asset_liab_matrix_page),
        #     url_path="asset-liability-matrix",
        #     title="Asset-Liability Matrix",
        #     icon="📊",
        # ),
        st.Page(
            price_shock_cached_page,
            url_path="price-shock-cached",
            title="Price Shock",
            icon="💸",
        ),
        st.Page(
            asset_liab_matrix_cached_page,
            url_path="asset-liability-matrix-cached",
            title="Asset-Liability Matrix",
            icon="📊",
        ),
        st.Page(
            needs_backend(liquidation_curves_page),
            url_path="liquidation-curves",
            title="Liquidation Curves",
            icon="🌊",
        ),
    ]
    cached_pages = [
        st.Page(
            health_cached_page,
            url_path="health-cached",
            title="Health (Cached)",
            icon="🏥",
        ),
    ]
    if os.getenv("DEV"):
        main_pages.append(
            st.Page(
                needs_backend(backend_page),
                url_path="backend",
                title="Control Backend",
                icon="🧪",
            )
        )

    pg = st.navigation(
        {
            "Main": main_pages,
            # "Cached": cached_pages,
        }
    )
    pg.run()
