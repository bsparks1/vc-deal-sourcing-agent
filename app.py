# Scout's Streamlit web app (the entry point: `uv run streamlit run app.py`).
# This is the home page: what Scout is, whether the API keys are set, and where to start.
# Other pages live in pages/: Fund Profile, Source, Inbox, Watchlist, and Company.

import streamlit as st

from scout import config
from scout.page_setup import setup_page

# Page title, database tables, and the daily scheduler (see scout/page_setup.py).
setup_page("Scout")

st.title("Scout")
st.write("An AI agent that researches the web to find early-stage companies that fit your fund's thesis.")

st.subheader("Setup check")

# Show ✅ / ❌ per key. We only check whether a key is set; we never display its value.
for name, value in config.REQUIRED_KEYS.items():
    icon = "✅" if value else "❌"
    st.write(f"{icon} `{name}`")

missing = config.missing_keys()
if missing:
    # Name the missing keys so the fix is obvious, without revealing any key values.
    st.error(f"Missing: {', '.join(missing)}. Add them to `.env` (see `.env.example`) and restart the app.")
else:
    st.success("All API keys are set.")

st.caption(f"Model: `{config.MODEL}` · Traces: {config.PHOENIX_ENDPOINT}")

st.subheader("How to use Scout")
st.page_link("pages/1_Fund_Profile.py", label="1. Set up your Fund Profile", icon="📝")
st.page_link("pages/2_Source.py", label="2. Send the agent to find companies", icon="🔎")
st.page_link("pages/3_Inbox.py", label="3. Review what it found", icon="📥")
st.page_link("pages/4_Watchlist.py", label="4. Track your watchlist", icon="⭐")
