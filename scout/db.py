# The SQLite foundation for Scout: the connection, the table definitions, and the fund
# profile. Company and run queries live in scout/companies.py; feedback in scout/feedback.py.
# The rest of the app never writes SQL itself; it calls functions in those files.
# The database is a single file (config.DB_PATH, "scout.db") in the project folder.

import sqlite3
from datetime import datetime, timezone

from scout import config

# The tables from SPEC.md, plus learned_preferences (Step 7) and company_checks (Step 13).
# "IF NOT EXISTS" makes this safe to run on every app start.
# Lists (founders, sources) and dicts (score_breakdown) are stored as JSON text,
# because SQLite has no list or dict column type.
SCHEMA = """
CREATE TABLE IF NOT EXISTS fund_profile (
    id INTEGER PRIMARY KEY,
    fund_name TEXT NOT NULL,
    thesis TEXT NOT NULL,
    categories TEXT,
    stages TEXT,
    check_size TEXT,
    include_signals TEXT,
    exclude_signals TEXT,
    daily_target INTEGER,
    schedule_enabled INTEGER DEFAULT 0,  -- 1 = run the agent automatically each day (Step 12)
    schedule_hour INTEGER DEFAULT 9,     -- local hour (0-23) after which the daily run starts
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    domain TEXT UNIQUE,              -- UNIQUE stops the agent saving the same company twice
    website TEXT,
    one_liner TEXT,
    category TEXT,
    stage TEXT,
    location TEXT,
    founded_year INTEGER,
    funding_summary TEXT,
    founders TEXT,                   -- JSON text
    score_total INTEGER,
    score_breakdown TEXT,            -- JSON text
    rationale TEXT,
    sources TEXT,                    -- JSON list of URLs
    traction TEXT,                   -- JSON list of signals (added in Step 9)
    deal_status TEXT DEFAULT 'watching',  -- for watchlist companies: 'watching' | 'reached_out' | 'in_conversation'
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'watching', 'passed')),
    run_id INTEGER REFERENCES runs(id),
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    verdict TEXT NOT NULL CHECK (verdict IN ('up', 'down')),
    reason TEXT,
    created_at TEXT
);

-- One row each time feedback is summarized (Step 7). The newest row is what the agent
-- uses; older rows are kept so you can see how its preferences changed over time.
CREATE TABLE IF NOT EXISTS learned_preferences (
    id INTEGER PRIMARY KEY,
    summary TEXT NOT NULL,
    feedback_count INTEGER,
    created_at TEXT
);

-- One row per change check on a watchlist company (Step 13). "changes" is a JSON list.
CREATE TABLE IF NOT EXISTS company_checks (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    checked_at TEXT,
    summary TEXT,
    changes TEXT,
    exclusion_now_applies INTEGER DEFAULT 0,
    exclusion_reason TEXT
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    request TEXT,
    started_at TEXT,
    finished_at TEXT,
    companies_saved INTEGER DEFAULT 0,
    status TEXT,
    error TEXT,
    trigger TEXT DEFAULT 'manual'    -- 'manual' (Source page / terminal) or 'scheduled'
);
"""

# The fund_profile columns a user can edit (everything except id and updated_at).
PROFILE_FIELDS = [
    "fund_name", "thesis", "categories", "stages", "check_size",
    "include_signals", "exclude_signals", "daily_target", "schedule_enabled", "schedule_hour",
]


def now() -> str:
    """Return the current UTC time as text, e.g. '2026-10-12T18:40:00+00:00'.

    SQLite has no date type, so we store ISO-format strings (which also sort correctly).
    """
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_connection() -> sqlite3.Connection:
    """Open a connection to the Scout database file.

    Row factory lets us read columns by name (row["thesis"]) instead of by position.
    """
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    # SQLite ignores REFERENCES (foreign keys) unless this is switched on per connection.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Columns added after a table was first created. "CREATE TABLE IF NOT EXISTS" never changes
# a table that already exists, so init_db adds any of these that are missing.
ADDED_COLUMNS = {
    "companies": {"traction": "TEXT", "deal_status": "TEXT DEFAULT 'watching'"},
    "fund_profile": {"schedule_enabled": "INTEGER DEFAULT 0", "schedule_hour": "INTEGER DEFAULT 9"},
    "runs": {"trigger": "TEXT DEFAULT 'manual'"},
}


def init_db() -> None:
    """Create all tables if they don't exist yet, and add any newer columns.

    Safe to call every time the app starts.
    """
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        for table, columns in ADDED_COLUMNS.items():
            # PRAGMA table_info lists a table's current columns, one row per column.
            existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            for name, column_type in columns.items():
                if name not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {column_type}")
        conn.commit()
    finally:
        conn.close()  # always close, even if the SQL fails


def get_fund_profile() -> dict | None:
    """Return the saved fund profile as a dict, or None if none has been saved yet."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM fund_profile WHERE id = 1").fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def save_fund_profile(profile: dict) -> None:
    """Insert or update the fund profile.

    Phase 1 supports one fund, so the profile always lives in the row with id = 1.
    "ON CONFLICT ... DO UPDATE" means: insert it the first time, overwrite it after that.
    """
    values = {field: profile.get(field) for field in PROFILE_FIELDS}
    values["updated_at"] = now()

    conn = get_connection()
    try:
        # Named placeholders (:fund_name) let SQLite insert the values safely,
        # which prevents SQL injection; we never paste user text into the SQL string.
        conn.execute(
            """
            INSERT INTO fund_profile (id, fund_name, thesis, categories, stages, check_size,
                                      include_signals, exclude_signals, daily_target,
                                      schedule_enabled, schedule_hour, updated_at)
            VALUES (1, :fund_name, :thesis, :categories, :stages, :check_size,
                    :include_signals, :exclude_signals, :daily_target,
                    :schedule_enabled, :schedule_hour, :updated_at)
            ON CONFLICT(id) DO UPDATE SET
                fund_name = excluded.fund_name,
                thesis = excluded.thesis,
                categories = excluded.categories,
                stages = excluded.stages,
                check_size = excluded.check_size,
                include_signals = excluded.include_signals,
                exclude_signals = excluded.exclude_signals,
                daily_target = excluded.daily_target,
                schedule_enabled = excluded.schedule_enabled,
                schedule_hour = excluded.schedule_hour,
                updated_at = excluded.updated_at
            """,
            values,
        )
        conn.commit()
    finally:
        conn.close()

