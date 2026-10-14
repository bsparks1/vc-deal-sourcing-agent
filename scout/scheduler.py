# Runs the agent automatically once a day while the Streamlit app is running (Build Step 12).
# A background thread wakes up every few minutes and asks one question: is a scheduled run
# due? It's due when the schedule is on, the local time is past the fund's chosen hour, and
# no scheduled run has started yet today. If so, it runs the agent for the daily target.

import threading
import time
from datetime import datetime

from scout import config, db, runs
from scout.agent import run_agent

THREAD_NAME = "scout-scheduler"


def to_local(timestamp: str) -> datetime:
    """Turn a stored UTC timestamp (e.g. '2026-10-12T18:40:00+00:00') into local time."""
    return datetime.fromisoformat(timestamp).astimezone()


# [A13 Autonomy] The agent runs on a schedule without a person clicking Run.
def is_run_due(profile: dict | None, now: datetime, last_scheduled_start: datetime | None) -> bool:
    """Decide whether a scheduled run should start now.

    A pure function (no database, no clock of its own) so it can be tested with any times.
    """
    if not profile or not profile.get("schedule_enabled"):
        return False
    if now.hour < (profile.get("schedule_hour") or 0):
        return False  # too early today
    # At most one scheduled run per day. If the app was closed at the scheduled hour, this
    # still catches up later the same day, but it never runs extra to make up past days.
    return last_scheduled_start is None or last_scheduled_start.date() < now.date()


def next_run_description(profile: dict | None) -> str:
    """A short, human-readable status line for the schedule (shown on the Source page)."""
    if not profile or not profile.get("schedule_enabled"):
        return "Off. Turn it on in your Fund Profile."
    target = min(profile.get("daily_target") or 1, config.SCHEDULE_MAX_TARGET)
    noun = "company" if target == 1 else "companies"
    return f"Daily after {profile['schedule_hour']}:00 (your computer's time), {target} {noun} per run."


def run_scheduled_if_due() -> dict | None:
    """Check the schedule and, if a run is due, run the agent. Returns the run's result or None."""
    db.init_db()
    profile = db.get_fund_profile()
    last = runs.list_runs(limit=1, trigger="scheduled")
    last_start = to_local(last[0]["started_at"]) if last else None
    if not is_run_due(profile, datetime.now().astimezone(), last_start):
        return None

    target = min(profile.get("daily_target") or 1, config.SCHEDULE_MAX_TARGET)
    # Nobody is watching a scheduled run, so its steps go to the terminal running Streamlit.
    return run_agent(target=target, trigger="scheduled",
                     on_step=lambda line: print(f"[scheduled] {line}"))


def scheduler_loop() -> None:
    """Check forever, every SCHEDULER_CHECK_SECONDS. Runs inside the background thread."""
    while True:
        try:
            result = run_scheduled_if_due()
            if result:
                print(f"[scheduled] Run {result['run_id']}: {result['status']}, "
                      f"{result['companies_saved']} saved")
        except Exception as error:  # one bad check must not kill the scheduler for good
            print(f"[scheduled] Check failed: {error}")
        time.sleep(config.SCHEDULER_CHECK_SECONDS)


def start_scheduler() -> None:
    """Start the background scheduler thread, unless it's already running.

    Every page calls this. We look for a live thread by name (rather than a module-level
    flag) because Streamlit can re-import this module when files change, which would reset a
    flag and start a second scheduler.
    """
    if any(thread.name == THREAD_NAME for thread in threading.enumerate()):
        return
    # daemon=True: the thread stops automatically when the app stops.
    threading.Thread(target=scheduler_loop, name=THREAD_NAME, daemon=True).start()
