# Reading and writing companies in the SQLite database.
# The agent's tools use it to check and save companies; the pages use it to list companies,
# show one company, and move companies between review (new), watchlist, and passed.
# Connection and table setup live in scout/db.py; agent runs in scout/runs.py; feedback in
# scout/feedback.py.

import json
from datetime import datetime, timedelta, timezone

from scout.db import get_connection, now

def normalize_domain(url_or_domain: str) -> str:
    """Turn 'https://www.Example.com/about' into 'example.com'.

    The domain is how we tell companies apart, so every spelling of a site must match.
    """
    text = url_or_domain.strip().lower()
    text = text.split("://")[-1]  # drop "https://"
    text = text.split("/")[0]  # drop any path like "/about"
    return text.removeprefix("www.")


def find_company(name_or_domain: str) -> dict | None:
    """Return a saved company matching this domain or (case-insensitive) name, or None."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM companies WHERE domain = ? OR lower(name) = lower(?)",
            (normalize_domain(name_or_domain), name_or_domain.strip()),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def save_company(company: dict) -> int:
    """Insert a new company with status 'new' and return its id.

    Raises sqlite3.IntegrityError if the domain is already saved (domain is UNIQUE).
    """
    columns = [
        "name", "domain", "website", "one_liner", "category", "stage", "location",
        "founded_year", "funding_summary", "founders", "score_total", "score_breakdown",
        "rationale", "sources", "traction", "run_id",
    ]
    values = {column: company.get(column) for column in columns}
    values["created_at"] = values["updated_at"] = now()

    conn = get_connection()
    try:
        names = ", ".join(values)  # "name, domain, ..." built from our own fixed list
        placeholders = ", ".join(f":{column}" for column in values)
        cursor = conn.execute(f"INSERT INTO companies ({names}) VALUES ({placeholders})", values)
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def parse_company(row) -> dict:
    """Turn a companies row into a dict, decoding the JSON text columns into lists/dicts."""
    company = dict(row)
    for column in ("founders", "sources", "score_breakdown", "traction"):
        # "or 'null'" handles empty cells; json.loads('null') gives None.
        company[column] = json.loads(company[column] or "null")
    return company


def get_company(company_id: int) -> dict | None:
    """Return one company by id (with JSON columns decoded), or None if it doesn't exist."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
    finally:
        conn.close()
    return parse_company(row) if row else None


def count_by_status() -> dict[str, int]:
    """Return how many companies are in each status, e.g. {'new': 2, 'watching': 5}."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT status, COUNT(*) FROM companies GROUP BY status").fetchall()
    finally:
        conn.close()
    counts = {"new": 0, "watching": 0, "passed": 0}  # so missing statuses show as 0
    counts.update({status: count for status, count in rows})
    return counts


def list_companies(status: str) -> list[dict]:
    """Return all companies with this status ('new', 'watching', 'passed'), best score first.

    The JSON text columns are turned back into Python lists/dicts so pages can use them.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM companies WHERE status = ? ORDER BY score_total DESC, id DESC",
            (status,),
        ).fetchall()
    finally:
        conn.close()

    return [parse_company(row) for row in rows]


def update_founders(company_id: int, founders: list[dict]) -> None:
    """Replace a company's founders (used by the Company page's "Research founders" button)."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE companies SET founders = ?, updated_at = ? WHERE id = ?",
            (json.dumps(founders), now(), company_id),
        )
        conn.commit()
    finally:
        conn.close()


# Where a watchlist company is in the fund's process. Shown as a dropdown on the Watchlist.
DEAL_STATUSES = {"watching": "👀 Watching", "reached_out": "✉️ Reached out",
                 "in_conversation": "💬 In conversation"}


def set_deal_status(company_id: int, deal_status: str) -> None:
    """Update where a watchlist company is in the process (e.g. 'reached_out')."""
    conn = get_connection()
    try:
        conn.execute("UPDATE companies SET deal_status = ?, updated_at = ? WHERE id = ?",
                     (deal_status, now(), company_id))
        conn.commit()
    finally:
        conn.close()


def set_company_status(company_id: int, status: str) -> None:
    """Move a company to 'watching' (watchlist) or 'passed'."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE companies SET status = ?, updated_at = ? WHERE id = ?",
            (status, now(), company_id),
        )
        conn.commit()
    finally:
        conn.close()


def pipeline_stats() -> dict:
    """Headline numbers for the dashboard: companies in each stage of the pipeline,
    how many were found in the last 7 days, and the average score of those awaiting review."""
    conn = get_connection()
    try:
        by_status = dict(conn.execute(
            "SELECT status, COUNT(*) FROM companies GROUP BY status").fetchall())
        by_deal = dict(conn.execute(
            "SELECT deal_status, COUNT(*) FROM companies WHERE status = 'watching' "
            "GROUP BY deal_status").fetchall())
        # Timestamps are ISO text, so comparing as text works for "newer than".
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(timespec="seconds")
        found_7d = conn.execute("SELECT COUNT(*) FROM companies WHERE created_at >= ?",
                                (week_ago,)).fetchone()[0]
        avg_new = conn.execute(
            "SELECT AVG(score_total) FROM companies WHERE status = 'new'").fetchone()[0]
    finally:
        conn.close()
    return {
        "new": by_status.get("new", 0), "watching": by_status.get("watching", 0),
        "passed": by_status.get("passed", 0), "found_7d": found_7d,
        "avg_new_score": round(avg_new) if avg_new is not None else None,
        # Older rows saved before deal_status existed count as plain "watching".
        "deal": {key: by_deal.get(key, 0) for key in DEAL_STATUSES}
                | {"watching": by_deal.get("watching", 0) + by_deal.get(None, 0)},
    }

