# Explore: review new matches one at a time, like a dating app. Swipe right (or press →) to add
# a company to the watchlist, left (or ←) to pass. Full detail is one click away under the card.
# After each swipe you can optionally say why; every swipe teaches Scout your taste.

import streamlit as st

from scout import companies, feedback
from ui.details import render_detail_tabs
from ui.swipe import swipe_card

# Quick "why?" reasons offered after a swipe, so feedback takes one click.
REASONS = {
    "up": ["Great founder story", "Strong category fit", "Early traction", "Unique product"],
    "down": ["Too established", "Wrong category", "Already funded", "Weak team signal",
             "Crowded market"],
}

st.title("Explore new companies")


def decide(company: dict, direction: str) -> None:
    """Record a swipe: save the feedback, move the company, and remember it for the 'why?' box."""
    verdict = "up" if direction == "right" else "down"
    feedback_id = feedback.add_feedback(company["id"], verdict)
    if verdict == "up":
        companies.set_company_status(company["id"], "watching")
        companies.set_deal_status(company["id"], "watching")
    else:
        companies.set_company_status(company["id"], "passed")
    feedback.refresh_learned_preferences_in_background()  # don't make the user wait for it
    st.session_state["last_swipe"] = {"feedback_id": feedback_id, "name": company["name"],
                                      "verdict": verdict}
    st.rerun()  # show the next card


# --- Optional "why?" for the previous swipe ---
last = st.session_state.get("last_swipe")
if last:
    action = "added to your watchlist ⭐" if last["verdict"] == "up" else "passed"
    with st.container(border=True):
        with st.form("why"):
            st.markdown(f"**{last['name']}** {action}. Why? *(optional, helps Scout learn)*")
            picked = st.pills("Quick reasons", REASONS[last["verdict"]], selection_mode="multi",
                              label_visibility="collapsed")
            note = st.text_input("Anything else?", label_visibility="collapsed",
                                 placeholder="Anything else? e.g. founder already runs a big brand")
            save_col, skip_col = st.columns(2)
            save = save_col.form_submit_button("Save reason", type="primary", width="stretch")
            skip = skip_col.form_submit_button("Skip", width="stretch")
        if save or skip:
            if save:
                reason = "; ".join(list(picked or []) + ([note.strip()] if note.strip() else []))
                feedback.set_feedback_reason(last["feedback_id"], reason)
                feedback.refresh_learned_preferences_in_background()
            del st.session_state["last_swipe"]
            st.rerun()

# --- The current card ---
queue = companies.list_companies("new")  # best score first
if not queue:
    st.success("You're all caught up: no new matches to review.")
    st.write("Use **Run agentic analysis** in the sidebar to find more companies.")
    st.page_link("views/watchlist.py", label="Go to your watchlist", icon="⭐")
    st.stop()

company = queue[0]
st.caption(f"{len(queue)} to review · best match first")

direction = swipe_card(company)

# Buttons (and arrow keys) do the same as swiping, for people without a touchscreen or trackpad.
pass_col, like_col = st.columns(2)
if pass_col.button("Pass", icon=":material/close:", width="stretch", shortcut="Left",
                   key=f"pass_{company['id']}"):
    direction = "left"
if like_col.button("Interested", icon=":material/favorite:", type="primary", width="stretch",
                   shortcut="Right", key=f"like_{company['id']}"):
    direction = "right"

with st.expander("More detail: score, founders, traction, sources"):
    render_detail_tabs(company)
    st.page_link("views/company.py", label="Open full profile", icon="📄",
                 query_params={"id": company["id"]})

if direction:
    decide(company, direction)
