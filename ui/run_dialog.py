# The "Run agentic analysis" pop-up, opened from the sidebar button on every page.
# It asks how many companies to find and an optional focus, runs the agent while showing each
# step live, and then offers to jump to Explore to review what it found.

import streamlit as st

from scout import config, db
from scout.agent import run_agent


@st.dialog("Run agentic analysis", width="large")
def run_analysis_dialog() -> None:
    """The dialog's contents. Streamlit shows this as a pop-up over the current page."""
    missing = config.missing_keys()
    if missing:
        st.error(f"Missing: {', '.join(missing)}. Add them to `.env` and restart the app.")
        return

    # After a run finishes, show its result instead of the form (kept in session_state so it
    # survives the rerun that happens when a button inside the dialog is clicked).
    result = st.session_state.get("last_run_result")
    if result:
        show_result(result)
        return

    profile = db.get_fund_profile() or {}
    st.write("Scout will search the web for new companies that fit your Fund Profile, research "
             "each one, score it, and add the good ones to **Explore** for you to review.")
    with st.form("run_analysis"):
        target = st.number_input("How many companies?", min_value=1, max_value=10,
                                 value=min(int(profile.get("daily_target") or 3), 10))
        focus = st.text_input("Focus (optional)", placeholder="e.g. functional beverages")
        st.caption("Takes roughly 30-60 seconds per company. Keep this window open while it runs.")
        start = st.form_submit_button("Run analysis", type="primary", icon=":material/rocket_launch:")

    if start:
        with st.status(f"Finding {int(target)} companies...", expanded=True) as status:
            result = run_agent(target=int(target), focus=focus.strip(), on_step=status.write)
            status.update(label=f"Done: {result['companies_saved']} saved",
                          state="complete" if result["status"] == "completed" else "error",
                          expanded=False)
        st.session_state["last_run_result"] = result
        show_result(result)


def show_result(result: dict) -> None:
    """The run's outcome, the agent's summary, and where to go next."""
    if result["error"]:
        st.error(result["error"])
    saved = result["companies_saved"]
    st.success(f"Run {result['run_id']} {result['status']}: "
               f"{saved} new {'company' if saved == 1 else 'companies'} found.")
    with st.expander("The agent's summary"):
        st.markdown(result["summary"] or "(no summary)")
    if not result["tracing_on"]:
        st.caption("Phoenix wasn't running, so this run wasn't traced.")

    left, right = st.columns(2)
    if left.button("Review them in Explore", type="primary", disabled=not result["companies_saved"]):
        del st.session_state["last_run_result"]
        st.switch_page("views/explore.py")
    if right.button("Start another run"):
        del st.session_state["last_run_result"]
        st.rerun(scope="fragment")  # redraw just the dialog (keeps it open) to show the form
