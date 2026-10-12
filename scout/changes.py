# Change tracking for watchlist companies (Build Step 13): re-research a company, compare the
# new evidence with what Scout knew when it was saved, and record what changed. Every check is
# stored in the company_checks table, so the Company page can show the full history.
# Saved company facts are never overwritten; the checks are the record of what changed.

import json
from typing import Literal

from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field

from scout import config, db
from scout.db import get_connection, now
from scout.defaults import DEFAULT_FUND_PROFILE
from scout.web import get_tavily_client


class Change(BaseModel):
    """One thing that's different from what we knew."""

    field: Literal["funding", "stage", "retail", "traction", "team", "product", "other"]
    before: str = Field(description="What we knew before (or 'unknown').")
    after: str = Field(description="What the new evidence shows.")
    significant: bool = Field(description="True if an investor would want to know about it.")
    source_urls: list[str] = Field(description="URLs from the evidence that show this change.")


class ChangeReport(BaseModel):
    """The full answer the model must return."""

    changes: list[Change]
    summary: str = Field(description="One sentence: what changed, or 'No material changes found.'")
    exclusion_now_applies: bool = Field(
        description="True if the evidence shows one of the fund's exclusion signals now applies.")
    exclusion_reason: str = Field(description="Which signal and why. Empty string if none.")


COMPARE_PROMPT = """You track companies on a venture fund's watchlist. Compare what the fund
knew about this company with NEW EVIDENCE gathered today, and list what has changed.

Rules:
- Only list changes the evidence actually shows. Never use your own knowledge.
- A change is something new or different (a funding round, new retailers, a new product, a
  founder leaving, much higher follower counts), not a restatement of what we already knew.
- Don't repeat changes that are already recorded below.
- Cite the evidence URLs (exactly as given) for each change.
- The fund rules a company out if any of these apply: {exclude_signals}

WHAT WE KNEW (saved {saved_on}):
{known}

CHANGES ALREADY RECORDED:
{previous}

NEW EVIDENCE (published since {since}, plus the company's website today):
{evidence}
"""


def gather_evidence(name: str, website: str | None, since: str) -> list[dict]:
    """Search for news published since `since` (YYYY-MM-DD) and read the website as it is today."""
    client = get_tavily_client()
    results = {}  # keyed by URL to avoid duplicates
    for query in [f'"{name}"', f'"{name}" funding OR raises OR retail OR stores OR launches']:
        # start_date limits results to pages published on or after that date.
        response = client.search(query=query, start_date=since, max_results=config.SEARCH_MAX_RESULTS)
        for item in response.get("results", []):
            results[item["url"]] = {"url": item["url"], "text": item.get("content", "")}
    if website:
        try:
            page = client.extract(urls=[website], format="text").get("results", [])
        except Exception:
            page = []  # a website that blocks reading shouldn't stop the check
        for item in page:
            results[item["url"]] = {"url": item["url"],
                                    "text": (item.get("raw_content") or "")[: config.PAGE_MAX_CHARS]}
    return list(results.values())


def check_company(company: dict) -> dict:
    """Re-research one company, record what changed, and return the saved check as a dict."""
    config.require_keys()
    history = list_checks(company["id"])
    # Look for news since the last check, or since the company was saved if never checked.
    since = (history[-1]["checked_at"] if history else company["created_at"] or now())[:10]
    evidence = gather_evidence(company["name"], company["website"], since)

    known = {key: company.get(key) for key in
             ["one_liner", "stage", "funding_summary", "location", "traction", "founders"]}
    previous = [c for check in history for c in check["changes"]]
    profile = db.get_fund_profile() or DEFAULT_FUND_PROFILE
    prompt = COMPARE_PROMPT.format(
        exclude_signals=(profile.get("exclude_signals") or "").replace("\n", "; "),
        saved_on=(company["created_at"] or "unknown")[:10], known=json.dumps(known, indent=2),
        previous=json.dumps(previous, indent=2) if previous else "none", since=since,
        evidence="\n\n".join(f"URL: {e['url']}\n{e['text']}" for e in evidence) or "(nothing found)")

    llm = ChatAnthropic(model=config.MODEL, api_key=config.ANTHROPIC_API_KEY,
                        max_tokens=config.SCORING_MAX_TOKENS)
    report: ChangeReport = llm.with_structured_output(ChangeReport, method="json_schema").invoke(prompt)

    # Same source check as founder research: keep only URLs we really fetched, and drop any
    # change left with no real source (it can't be verified, so we don't record it).
    fetched = {e["url"] for e in evidence}
    changes = []
    for change in report.changes:
        real = [url for url in change.source_urls if url in fetched]
        if real:
            changes.append({**change.model_dump(), "source_urls": real})
    exclusion = report.exclusion_now_applies and bool(changes)  # a flag needs sourced evidence

    save_check(company["id"], report.summary, changes, exclusion, report.exclusion_reason)
    return list_checks(company["id"])[-1]


# --- Storing checks ---

def save_check(company_id: int, summary: str, changes: list[dict], exclusion: bool,
               exclusion_reason: str) -> None:
    """Record one change check for a company."""
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO company_checks (company_id, checked_at, summary, changes,
                                           exclusion_now_applies, exclusion_reason)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (company_id, now(), summary, json.dumps(changes), int(exclusion), exclusion_reason),
        )
        conn.commit()
    finally:
        conn.close()


def list_checks(company_id: int) -> list[dict]:
    """Return every check for a company, oldest first, with its changes decoded from JSON."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM company_checks WHERE company_id = ? ORDER BY id",
                            (company_id,)).fetchall()
    finally:
        conn.close()
    return [{**dict(row), "changes": json.loads(row["changes"] or "[]")} for row in rows]


def change_status(company_id: int) -> dict:
    """Summarize a company's check history for a badge: change count, flag, last checked."""
    checks = list_checks(company_id)
    return {
        "checked": bool(checks),
        "last_checked": checks[-1]["checked_at"] if checks else None,
        "significant": sum(c["significant"] for check in checks for c in check["changes"]),
        "exclusion": any(check["exclusion_now_applies"] for check in checks),
    }

