# Recording agent runs in the SQLite database: when each run started and finished, what it
# was asked to do, whether it was started by a person or the daily scheduler, and how many
# companies it saved. Used by scout/agent.py, scout/scheduler.py, and the dashboard.

from scout.db import get_connection, now


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
