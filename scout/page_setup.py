# Shared setup that every Streamlit page runs first: page title, database tables, scheduler.
# Streamlit runs each page file on its own (opening the Inbox directly never runs app.py),
# so anything every page needs has to be called from every page; this keeps it to one line.

import streamlit as st

from scout import db
from scout.scheduler import start_scheduler


def setup_page(title: str) -> None:
    """Set the browser tab title, make sure the tables exist, and start the daily scheduler."""
    # Must be the first Streamlit call on the page.
    st.set_page_config(page_title=f"{title} · Scout" if title != "Scout" else "Scout")
    db.init_db()  # create tables / add new columns (does nothing if already up to date)
    start_scheduler()  # does nothing if it's already running
