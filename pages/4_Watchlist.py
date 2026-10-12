# The Watchlist page: a dashboard of the companies the fund chose to follow.
# Shows headline numbers for the whole pipeline, a button to check every watched company for
# changes (Step 13), then one card per company (best score first) linking to its Company page.

import streamlit as st

from scout import companies
from scout.changes import change_status, check_company
from scout.page_setup import setup_page

setup_page("Watchlist")  # title, database tables, daily scheduler

st.title("Watchlist")

# Headline numbers across the whole pipeline: inbox -> watchlist / passed.
counts = companies.count_by_status()
watching = companies.list_companies("watching")
average = round(sum(c["score_total"] for c in watching) / len(watching)) if watching else None

col1, col2, col3, col4 = st.columns(4)
col1.metric("Watching", counts["watching"])
col2.metric("Avg. score", f"{average}/100" if average is not None else "–")
col3.metric("To review", counts["new"])
col4.metric("Passed", counts["passed"])

if counts["new"]:
    st.page_link("pages/3_Inbox.py", label=f"Review {counts['new']} new in the Inbox", icon="📥")

st.divider()

if not watching:
    st.info("No companies on the watchlist yet. Save good leads from the Inbox with ⭐.")
    st.stop()

# Re-research every watched company and record what changed (one at a time, ~10-20s each).
if st.button(f"🔄 Check all {len(watching)} for changes"):
    with st.status("Checking watchlist companies for changes...", expanded=True) as status:
        for company in watching:
            status.write(f"Checking {company['name']}...")
            try:
                check = check_company(company)
                status.write(f"  {check['summary']}")
            except Exception as error:  # keep going: one failure shouldn't stop the rest
                status.write(f"  Check failed: {error}")
        status.update(label="Watchlist checked", state="complete")

for company in watching:
    with st.container(border=True):
        left, right = st.columns([4, 1])
        # query_params puts "?id=3" in the URL, so the Company page knows which one to show
        # (and the link still works after a refresh, or if you bookmark it).
        left.page_link("pages/5_Company.py", label=f"**{company['name']}**",
                       query_params={"id": company["id"]})
        left.write(company["one_liner"] or "")
        # updated_at[:10] keeps just the date part ("2026-10-12") of the timestamp.
        since = f"watching since {company['updated_at'][:10]}" if company["updated_at"] else None
        facts = [company["category"], company["stage"], company["location"], since]
        left.caption(" · ".join(fact for fact in facts if fact))
        right.metric("Score", f"{company['score_total']}/100")

        # Change-tracking badge: what's different since the company was saved.
        changes = change_status(company["id"])
        if changes["exclusion"]:
            left.error("⚠️ Now shows one of your exclusion signals. Open it to see why.")
        elif changes["significant"]:
            left.warning(f"🔔 {changes['significant']} significant change(s) since you saved it")
        elif changes["checked"]:
            left.caption(f"✓ No significant changes (checked {changes['last_checked'][:10]})")

# Passed companies stay available (collapsed) in case the fund changes its mind.
passed = companies.list_companies("passed")
if passed:
    with st.expander(f"Passed companies ({len(passed)})"):
        for company in passed:
            st.page_link("pages/5_Company.py", label=f"{company['name']} ({company['score_total']}/100)",
                         query_params={"id": company["id"]})
