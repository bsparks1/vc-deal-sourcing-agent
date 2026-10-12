# The Inbox page: review companies the agent found (status 'new'), best score first.
# For each one, give a thumbs up/down with a reason, then save it to the watchlist or pass.
# Each review re-summarizes all feedback into "learned preferences" for the agent's next run.

import streamlit as st

from scout import companies, feedback
from scout.founders import describe_founder
from scout.page_setup import setup_page
from scout.scoring import RUBRIC_MAX

setup_page("Inbox")  # title, database tables, daily scheduler

st.title("Inbox")

# A message saved before st.rerun() (below), shown once on the next run of the page.
# Without this, the confirmation would vanish when the page reloads.
if "inbox_message" in st.session_state:
    st.success(st.session_state.pop("inbox_message"))
if "inbox_warning" in st.session_state:
    st.warning(st.session_state.pop("inbox_warning"))

inbox = companies.list_companies("new")
if not inbox:
    st.info("Nothing to review. Run the agent from the Source page to find companies.")
    st.page_link("pages/2_Source.py", label="Go to Source", icon="🔎")
    st.stop()

noun = "company" if len(inbox) == 1 else "companies"
st.write(f"{len(inbox)} {noun} to review, best score first.")

for company in inbox:
    with st.container(border=True):
        left, right = st.columns([4, 1])
        left.subheader(company["name"])
        left.write(company["one_liner"] or "")
        right.metric("Score", f"{company['score_total']}/100")

        # Short facts line, skipping anything the agent couldn't verify.
        facts = [company["category"], company["stage"], company["location"],
                 company["funding_summary"]]
        st.caption(" · ".join(fact for fact in facts if fact))
        if company["website"]:
            st.markdown(f"[{company['domain']}]({company['website']})")
        st.page_link("pages/5_Company.py", label="Full profile", icon="📄",
                     query_params={"id": company["id"]})

        with st.expander("Why this score"):
            st.write(company["rationale"])
            breakdown = company["score_breakdown"] or {}
            for dimension, maximum in RUBRIC_MAX.items():
                st.write(f"- **{dimension}**: {breakdown.get(dimension, '?')}/{maximum}")
            if company["founders"]:
                st.write("**Founders:** " + "; ".join(describe_founder(f) for f in company["founders"]))
            st.write("**Sources:**")
            for url in company["sources"] or []:
                st.write(f"- {url}")

        # One small form per company. The key must be unique, so it includes the company id.
        with st.form(f"review_{company['id']}"):
            verdict = st.radio(
                "Is this a good lead for us?", ["👍 Good lead", "👎 Bad lead"],
                index=None, horizontal=True,  # index=None: nothing pre-selected
            )
            reason = st.text_input("Why? (the agent learns from this)",
                                   placeholder="e.g. too far along, already in Whole Foods")
            watch_col, pass_col = st.columns(2)
            watch = watch_col.form_submit_button("⭐ Save to watchlist", use_container_width=True)
            skip = pass_col.form_submit_button("Pass", use_container_width=True)

        if watch or skip:
            if verdict is None:
                st.error("Pick 👍 or 👎 first, so the agent can learn from your call.")
            else:
                feedback.add_feedback(company["id"], "up" if verdict.startswith("👍") else "down",
                                       reason.strip())
                companies.set_company_status(company["id"], "watching" if watch else "passed")
                # Re-summarize all feedback so the agent's next run reflects this review.
                with st.spinner("Updating what Scout has learned..."):
                    try:
                        feedback.update_learned_preferences()
                    except Exception as error:
                        # The review itself is already saved; only the summary failed.
                        st.session_state["inbox_warning"] = f"Couldn't update learned preferences: {error}"
                st.session_state["inbox_message"] = (
                    f"{company['name']} {'saved to watchlist' if watch else 'passed'}."
                )
                st.rerun()  # reload so the reviewed company disappears from the list
