# The Company page: the deep profile of one company, opened from the Watchlist or Inbox.
# Which company to show comes from the URL (e.g. /Company?id=3). Shows what it makes, stage
# and funding, traction, the founding team with sources, what changed since it was saved,
# the score breakdown, all sources, past reviews, and buttons to re-research or change status.

import streamlit as st

from scout import companies, feedback
from scout.changes import check_company, list_checks
from scout.founders import research_founders
from scout.page_setup import setup_page
from scout.scoring import RUBRIC_MAX

setup_page("Company")  # title, database tables, daily scheduler

# Read ?id=... from the URL. Query params are always text, so convert to a number safely.
company_id = st.query_params.get("id", "")
company = companies.get_company(int(company_id)) if company_id.isdigit() else None

if company is None:
    st.title("Company")
    st.info("Open a company from the Watchlist to see its profile here.")
    st.page_link("pages/4_Watchlist.py", label="Go to Watchlist", icon="⭐")
    st.stop()

STATUS_LABELS = {"new": "📥 In inbox", "watching": "⭐ Watching", "passed": "Passed"}

# --- Header: name, one-liner, score, status ---
left, right = st.columns([4, 1])
left.title(company["name"])
left.write(company["one_liner"] or "")
if company["website"]:
    left.markdown(f"[{company['domain']}]({company['website']})")
right.metric("Score", f"{company['score_total']}/100")
right.caption(STATUS_LABELS.get(company["status"], company["status"]))

# --- Overview (blank facts show as "Unknown", never guessed) ---
st.subheader("Overview")
facts = {
    "Category": company["category"], "Stage": company["stage"],
    "Location": company["location"], "Founded": company["founded_year"],
    "Funding": company["funding_summary"],
}
for label, value in facts.items():
    st.write(f"**{label}:** {value if value else 'Unknown'}")

# --- Traction signals (saved by the agent from Step 9 on) ---
st.subheader("Traction")
for signal in company["traction"] or ["No traction signals recorded."]:
    st.write(f"- {signal}")

# --- Founding team, each founder with the sources that back them up ---
st.subheader("Founding team")
founders = company["founders"] or []
if not founders:
    st.write("No founders found yet.")
for founder in founders:
    if isinstance(founder, str):  # saved before Step 9: a plain line of text, no sources
        st.write(f"- {founder}")
        continue
    with st.container(border=True):
        st.markdown(f"**{founder['name']}**" + (f" · {founder['role']}" if founder["role"] else ""))
        st.write(founder["background"] or "Background unknown.")
        st.caption("Sources: " + ", ".join(f"[{i + 1}]({url})" for i, url in
                                           enumerate(founder["source_urls"])))

# Re-run founder research on demand, e.g. for companies saved before Step 9.
if st.button("🔍 Research founders" if not founders else "🔍 Research founders again"):
    with st.spinner("Searching the web for the founding team..."):
        try:
            result = research_founders(company["name"], company["domain"])
        except Exception as error:
            st.error(f"Founder research failed: {error}")
        else:
            if result["founders"]:
                companies.update_founders(company["id"], result["founders"])
                st.rerun()  # reload to show the new founders
            else:
                # Keep what we had rather than replacing it with nothing.
                st.warning(f"No founders found. {result['notes']}")

# --- What changed since it was saved (Step 13) ---
st.subheader("What changed since you saved it")
checks = list_checks(company["id"])
if not checks:
    st.write("Not checked yet.")
for check in reversed(checks):  # newest first
    st.markdown(f"**{check['checked_at'][:10]}**: {check['summary']}")
    if check["exclusion_now_applies"]:
        st.error(f"⚠️ {check['exclusion_reason']}")
    for change in check["changes"]:
        mark = "🔔 " if change["significant"] else ""
        links = ", ".join(f"[{i + 1}]({url})" for i, url in enumerate(change["source_urls"]))
        st.write(f"- {mark}**{change['field']}**: {change['before']} → {change['after']} ({links})")

if st.button("🔄 Check for changes"):
    with st.spinner("Searching for news since the last check..."):
        try:
            check_company(company)
            st.rerun()  # reload to show the new check
        except Exception as error:
            st.error(f"Change check failed: {error}")

# --- Score breakdown: one progress bar per rubric dimension ---
st.subheader("Score breakdown")
breakdown = company["score_breakdown"] or {}
for dimension, maximum in RUBRIC_MAX.items():
    points = breakdown.get(dimension, 0)
    # st.progress needs a number from 0.0 to 1.0, so divide by the dimension's maximum.
    st.progress(points / maximum, text=f"{dimension.replace('_', ' ')}: {points}/{maximum}")
st.write(company["rationale"] or "")

# --- Sources: every fact should trace back to one of these ---
st.subheader("Sources")
for url in company["sources"] or []:
    st.write(f"- {url}")

# --- Review history ---
reviews = feedback.list_feedback_for_company(company["id"])
if reviews:
    st.subheader("Your reviews")
    for review in reviews:
        thumb = "👍" if review["verdict"] == "up" else "👎"
        st.write(f"{thumb} {review['reason'] or '(no reason given)'} · {review['created_at'][:10]}")

# --- Change status ---
st.divider()
if company["run_id"] and company["created_at"]:
    st.caption(f"Found by run {company['run_id']} on {company['created_at'][:10]}.")
if company["status"] == "watching":
    if st.button("Remove from watchlist (pass)"):
        companies.set_company_status(company["id"], "passed")
        st.rerun()  # reload so the new status shows
elif st.button("⭐ Add to watchlist"):
    companies.set_company_status(company["id"], "watching")
    st.rerun()
