# The Fund Profile page: a form where the fund describes what it invests in.
# The agent reads this profile to know what a "good" company looks like, and the daily
# cadence settings here control the automatic scheduled runs (scout/scheduler.py).
# Streamlit shows every file in pages/ as a sidebar link; the "1_" prefix sets its order.

import streamlit as st

from scout import db
from scout.defaults import DEFAULT_FUND_PROFILE
from scout.page_setup import setup_page

setup_page("Fund Profile")  # title, database tables, daily scheduler

st.title("Fund Profile")
st.write("Tell Scout what your fund invests in. The agent uses this to judge every company it finds.")

saved = db.get_fund_profile()
if saved:
    st.caption(f"Last saved: {saved['updated_at']} (UTC)")
else:
    st.info("Nothing saved yet. The form below is pre-filled with the Brand Project template; edit it and click Save.")

# Fill the form from the saved profile, or from the template if nothing is saved yet.
profile = saved or DEFAULT_FUND_PROFILE

# st.form groups the inputs so the page only reruns when Save is clicked,
# not on every keystroke.
with st.form("fund_profile"):
    fund_name = st.text_input("Fund name", value=profile["fund_name"])
    thesis = st.text_area("Investment thesis", value=profile["thesis"], height=120)
    categories = st.text_area("Target categories (one per line)", value=profile["categories"])
    stages = st.text_area("Stages (one per line)", value=profile["stages"], height=80)
    check_size = st.text_input(
        "Check size", value=profile["check_size"] or "", placeholder="e.g. $100k-$500k"
    )
    include_signals = st.text_area(
        "Signals to look for (one per line)", value=profile["include_signals"], height=140
    )
    exclude_signals = st.text_area(
        "Signals that rule a company out (one per line)", value=profile["exclude_signals"], height=140
    )
    daily_target = st.number_input(
        "New companies per day", min_value=1, max_value=50, value=int(profile["daily_target"] or 3)
    )

    st.markdown("**Daily cadence**")
    # .get(...) because profiles saved before Step 12 don't have these keys yet.
    schedule_enabled = st.checkbox(
        "Find new companies automatically every day (while the app is running)",
        value=bool(profile.get("schedule_enabled")),
    )
    schedule_hour = st.number_input(
        "Start the daily run after this hour (0-23, your computer's time)",
        min_value=0, max_value=23, value=int(profile.get("schedule_hour") or 9),
    )
    st.caption("Each scheduled run uses API credits (roughly 30-60 seconds of agent work per "
               "company) and is capped at 10 companies, since nobody is watching it.")
    submitted = st.form_submit_button("Save")

if submitted:
    # Fund name and thesis are the minimum the agent needs; everything else is optional.
    if not fund_name.strip() or not thesis.strip():
        st.error("Fund name and investment thesis are required.")
    else:
        db.save_fund_profile({
            "fund_name": fund_name.strip(),
            "thesis": thesis.strip(),
            "categories": categories.strip(),
            "stages": stages.strip(),
            "check_size": check_size.strip(),
            "include_signals": include_signals.strip(),
            "exclude_signals": exclude_signals.strip(),
            "daily_target": int(daily_target),
            "schedule_enabled": int(schedule_enabled),  # SQLite has no True/False; 1 or 0
            "schedule_hour": int(schedule_hour),
        })
        st.success("Fund profile saved.")
