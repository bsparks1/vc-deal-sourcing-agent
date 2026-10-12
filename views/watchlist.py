# The Watchlist: a dashboard of every company the fund swiped right on.
# The headline numbers are clickable filters (e.g. "Reached out" shows only those companies),
# each company's deal status can be changed in place, and companies can be checked for changes.

import streamlit as st

from scout import companies
from scout.changes import change_status, check_company
from ui.details import facts_line
from ui.theme import page_header
from ui.widgets import change_badge

page_header("Pipeline", "Watchlist", "Every company you swiped right on, and where each one stands.")

watchlist = companies.list_companies("watching")
for company in watchlist:  # rows saved before deal statuses existed count as "watching"
    company["deal_status"] = company.get("deal_status") or "watching"
alerts = {c["id"] for c in watchlist
          if (s := change_status(c["id"]))["exclusion"] or s["significant"]}
stats = companies.pipeline_stats()

# The filter comes from the URL (?filter=reached_out), so the dashboard can link straight here.
# Short labels so six cards fit side by side (the dropdowns use the longer DEAL_STATUSES names).
FILTERS = {"all": "All", "watching": "Watching", "reached_out": "Reached out",
           "in_conversation": "In talks", "alerts": "Alerts"}
current = st.query_params.get("filter", "all")
if current not in FILTERS:
    current = "all"


def count_for(key: str) -> int:
    """How many watchlist companies a filter would show."""
    if key == "all":
        return len(watchlist)
    if key == "alerts":
        return len(alerts)
    return sum(c["deal_status"] == key for c in watchlist)


# --- Clickable headline numbers: each one filters the list below ---
cols = st.columns(len(FILTERS) + 1)
for col, (key, label) in zip(cols, FILTERS.items()):
    with col.container(border=True):
        st.metric(label, count_for(key))
        # The selected filter's button is highlighted ("primary").
        if st.button("Showing" if key == current else "Show", key=f"f_{key}", width="stretch",
                     type="primary" if key == current else "secondary"):
            st.query_params["filter"] = key
            st.rerun()
with cols[-1].container(border=True):
    st.metric("To review", stats["new"])
    if st.button("Review", key="f_review", width="stretch", disabled=not stats["new"]):
        st.switch_page("views/explore.py")  # opens the swipe review for those companies

shown = [c for c in watchlist if current == "all"
         or (current == "alerts" and c["id"] in alerts) or c["deal_status"] == current]

left, right = st.columns([3, 1])
left.subheader(f"{FILTERS[current]} ({len(shown)})")
if right.button(f"Check {len(shown)} for changes", icon=":material/refresh:", disabled=not shown,
                width="stretch"):
    with st.status("Checking for news since each company was saved...", expanded=True) as status:
        for company in shown:
            status.write(f"Checking {company['name']}...")
            try:
                status.write(f"  {check_company(company)['summary']}")
            except Exception as error:  # keep going: one failure shouldn't stop the rest
                status.write(f"  Check failed: {error}")
        status.update(label="Done", state="complete")
    st.rerun()

if not shown:
    st.info("No companies here yet. Swipe right on companies in Explore to add them.")


def on_status_change(company_id: int) -> None:
    """Save a new deal status as soon as it's picked in the dropdown."""
    choice = st.session_state[f"deal_{company_id}"]
    if choice == "passed":
        companies.set_company_status(company_id, "passed")
    else:
        companies.set_deal_status(company_id, choice)


STATUS_OPTIONS = {**companies.DEAL_STATUSES, "passed": "Pass (remove)"}
for company in shown:
    with st.container(border=True):
        info, status_col, score_col = st.columns([5, 2, 1])
        info.page_link("views/company.py", label=f"**{company['name']}**",
                       query_params={"id": company["id"]})
        info.write(company["one_liner"] or "")
        info.caption(facts_line(company))
        with info:
            change_badge(company)
        status_col.selectbox("Status", list(STATUS_OPTIONS), format_func=STATUS_OPTIONS.get,
                             index=list(STATUS_OPTIONS).index(company["deal_status"]),
                             key=f"deal_{company['id']}", on_change=on_status_change,
                             args=(company["id"],))
        score_col.metric("Score", company["score_total"])

# Passed companies stay reachable in case the fund changes its mind.
passed = companies.list_companies("passed")
if passed:
    with st.expander(f"Passed companies ({len(passed)})"):
        for company in passed:
            name_col, button_col = st.columns([4, 1])
            name_col.page_link("views/company.py", label=f"{company['name']} ({company['score_total']})",
                               query_params={"id": company["id"]})
            if button_col.button("Review again", key=f"undo_{company['id']}"):
                companies.set_company_status(company["id"], "new")  # back into Explore
                st.rerun()
