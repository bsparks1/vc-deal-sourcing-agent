# Scout's entry point and router (`uv run streamlit run app.py`). Streamlit runs this file on
# every page view: it does the shared setup (page settings, database, daily scheduler), draws
# the sidebar with the always-available "Run agentic analysis" button, then shows the page
# the user picked. The pages themselves live in views/.

import streamlit as st

from scout import config, db
from scout.scheduler import start_scheduler
from ui.run_dialog import run_analysis_dialog

st.set_page_config(page_title="Scout", page_icon="🔭", layout="wide")
db.init_db()  # create tables / add new columns (does nothing if already up to date)
start_scheduler()  # daily automatic runs, if switched on in the Fund Profile

# The pages, in sidebar order. Company is "hidden": it's opened from links, not the menu.
pages = [
    st.Page("views/dashboard.py", title="Dashboard", icon="📊", default=True),
    st.Page("views/explore.py", title="Explore", icon="🃏"),
    st.Page("views/watchlist.py", title="Watchlist", icon="⭐"),
    st.Page("views/fund_profile.py", title="Fund Profile", icon="📝"),
    st.Page("views/company.py", title="Company", icon="📄", visibility="hidden"),
]
current_page = st.navigation(pages)

with st.sidebar:
    st.markdown("### 🔭 Scout")
    st.caption("Your agentic deal-sourcing analyst")
    if st.button("Run agentic analysis", type="primary", icon=":material/rocket_launch:",
                 width="stretch"):
        run_analysis_dialog()  # opens the pop-up over whatever page is showing
    missing = config.missing_keys()
    if missing:
        st.error(f"Missing in .env: {', '.join(missing)}")
    st.caption(f"Traces: [Phoenix]({config.PHOENIX_ENDPOINT})")

current_page.run()  # draw the chosen page
