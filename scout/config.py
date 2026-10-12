# Central settings for Scout: API keys, model name, file paths, and URLs.
# Every other file imports settings from here instead of reading .env itself,
# so there is exactly one place to look when a setting needs to change.

import os
from pathlib import Path

from dotenv import load_dotenv

# The project folder: this file is scout/config.py, so go up two levels.
PROJECT_DIR = Path(__file__).resolve().parent.parent

# Read the project's .env file (if it exists) into environment variables. We give the exact
# path because, without one, python-dotenv sometimes searches the current folder instead.
# override=False means a variable already set in your shell wins over .env.
load_dotenv(PROJECT_DIR / ".env", override=False)

# --- Secrets (only ever come from .env / the environment) ---
# `or None` turns an empty value like "ANTHROPIC_API_KEY=" into None, so blank counts as missing.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY") or None
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY") or None

# --- Settings (sensible defaults, overridable in .env) ---
MODEL = os.getenv("MODEL") or "claude-sonnet-5-5"
DB_PATH = "scout.db"  # SQLite file, created in the project folder in Build Step 2
PHOENIX_ENDPOINT = "http://localhost:6006"  # where `uv run phoenix serve` listens

# --- Web tool limits (scout/tools.py) ---
SEARCH_MAX_RESULTS = 5  # results per search; more costs tokens without helping much
PAGE_MAX_CHARS = 8000  # cap on page text sent to the model, so one huge page can't flood it

# --- Scoring (scout/scoring.py) ---
SCORING_MAX_TOKENS = 16000  # room for the model's reasoning plus the JSON score
EXCLUDED_SCORE_CAP = 20  # max total for a company showing any exclusion signal (see scoring.py)

# --- Agent (scout/agent.py) ---
MIN_SAVE_SCORE = 60  # save_candidate refuses companies scoring below this
AGENT_MAX_STEPS = 80  # LangGraph "recursion limit": caps how long (and costly) one run can get
AGENT_MAX_TOKENS = 16000  # per model reply, including its reasoning
PHOENIX_PROJECT = "scout"  # traces are grouped under this project name in Phoenix

# --- Scheduled runs (scout/scheduler.py) ---
SCHEDULER_CHECK_SECONDS = 300  # how often the background scheduler checks if a run is due
SCHEDULE_MAX_TARGET = 10  # cap on companies per scheduled run, since nobody is watching it

# --- Learning from feedback (scout/feedback.py) ---
FEEDBACK_LIMIT = 50  # summarize only the most recent reviews, to keep the prompt small
FEEDBACK_MAX_TOKENS = 4000  # the summary is one short paragraph

# The keys Scout cannot work without. Used by the status check and require_keys().
REQUIRED_KEYS = {
    "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
    "TAVILY_API_KEY": TAVILY_API_KEY,
}


def missing_keys() -> list[str]:
    """Return the names (never the values) of required keys that are not set.

    The UI uses this to show a status check without crashing when a key is missing.
    """
    return [name for name, value in REQUIRED_KEYS.items() if not value]


def require_keys() -> None:
    """Stop with a clear error if any required key is missing.

    Code that is about to call an API (the agent, the tools) calls this first, so the
    error says "set TAVILY_API_KEY in .env" instead of a confusing 401 from the API.
    Only key names are included in the message, so no secret can leak into logs.
    """
    missing = missing_keys()
    if missing:
        raise RuntimeError(
            f"Missing required key(s): {', '.join(missing)}. "
            "Add them to your .env file (see .env.example), then restart the app."
        )
