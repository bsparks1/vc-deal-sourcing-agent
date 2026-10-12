# Scout's entry point and router (`uv run streamlit run app.py`). Streamlit runs this file on
# every page view: it does the shared setup (page settings, database, daily scheduler), draws
# the sidebar with the always-available "Run agentic analysis" button, then shows the page
# the user picked. The pages themselves live in views/.

from pathlib import Path

import streamlit as st

from scout import config, db
from scout.scheduler import start_scheduler
from ui.run_dialog import run_analysis_dialog
from ui.theme import apply_theme

STATIC = Path(__file__).parent / "static"  # the logo files, found wherever the app is started

st.set_page_config(page_title="Scout", page_icon=str(STATIC / "mark.svg"), layout="wide")
apply_theme()  # the design system's extra styles (titles, numbers, list markers)
st.logo(str(STATIC / "logo.svg"), icon_image=str(STATIC / "mark.svg"), size="large")
db.init_db()  # create tables / add new columns (does nothing if already up to date)
start_scheduler()  # daily automatic runs, if switched on in the Fund Profile

# The pages, in sidebar order. Company is "hidden": it's opened from links, not the menu.
pages = [
    # Material icons: simple line icons that match the design (no emoji).
    st.Page("views/dashboard.py", title="Dashboard", icon=":material/space_dashboard:", default=True),
    st.Page("views/explore.py", title="Explore", icon=":material/swipe:"),
    st.Page("views/watchlist.py", title="Watchlist", icon=":material/bookmark:"),
    st.Page("views/fund_profile.py", title="Fund Profile", icon=":material/tune:"),
    st.Page("views/company.py", title="Company", icon=":material/business:", visibility="hidden"),
]
current_page = st.navigation(pages)

with st.sidebar:
    st.caption("Agentic deal-sourcing analyst")
    if st.button("Run agentic analysis", type="primary", icon=":material/rocket_launch:",
                 width="stretch"):
        run_analysis_dialog()  # opens the pop-up over whatever page is showing
    missing = config.missing_keys()
    if missing:
        st.error(f"Missing in .env: {', '.join(missing)}")
    st.caption(f"Traces: [Phoenix]({config.PHOENIX_ENDPOINT})")

current_page.run()  # draw the chosen page
