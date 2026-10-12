# The Company page: the full profile of one company, opened from Explore, the Watchlist, or
# the Dashboard. Which company comes from the URL (e.g. ?id=3), so links survive a refresh.
# Shows everything Scout knows, what changed since it was saved, and the fund's past swipes,
# with buttons to re-research founders, check for changes, and change its status.

import streamlit as st

from scout import companies
from scout.changes import check_company
from scout.founders import research_founders
from ui.details import (render_changes, render_founders, render_overview, render_reviews,
                        render_score, render_sources, render_traction)

# Read ?id=... from the URL. Query params are always text, so convert to a number safely.
company_id = st.query_params.get("id", "")
company = companies.get_company(int(company_id)) if company_id.isdigit() else None
if company is None:
    st.title("Company")
    st.info("Open a company from Explore or the Watchlist to see its profile here.")
    st.page_link("views/watchlist.py", label="Go to Watchlist", icon="⭐")
    st.stop()

# --- Header: name, one-liner, score, and where it is in the pipeline ---
left, right = st.columns([4, 1])
left.title(company["name"])
left.write(company["one_liner"] or "")
if company["website"]:
    left.markdown(f"[{company['domain']}]({company['website']})")
right.metric("Score", f"{company['score_total']}/100")

if company["status"] == "watching":
    options = {**companies.DEAL_STATUSES, "passed": "✖ Pass (remove)"}
    choice = right.selectbox("Status", list(options), format_func=options.get,
                             index=list(options).index(company.get("deal_status") or "watching"))
    if choice != (company.get("deal_status") or "watching"):
        if choice == "passed":
            companies.set_company_status(company["id"], "passed")
        else:
            companies.set_deal_status(company["id"], choice)
        st.rerun()
elif company["status"] == "new":
    right.caption("🃏 Waiting for review in Explore")
else:
    right.caption("Passed")
    if right.button("Review again"):
        companies.set_company_status(company["id"], "new")
        st.rerun()

# --- Everything Scout knows, in tabs ---
tabs = st.tabs(["Overview", "Founders", "Score", "What changed", "Sources", "Your reviews"])
with tabs[0]:
    render_overview(company)
    st.markdown("**Traction**")
    render_traction(company)
with tabs[1]:
    render_founders(company)
    if st.button("🔍 Research founders" + (" again" if company["founders"] else "")):
        with st.spinner("Searching the web for the founding team..."):
            try:
                result = research_founders(company["name"], company["domain"])
            except Exception as error:
                st.error(f"Founder research failed: {error}")
            else:
                if result["founders"]:
                    companies.update_founders(company["id"], result["founders"])
                    st.rerun()
                else:  # keep what we had rather than replacing it with nothing
                    st.warning(f"No founders found. {result['notes']}")
with tabs[2]:
    render_score(company)
with tabs[3]:
    render_changes(company)
    if st.button("🔄 Check for changes"):
        with st.spinner("Searching for news since the last check..."):
            try:
                check_company(company)
                st.rerun()
            except Exception as error:
                st.error(f"Change check failed: {error}")
with tabs[4]:
    render_sources(company)
with tabs[5]:
    render_reviews(company)

if company["run_id"] and company["created_at"]:
    st.caption(f"Found by agent run {company['run_id']} on {company['created_at'][:10]}.")
