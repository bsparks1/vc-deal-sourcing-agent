# The Source page: ask the agent to find N new companies and watch it work, step by step.
# It calls run_agent() from scout/agent.py and shows each step as it happens.
# Companies the agent saves land in the Inbox page for review.

import streamlit as st

from scout import companies, config, db, feedback
from scout.agent import run_agent
from scout.page_setup import setup_page
from scout.scheduler import next_run_description

setup_page("Source")  # title, database tables, daily scheduler

st.title("Source")
st.write("Send the agent out to find new companies that fit your fund profile.")

# The agent can't run without both keys; say so up front instead of failing mid-run.
missing = config.missing_keys()
if missing:
    st.error(f"Missing: {', '.join(missing)}. Add them to `.env` and restart the app.")
    st.stop()  # stop drawing the rest of the page

profile = db.get_fund_profile()
if profile is None:
    st.warning("No fund profile saved yet, so the agent will use the Brand Project template.")
    st.page_link("pages/1_Fund_Profile.py", label="Set up your Fund Profile", icon="📝")

# Show what the agent has learned from past reviews, so its behavior is never a mystery.
learned = feedback.get_learned_preferences()
with st.expander("What Scout has learned from your reviews"):
    if learned:
        st.write(learned["summary"])
        st.caption(f"Based on {learned['feedback_count']} reviews · updated {learned['created_at']} (UTC)")
    else:
        st.write("Nothing yet. Give 👍 / 👎 on companies in the Inbox and Scout will adapt.")

with st.form("source"):
    target = st.number_input(
        "How many companies?", min_value=1, max_value=10,
        value=min(int((profile or {}).get("daily_target") or 3), 10),
    )
    focus = st.text_input("Focus (optional)", placeholder="e.g. functional beverages")
    st.caption("Each company takes roughly 30-60 seconds of research. Keep this page open while it runs.")
    submitted = st.form_submit_button("Find companies", type="primary")

if submitted:
    # st.status is a collapsible box with a spinner; we write each agent step into it.
    with st.status(f"Finding {int(target)} companies...", expanded=True) as status:
        result = run_agent(target=int(target), focus=focus.strip(), on_step=status.write)
        status.update(
            label=f"Run {result['run_id']}: {result['status']}, {result['companies_saved']} saved",
            state="complete" if result["status"] == "completed" else "error",
            expanded=False,  # collapse the step log once done; the summary below is what matters
        )

    if result["error"]:
        st.error(result["error"])
    if result["summary"]:
        st.markdown(result["summary"])
    if result["companies_saved"]:
        st.page_link("pages/3_Inbox.py", label="Review them in the Inbox", icon="📥")

    if result["tracing_on"]:
        st.caption(f"Full trace: {config.PHOENIX_ENDPOINT} (project '{config.PHOENIX_PROJECT}')")
    else:
        st.caption("Phoenix wasn't running, so this run wasn't traced. Start it with `uv run phoenix serve`.")

# --- Daily cadence and run history ---
st.divider()
st.subheader("Daily cadence")
st.write(next_run_description(db.get_fund_profile()))
runs = companies.list_runs(limit=10)
if runs:
    st.caption("Recent runs (newest first). Scheduled runs print their steps in the terminal running the app.")
    st.dataframe(
        [{"Run": r["id"], "Trigger": r["trigger"] or "manual", "Started (UTC)": r["started_at"][:16],
          "Status": r["status"], "Saved": r["companies_saved"], "Request": r["request"]}
         for r in runs],
        hide_index=True,
    )

