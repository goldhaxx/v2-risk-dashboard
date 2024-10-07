from dotenv import load_dotenv
from lib.page import header
from lib.page import needs_backend
from lib.page import sidebar
from page.asset_liability import asset_liab_matrix_page
from page.backend import backend_page
from page.health import health_page
from page.orderbook import orderbook_page
from page.price_shock import price_shock_page
from sections.liquidation_curves import plot_liquidation_curve
from sections.welcome import welcome_page
import streamlit as st


load_dotenv()

if __name__ == "__main__":
    st.set_page_config(layout="wide")
    header()
    sidebar()

    pg = st.navigation(
        [
            st.Page(
                welcome_page,
                url_path="welcome",
                title="Welcome",
                icon=":material/home:",
            ),
            st.Page(
                needs_backend(orderbook_page),
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
                needs_backend(plot_liquidation_curve),
                url_path="liquidation-curves",
                title="Liquidation Curves",
                icon="🌊",
            ),
            st.Page(
                needs_backend(backend_page),
                url_path="backend",
                title="Control Backend",
                icon="🧪",
            ),
        ]
    )
    pg.run()
