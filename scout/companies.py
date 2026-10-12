# Reading and writing companies and agent runs in the SQLite database.
# The agent's tools use it to check and save companies; the pages use it to list companies,
# show one company, and move companies between inbox, watchlist, and passed.
# Connection and table setup live in scout/db.py; feedback lives in scout/feedback.py.

import json

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


def create_run(request: str, trigger: str = "manual") -> int:
    """Record that an agent run has started ('manual' or 'scheduled') and return its id."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO runs (request, started_at, status, trigger) VALUES (?, ?, 'running', ?)",
            (request, now(), trigger),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def list_runs(limit: int = 10, trigger: str | None = None) -> list[dict]:
    """Return the most recent agent runs, newest first, optionally only one trigger type."""
    conn = get_connection()
    try:
        if trigger:
            rows = conn.execute("SELECT * FROM runs WHERE trigger = ? ORDER BY id DESC LIMIT ?",
                                (trigger, limit)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def finish_run(run_id: int, status: str, error: str | None = None) -> int:
    """Mark a run as finished, count the companies it saved, and return that count."""
    conn = get_connection()
    try:
        saved = conn.execute(
            "SELECT COUNT(*) FROM companies WHERE run_id = ?", (run_id,)
        ).fetchone()[0]
        conn.execute(
            "UPDATE runs SET finished_at = ?, status = ?, companies_saved = ?, error = ? WHERE id = ?",
            (now(), status, saved, error, run_id),
        )
        conn.commit()
        return saved
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
