"""
social_media_manager.py — Runs ALL collectors in sequence.

Usage:
    python -m data_collectors.social_media_manager

    # Or from Python:
    from data_collectors.social_media_manager import run_all_collectors
    run_all_collectors()
"""

import sys
import os
import time
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_all_collectors(days_back=90):
    """
    Run every collector in sequence, print a final summary.
    """
    print("=" * 60)
    print(f"  BioGuard AI — Unified Social Media Collection")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Lookback: {days_back} days")
    print("=" * 60)

    results = {}

    # ── 1. Telegram ────────────────────────────────────────────
    try:
        from data_collectors.telegram_collector import collect_telegram_data
        t0 = time.time()
        count = collect_telegram_data(days_back=days_back)
        results["Telegram"] = {"count": count, "time": round(time.time() - t0, 1)}
    except Exception as e:
        print(f"❌ Telegram collector failed: {e}")
        results["Telegram"] = {"count": 0, "error": str(e)}

    # ── 2. RSS News ───────────────────────────────────────────
    try:
        from data_collectors.rss_news_collector import collect_rss_data
        t0 = time.time()
        count = collect_rss_data(days_back=days_back)
        results["RSS_NEWS"] = {"count": count, "time": round(time.time() - t0, 1)}
    except Exception as e:
        print(f"❌ RSS collector failed: {e}")
        results["RSS_NEWS"] = {"count": 0, "error": str(e)}

    # ── 3. YouTube ────────────────────────────────────────────
    try:
        from data_collectors.youtube_collector import collect_youtube_data
        t0 = time.time()
        count = collect_youtube_data(days_back=days_back)
        results["YouTube"] = {"count": count, "time": round(time.time() - t0, 1)}
    except Exception as e:
        print(f"❌ YouTube collector failed: {e}")
        results["YouTube"] = {"count": 0, "error": str(e)}

    # ── 4. Bluesky ────────────────────────────────────────────
    try:
        from data_collectors.bluesky_collector import collect_bluesky_data
        t0 = time.time()
        count = collect_bluesky_data(days_back=days_back)
        results["Bluesky"] = {"count": count, "time": round(time.time() - t0, 1)}
    except Exception as e:
        print(f"❌ Bluesky collector failed: {e}")
        results["Bluesky"] = {"count": 0, "error": str(e)}

    # ── 5. Mastodon ───────────────────────────────────────────
    try:
        from data_collectors.mastodon_collector import collect_mastodon_data
        t0 = time.time()
        count = collect_mastodon_data(days_back=days_back)
        results["Mastodon"] = {"count": count, "time": round(time.time() - t0, 1)}
    except Exception as e:
        print(f"❌ Mastodon collector failed: {e}")
        results["Mastodon"] = {"count": 0, "error": str(e)}

    # ── SUMMARY ───────────────────────────────────────────────
    total_new = sum(r["count"] for r in results.values())
    print(f"\n{'='*60}")
    print(f"  FINAL SUMMARY — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    for name, r in results.items():
        status = "✅" if r.get("count", 0) > 0 else "⚠️"
        if "error" in r:
            status = "❌"
            print(f"  {status} {name:12s}  ERROR: {r['error']}")
        else:
            t = r.get("time", "?")
            print(f"  {status} {name:12s}  {r['count']:>5} new posts  ({t}s)")

    print(f"  {'─'*45}")
    print(f"  📊 TOTAL NEW POSTS: {total_new}")
    print(f"{'='*60}")

    return results


if __name__ == "__main__":
    run_all_collectors(days_back=90)