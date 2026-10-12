# Everything about the fund's reviews: storing thumbs up / down in SQLite, and turning them
# into a short "learned preferences" paragraph. The Inbox calls update_learned_preferences()
# after each review; scout/agent.py adds the newest paragraph to the agent's system prompt
# on its next run. This is in-context learning: no model is trained, and exactly what the
# agent was told is visible in traces.

from langchain_anthropic import ChatAnthropic

from scout import config
from scout.db import get_connection, now

SUMMARY_PROMPT = """Below are a venture fund's reviews of companies an AI research agent found.
Write a short paragraph (at most 120 words) of guidance for the agent's next search:
what kinds of companies the fund liked, what it rejected, and any patterns in its reasons.

Rules:
- Only state preferences the reviews actually support. Don't invent new criteria.
- Base patterns on the fund's stated reasons, not on incidental details of a company's
  description. If a company was rejected "because the founder already runs a brand",
  don't also conclude anything about its sales channels or product.
- Prefer specific, usable guidance ("skip brands whose founder already runs an established
  company") over vague praise ("the fund likes good companies").
- If a pattern rests on a single review, say it is tentative.
- Write it as direct instructions to the agent, in plain text with no headings.

REVIEWS (newest first):
{reviews}
"""


def format_review(item: dict) -> str:
    """Turn one feedback row into a readable line for the prompt."""
    verdict = "LIKED" if item["verdict"] == "up" else "REJECTED"
    details = ", ".join(str(value) for value in [
        item["category"], item["stage"], item["funding_summary"],
        f"score {item['score_total']}",
    ] if value)
    reason = item["reason"] or "(no reason given)"
    return f"- {verdict}: {item['name']} ({details}). {item['one_liner'] or ''} Reason: {reason}"


def update_learned_preferences() -> str | None:
    """Summarize all recent feedback into a new learned-preferences paragraph and save it.

    Returns the new paragraph, or None if there's no feedback yet. One LLM call.
    """
    feedback = list_feedback(limit=config.FEEDBACK_LIMIT)
    if not feedback:
        return None

    config.require_keys()
    llm = ChatAnthropic(
        model=config.MODEL,
        api_key=config.ANTHROPIC_API_KEY,
        max_tokens=config.FEEDBACK_MAX_TOKENS,
        # Low effort: summarizing a list of reviews is easy, and the fund is waiting on it
        # after each click in the Inbox, so speed matters more than deep reasoning here.
        output_config={"effort": "low"},
    )
    reviews = "\n".join(format_review(item) for item in feedback)
    summary = llm.invoke(SUMMARY_PROMPT.format(reviews=reviews)).text.strip()

    save_learned_preferences(summary, feedback_count=len(feedback))
    return summary


# --- Storing reviews and learned preferences ---

def add_feedback(company_id: int, verdict: str, reason: str) -> None:
    """Record a thumbs up ('up') or down ('down') on a company, with an optional reason.

    Step 7 turns all of these into "learned preferences" for the agent's next run.
    """
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO feedback (company_id, verdict, reason, created_at) VALUES (?, ?, ?, ?)",
            (company_id, verdict, reason, now()),
        )
        conn.commit()
    finally:
        conn.close()


def list_feedback(limit: int = 50) -> list[dict]:
    """Return the most recent feedback, newest first, with the company each one is about.

    The limit keeps the summarizing prompt small even after hundreds of reviews.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT feedback.verdict, feedback.reason, companies.name, companies.one_liner,
                   companies.category, companies.stage, companies.funding_summary,
                   companies.score_total
            FROM feedback JOIN companies ON companies.id = feedback.company_id
            ORDER BY feedback.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def save_learned_preferences(summary: str, feedback_count: int) -> None:
    """Store a new learned-preferences summary (the newest one is the one in use)."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO learned_preferences (summary, feedback_count, created_at) VALUES (?, ?, ?)",
            (summary, feedback_count, now()),
        )
        conn.commit()
    finally:
        conn.close()


def get_learned_preferences() -> dict | None:
    """Return the newest learned-preferences row, or None if there's no feedback yet."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM learned_preferences ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def list_feedback_for_company(company_id: int) -> list[dict]:
    """Return every review of one company, oldest first (for its company page)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT verdict, reason, created_at FROM feedback WHERE company_id = ? ORDER BY id",
            (company_id,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]
