# Sections that display what Scout knows about one company. Written once and reused by the
# Explore page (inside the "More detail" dropdown) and the full Company page, so both always
# show the same information in the same way.

import streamlit as st

from scout.changes import list_checks
from scout.feedback import list_feedback_for_company
from scout.scoring import RUBRIC_MAX


def facts_line(company: dict) -> str:
    """'Category · Stage · Location · Founded 2025', skipping anything unknown."""
    founded = f"Founded {company['founded_year']}" if company.get("founded_year") else None
    parts = [company.get("category"), company.get("stage"), company.get("location"), founded]
    return " · ".join(str(part) for part in parts if part)


def render_overview(company: dict) -> None:
    """Key facts. Blank facts say "Unknown" rather than being guessed."""
    facts = {"Category": company["category"], "Stage": company["stage"],
             "Location": company["location"], "Founded": company["founded_year"],
             "Funding": company["funding_summary"]}
    for label, value in facts.items():
        st.write(f"**{label}:** {value if value else 'Unknown'}")


def render_traction(company: dict) -> None:
    """Traction signals the agent recorded (follower counts, retailers, press)."""
    for signal in company.get("traction") or ["No traction signals recorded."]:
        st.write(f"- {signal}")


def render_founders(company: dict) -> None:
    """One card per founder, with numbered links to the sources that back them up."""
    founders = company.get("founders") or []
    if not founders:
        st.write("No founders found yet.")
    for founder in founders:
        if isinstance(founder, str):  # saved before founder research existed: plain text
            st.write(f"- {founder}")
            continue
        with st.container(border=True):
            role = f" · {founder['role']}" if founder.get("role") else ""
            st.markdown(f"**{founder['name']}**{role}")
            st.write(founder.get("background") or "Background unknown.")
            links = ", ".join(f"[{i + 1}]({url})" for i, url in enumerate(founder["source_urls"]))
            st.caption(f"Sources: {links}")


def render_score(company: dict) -> None:
    """One progress bar per rubric dimension, then the scorer's explanation."""
    breakdown = company.get("score_breakdown") or {}
    for dimension, maximum in RUBRIC_MAX.items():
        points = breakdown.get(dimension, 0)
        # st.progress needs a number from 0.0 to 1.0, so divide by the dimension's maximum.
        st.progress(points / maximum, text=f"{dimension.replace('_', ' ')}: {points}/{maximum}")
    st.write(company.get("rationale") or "")


def render_sources(company: dict) -> None:
    """Every page the agent's facts came from."""
    for url in company.get("sources") or []:
        st.write(f"- {url}")


def render_changes(company: dict) -> None:
    """Every change check on this company, newest first, each change with its sources."""
    checks = list_checks(company["id"])
    if not checks:
        st.write("Not checked yet.")
    for check in reversed(checks):
        st.markdown(f"**{check['checked_at'][:10]}**: {check['summary']}")
        if check["exclusion_now_applies"]:
            st.error(check["exclusion_reason"])
        for change in check["changes"]:
            mark = "Significant · " if change["significant"] else ""
            links = ", ".join(f"[{i + 1}]({url})" for i, url in enumerate(change["source_urls"]))
            st.write(f"- {mark}**{change['field']}**: {change['before']} → {change['after']} ({links})")


def render_reviews(company: dict) -> None:
    """The fund's past swipes on this company, with reasons."""
    reviews = list_feedback_for_company(company["id"])
    if not reviews:
        st.write("No reviews yet.")
    for review in reviews:
        thumb = "Interested" if review["verdict"] == "up" else "Passed"
        st.write(f"**{thumb}**: {review['reason'] or '(no reason given)'} · `{review['created_at'][:10]}`")


def render_detail_tabs(company: dict) -> None:
    """All the detail sections as tabs: used inside Explore's "More detail" dropdown."""
    tabs = st.tabs(["Why this score", "Founders", "Traction", "Overview", "Sources"])
    with tabs[0]:
        render_score(company)
    with tabs[1]:
        render_founders(company)
    with tabs[2]:
        render_traction(company)
    with tabs[3]:
        render_overview(company)
    with tabs[4]:
        render_sources(company)
