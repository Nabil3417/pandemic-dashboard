"""
scheduler.py — Auto-runs all collectors every 12 hours inside the Flask server.

Features:
  - Runs every 12 hours
  - Catch-up: if the server was off during a scheduled run, it runs immediately on startup
  - Runs in a background thread — doesn't block Flask
  - Logs last run time to a local JSON file for persistence
"""

import os
import sys
import json
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─── PERSISTENCE FILE ──────────────────────────────────────────────────────────
# Tracks when the last collection happened (survives server restarts)

STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "scheduler_state.json"
)


def _load_state():
    """Load last run time from JSON file."""
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"last_run": None}


def _save_state(state):
    """Save last run time to JSON file."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def _needs_catchup(hours_interval=12):
    """Check if a scheduled run was missed (server was off)."""
    state = _load_state()
    last_run = state.get("last_run")

    if last_run is None:
        return True  # Never run before — run now

    try:
        last_dt = datetime.fromisoformat(last_run)
        if datetime.now() - last_dt > timedelta(hours=hours_interval):
            return True  # Missed a run
    except Exception:
        return True

    return False


def run_collection_job():
    """The actual job that APScheduler calls."""
    from data_collectors.social_media_manager import run_all_collectors

    print(f"\n{'='*60}")
    print(f"  ⏰ SCHEDULED COLLECTION — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    try:
        run_all_collectors(days_back=7)  # Only look back 7 days for scheduled runs
    except Exception as e:
        print(f"❌ Scheduled collection failed: {e}")

    # Save state
    _save_state({"last_run": datetime.now().isoformat()})


# ─── START SCHEDULER ───────────────────────────────────────────────────────────

def start_scheduler():
    """
    Start the APScheduler in background.
    Call this once when Flask starts.

    - If a run was missed (server was off), it runs immediately.
    - Then schedules every 12 hours going forward.
    """
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler()

    # Schedule: every 12 hours
    scheduler.add_job(
        run_collection_job,
        'interval',
        hours=12,
        id='social_media_collection',
        replace_existing=True,
    )

    scheduler.start()
    print("⏰ Scheduler started — collectors will run every 12 hours")

    # Catch-up: run now if we missed a scheduled run
    if _needs_catchup(hours_interval=12):
        print("⏰ Catching up — running missed collection now...")
        # Run in background so Flask doesn't block
        scheduler.add_job(
            run_collection_job,
            id='catchup_run',
            replace_existing=True,
        )
    else:
        state = _load_state()
        last = state.get("last_run", "never")
        print(f"⏰ Last collection was at: {last}")
        print(f"⏰ Next collection in: ~12 hours")

    return scheduler