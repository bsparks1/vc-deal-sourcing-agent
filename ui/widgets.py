# Small reusable pieces: clickable metric cards (the dashboard and watchlist "hero" numbers),
# the change-tracking badge shown on watchlist companies, and the learned-preferences summary.

import streamlit as st

from scout import feedback
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
        st.error("Now shows one of your exclusion signals. Open it to see why.")
    elif changes["significant"]:
        st.warning(f"{changes['significant']} significant change(s) since you saved it")
    elif changes["checked"]:
        st.caption(f"No significant changes · checked `{changes['last_checked'][:10]}`")


def split_summary(summary: str) -> tuple[str, str]:
    """Split a learned-preferences summary into (headline, full explanation).

    New summaries start with a one-sentence headline and a blank line. Older ones don't, so
    for those the first sentence becomes the headline.
    """
    if "\n\n" in summary:
        headline, _, rest = summary.partition("\n\n")
        return headline.strip(), rest.strip()
    first, dot, rest = summary.partition(". ")
    return (first + dot).strip(), rest.strip() or summary


def learned_preferences(caption: str = "") -> None:
    """What Scout has learned from the fund's swipes: the headline, with the full
    explanation in a dropdown so it doesn't take over the page."""
    learned = feedback.get_learned_preferences()
    if not learned:
        st.write("Nothing yet. Swipe on companies in Explore and Scout will adapt.")
        return
    headline, detail = split_summary(learned["summary"])
    st.markdown(f"**{headline}**")
    with st.expander("Full explanation"):
        st.write(detail)
    st.caption(f"From `{learned['feedback_count']}` swipes{caption}")

