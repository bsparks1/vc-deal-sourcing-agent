# The Dashboard: the home page a fund lands on, an executive summary of the whole pipeline.
# Top: clickable headline numbers (matches to review, watching, reached out, alerts).
# Below: the best new matches, watchlist alerts, what Scout has learned, and recent agent runs.

import streamlit as st

from scout import companies, db, feedback, runs
from scout.changes import change_status
from scout.scheduler import next_run_description
from ui.details import facts_line
from ui.widgets import metric_card

profile = db.get_fund_profile()
st.title(f"{profile['fund_name']} · Dashboard" if profile else "Dashboard")
if profile is None:
    st.info("Start by describing what your fund invests in.")
    st.page_link("views/fund_profile.py", label="Set up your Fund Profile", icon="📝")

stats = companies.pipeline_stats()
watchlist = companies.list_companies("watching")
# A watchlist company needs attention if a change check found something significant.
alerts = [c for c in watchlist if (s := change_status(c["id"]))["exclusion"] or s["significant"]]

# --- Headline numbers: each card jumps to the matching list ---
cols = st.columns(4)
with cols[0]:
    metric_card("Matches to review", stats["new"], "views/explore.py", "Review", "m_review",
                help="Companies the agent found that you haven't swiped on yet")
with cols[1]:
    metric_card("Watching", stats["deal"]["watching"], "views/watchlist.py", "Open", "m_watch",
                query={"filter": "watching"})
with cols[2]:
    metric_card("Reached out", stats["deal"]["reached_out"], "views/watchlist.py", "Open",
                "m_reached", query={"filter": "reached_out"})
with cols[3]:
    metric_card("Watchlist alerts", len(alerts), "views/watchlist.py", "Open", "m_alerts",
                query={"filter": "alerts"}, help="Significant changes since you saved them")

cols = st.columns(4)
cols[0].metric("Found in last 7 days", stats["found_7d"])
cols[1].metric("Avg. match score", f"{stats['avg_new_score']}/100" if stats["avg_new_score"] else "–",
               help="Average score of companies waiting for review")
cols[2].metric("In conversation", stats["deal"]["in_conversation"])
cols[3].metric("Passed", stats["passed"])

st.divider()
left, right = st.columns([3, 2])

# --- Best new matches ---
with left:
    st.subheader("Top new matches")
    new = companies.list_companies("new")[:3]  # already sorted best score first
    if not new:
        st.write("Nothing waiting. Use **Run agentic analysis** in the sidebar to find more.")
    for company in new:
        with st.container(border=True):
            name_col, score_col = st.columns([4, 1])
            name_col.markdown(f"**{company['name']}**  \n{company['one_liner'] or ''}")
            name_col.caption(facts_line(company))
            score_col.metric("Score", company["score_total"])
    if new:
        st.page_link("views/explore.py", label="Review all matches", icon="🃏")

# --- Alerts, learning, cadence, runs ---
with right:
    st.subheader("Watchlist alerts")
    if not alerts:
        st.write("No significant changes on your watchlist.")
    for company in alerts:
        st.page_link("views/company.py", label=company["name"], icon="🔔",
                     query_params={"id": company["id"]})

    st.subheader("What Scout has learned")
    learned = feedback.get_learned_preferences()
    if learned:
        st.write(learned["summary"])
        st.caption(f"From {learned['feedback_count']} of your swipes")
    else:
        st.write("Nothing yet. Swipe on companies in Explore and Scout will adapt.")

    st.subheader("Agent activity")
    st.caption(f"Daily cadence: {next_run_description(profile)}")
    recent = runs.list_runs(limit=5)
    if recent:
        st.dataframe(
            [{"Run": r["id"], "When (UTC)": r["started_at"][:16].replace("T", " "),
              "Trigger": r["trigger"] or "manual", "Status": r["status"],
              "Saved": r["companies_saved"]} for r in recent],
            hide_index=True,
        )
    else:
        st.write("No runs yet.")
