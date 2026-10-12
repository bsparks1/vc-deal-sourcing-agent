# Small reusable pieces: clickable metric cards (the dashboard and watchlist "hero" numbers)
# and the change-tracking badge shown on watchlist companies.

import streamlit as st

from scout.changes import change_status


def metric_card(label: str, value, page: str, button: str, key: str,
                query: dict | None = None, help: str | None = None) -> None:
    """A metric in a bordered card, with a button that jumps to the matching page/filter.

    query becomes URL parameters on the target page (e.g. {"filter": "reached_out"}), so
    the Watchlist opens already filtered, and the link still works after a refresh.
    """
    with st.container(border=True):
        st.metric(label, value, help=help)
        if st.button(button, key=key, type="tertiary", icon=":material/arrow_forward:"):
            st.switch_page(page, query_params=query)


def change_badge(company: dict) -> None:
    """Show what's changed since the company was saved: exclusion warning, alerts, or all clear."""
    changes = change_status(company["id"])
    if changes["exclusion"]:
        st.error("⚠️ Now shows one of your exclusion signals. Open it to see why.")
    elif changes["significant"]:
        st.warning(f"🔔 {changes['significant']} significant change(s) since you saved it")
    elif changes["checked"]:
        st.caption(f"✓ No significant changes (checked {changes['last_checked'][:10]})")
