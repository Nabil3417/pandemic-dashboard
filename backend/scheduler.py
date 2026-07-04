"""
scheduler.py — Auto-runs all collectors and W-DZMI calculations inside Flask.

Jobs:
  - Social media collection: every 12 hours (original)
  - OSRM routing:            every 2 hours
  - Social volume calc:      every 30 minutes
  - Google Mobility:         every 24 hours (static CSV, mostly first-run)
  - Google Trends:           every 24 hours
  - W-DZMI composite:        every 1 hour

Features:
  - Catch-up: if server was off during a scheduled run, runs immediately on startup
  - Runs in background thread — doesn't block Flask
  - Persists last run time to local JSON for state tracking
"""

import os
import sys
import json
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─── PERSISTENCE ──────────────────────────────────────────────────────────────
STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "scheduler_state.json"
)


def _load_state():
    """Load last run times from JSON file."""
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_state(state):
    """Save last run times to JSON file."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def _needs_catchup(state, job_name, interval_hours):
    """Check if a specific job missed its scheduled run."""
    last_run = state.get(job_name)
    if last_run is None:
        return True
    try:
        last_dt = datetime.fromisoformat(last_run)
        if datetime.now() - last_dt > timedelta(hours=interval_hours):
            return True
    except Exception:
        return True
    return False


def _mark_run(state, job_name):
    """Mark a job as just run."""
    state[job_name] = datetime.now().isoformat()
    _save_state(state)
    return state


# ─── JOB FUNCTIONS ────────────────────────────────────────────────────────────

def job_social_media():
    """Original: Collect social media posts from all sources."""
    from data_collectors.social_media_manager import run_all_collectors

    print(f"\n{'='*60}")
    print(f"  SCHEDULED: Social Media Collection")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    try:
        run_all_collectors(days_back=7)
        state = _load_state()
        _mark_run(state, "social_media")
        print(f"  Social media collection completed.")
    except Exception as e:
        print(f"  Social media collection FAILED: {e}")


def job_osrm_routing():
    """Collect OSRM routing data for all 25 corridors."""
    from data_collectors.osrm_routing_signal import fetch_all_corridors

    print(f"\n{'='*60}")
    print(f"  SCHEDULED: OSRM Routing Collector")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    try:
        result = fetch_all_corridors()
        state = _load_state()
        _mark_run(state, "osrm_routing")
        print(f"  OSRM routing done — {result}")
    except Exception as e:
        print(f"  OSRM routing FAILED: {e}")


def job_social_volume():
    """Recalculate social volume scores from existing posts."""
    from data_collectors.social_volume_signal import calculate_all_zones

    print(f"\n{'='*60}")
    print(f"  SCHEDULED: Social Volume Calculator")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    try:
        count = calculate_all_zones()
        state = _load_state()
        _mark_run(state, "social_volume")
        print(f"  Social volume done — {count} zones scored.")
    except Exception as e:
        print(f"  Social volume FAILED: {e}")


def job_google_mobility():
    """Process Google Mobility CSV into zone scores."""
    from data_collectors.google_mobility_signal import process_mobility_data

    print(f"\n{'='*60}")
    print(f"  SCHEDULED: Google Mobility Processor")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    try:
        count = process_mobility_data()
        state = _load_state()
        _mark_run(state, "google_mobility")
        print(f"  Google Mobility done — {count} records.")
    except Exception as e:
        print(f"  Google Mobility FAILED: {e}")


def job_google_trends():
    """Fetch Google Trends symptom search data."""
    from data_collectors.google_trends_signal import main as gt_main

    print(f"\n{'='*60}")
    print(f"  SCHEDULED: Google Trends Collector")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    try:
        gt_main()
        state = _load_state()
        _mark_run(state, "google_trends")
        print(f"  Google Trends done.")
    except Exception as e:
        print(f"  Google Trends FAILED: {e}")


def job_wdzmi_composite():
    """Recalculate W-DZMI composite score from all 4 signals."""
    from data_collectors.dzmi import main as dzmi_main

    print(f"\n{'='*60}")
    print(f"  SCHEDULED: W-DZMI Composite Calculator")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    try:
        dzmi_main()
        state = _load_state()
        _mark_run(state, "wdzmi_composite")
        print(f"  W-DZMI composite done.")
    except Exception as e:
        print(f"  W-DZMI composite FAILED: {e}")


# ─── SCHEDULER SETUP ─────────────────────────────────────────────────────────

def start_scheduler():
    """
    Start APScheduler with all jobs.
    Call this once when Flask starts (in app.py).
    """
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler()

    # ── Register all jobs ────────────────────────────────────────────────
    jobs = [
        # (func,                    id,                      interval_kwargs)
        (job_social_media,         "social_media",           {"hours": 12}),
        (job_osrm_routing,         "osrm_routing",           {"hours": 2}),
        (job_social_volume,        "social_volume",          {"minutes": 30}),
        (job_google_mobility,      "google_mobility",        {"hours": 24}),
        (job_google_trends,        "google_trends",          {"hours": 24}),
        (job_wdzmi_composite,      "wdzmi_composite",        {"hours": 1}),
    ]

    for func, job_id, interval_kw in jobs:
        scheduler.add_job(
            func,
            'interval',
            id=job_id,
            replace_existing=True,
            **interval_kw,
        )

    scheduler.start()

    # ── Print schedule summary ───────────────────────────────────────────
    print("=" * 60)
    print("  SCHEDULER STARTED — All Jobs Registered")
    print("=" * 60)
    for func, job_id, interval_kw in jobs:
        interval_str = ", ".join(f"{v} {k}" for k, v in interval_kw.items())
        print(f"    {job_id:25s}  every {interval_str}")
    print("=" * 60)

    # ── Catch-up: run missed jobs immediately ─────────────────────────────
    state = _load_state()
    catchup_intervals = {
        "social_media": 12,
        "osrm_routing": 2,
        "social_volume": 0.5,
        "google_mobility": 24,
        "google_trends": 24,
        "wdzmi_composite": 1,
    }

    catchup_needed = []
    for job_name, interval_h in catchup_intervals.items():
        if _needs_catchup(state, job_name, interval_h):
            catchup_needed.append(job_name)

    if catchup_needed:
        print(f"\n  Catch-up needed for {len(catchup_needed)} job(s): {', '.join(catchup_needed)}")
        print(f"  Running catch-up jobs in background...\n")

        # Run catch-up jobs with small delays to avoid overwhelming
        for i, job_name in enumerate(catchup_needed):
            job_func = {
                "social_media": job_social_media,
                "osrm_routing": job_osrm_routing,
                "social_volume": job_social_volume,
                "google_mobility": job_google_mobility,
                "google_trends": job_google_trends,
                "wdzmi_composite": job_wdzmi_composite,
            }[job_name]
            scheduler.add_job(job_func, id=f"catchup_{job_name}", replace_existing=True)
    else:
        print(f"\n  All jobs up to date. No catch-up needed.")
        for job_name, interval_h in catchup_intervals.items():
            last = state.get(job_name, "never")
            print(f"    {job_name:25s}  last run: {last}")

    return scheduler