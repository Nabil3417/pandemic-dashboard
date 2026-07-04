"""
social_volume_signal.py
=======================
Signal 2 of 4 for W-DZMI (Weighted Dynamic Zone Mobility Index).

Uses EXISTING social media posts in MongoDB to measure zone-level
digital activity as a mobility proxy. No new data collection needed —
this reads what Telegram, RSS, YouTube, Bluesky, and Mastodon
collectors already stored.

Logic:
    1. Count posts per zone for 3 time windows (24h, 7d, 30d)
    2. Compare current 24h count against 30-day daily average (baseline)
    3. Ratio > 1.0 means more activity than normal = higher mobility
    4. Scale to 0-100, apply zone weight

Usage:
    python -m data_collectors.social_volume_signal
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import social_posts, db

COLLECTION_NAME = "social_volume_data"

# Time windows for analysis
WINDOWS = {
    "24h": 1,
    "7d": 7,
    "30d": 30,
}


def _load_zones():
    """Load zone definitions from zones.json."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(base_dir, "data", "zones.json"), encoding="utf-8") as f:
        data = json.load(f)
    return data["zones"]


def count_posts_by_zone(hours=24):
    """
    Count social media posts per zone in the last N hours.
    Returns dict: {zone_id: count}
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)

    pipeline = [
        {"$match": {"timestamp": {"$gte": cutoff}}},
        {"$group": {"_id": "$zone_id", "count": {"$sum": 1}}},
    ]

    results = {}
    for doc in social_posts.aggregate(pipeline):
        zone_id = doc["_id"]
        if zone_id is not None:
            results[int(zone_id)] = doc["count"]

    return results


def compute_zone_scores():
    """
    Compute a 0-100 social volume mobility score for each zone.
    Returns dict: {zone_id: {score, trend, counts, ratio, confidence}}
    """
    zones = _load_zones()
    collection = db[COLLECTION_NAME]
    now = datetime.now(timezone.utc)

    # Count posts for 3 windows
    counts_24h = count_posts_by_zone(24)
    counts_7d = count_posts_by_zone(168)   # 7 days
    counts_30d = count_posts_by_zone(720)  # 30 days

    results = {}

    for zone_id_str, zone_info in zones.items():
        zone_id = int(zone_id_str)
        zone_weight = zone_info["zone_weight"]

        c24 = counts_24h.get(zone_id, 0)
        c7 = counts_7d.get(zone_id, 0)
        c30 = counts_30d.get(zone_id, 0)

        # Baseline = average daily posts over 30 days
        baseline_daily = c30 / 30.0 if c30 > 0 else 1.0

        # Current 24h vs baseline ratio
        ratio = c24 / baseline_daily if baseline_daily > 0 else 1.0

        # Scale to 0-100
        # ratio of 1.0 (normal) = score ~50
        # ratio of 2.0 (double activity) = score ~85
        # ratio of 0.5 (half activity) = score ~25
        if ratio > 0:
            raw_score = 50 + (25 * (ratio - 1.0) / 0.5)
        else:
            raw_score = 25

        # Apply zone weight (denser zones should score higher)
        weighted_score = raw_score * zone_weight
        score = round(min(max(weighted_score, 0), 100), 2)

        # Trend: compare this week vs previous week
        # Use 7d count: first 3.5 days vs last 3.5 days
        if c7 > 0:
            # Approximate: if 7d count is much higher than expected
            # from 30d average, trend is rising
            expected_7d = baseline_daily * 7
            week_ratio = c7 / expected_7d if expected_7d > 0 else 1.0
            if week_ratio > 1.3:
                trend = "rising"
            elif week_ratio < 0.7:
                trend = "falling"
            else:
                trend = "stable"
        else:
            trend = "stable"
            week_ratio = 1.0

        # Confidence: based on data volume
        # More posts = more reliable signal
        if c30 >= 100:
            confidence = 0.90
        elif c30 >= 30:
            confidence = 0.75
        elif c30 >= 10:
            confidence = 0.60
        else:
            confidence = 0.30

        record = {
            "zone_id": zone_id,
            "zone_name": zone_info["name"],
            "score": score,
            "trend": trend,
            "ratio": round(ratio, 3),
            "week_ratio": round(week_ratio, 3),
            "counts": {
                "24h": c24,
                "7d": c7,
                "30d": c30,
            },
            "baseline_daily": round(baseline_daily, 2),
            "confidence": confidence,
            "timestamp": now,
        }

        # Save to MongoDB (upsert by zone_id)
        collection.update_one(
            {"zone_id": zone_id},
            {"$set": record},
            upsert=True,
        )

        results[zone_id] = record

    return results


def get_social_volume_score(zone_id):
    """
    Get the latest social volume score for one zone.
    Returns dict or None.
    """
    collection = db[COLLECTION_NAME]
    doc = collection.find_one({"zone_id": zone_id}, sort=[("timestamp", -1)])
    if doc:
        doc.pop("_id", None)
        return doc
    return None


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
import json

if __name__ == "__main__":
    print("=" * 60)
    print("  Social Volume Signal Calculator")
    print(f"  Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 60)

    results = compute_zone_scores()

    print(f"\n  Social Volume Scores (sorted by score):\n")
    print(f"  {'Zone':<30} {'Score':>6} {'24h':>5} {'7d':>5} {'30d':>5} {'Ratio':>6} {'Trend':<8} {'Conf':>5}")
    print(f"  {'-'*78}")

    for zone_id in sorted(results, key=lambda z: results[z]["score"], reverse=True):
        r = results[zone_id]
        print(f"  {r['zone_name']:<30} {r['score']:>6.1f} {r['counts']['24h']:>5} {r['counts']['7d']:>5} {r['counts']['30d']:>5} {r['ratio']:>6.2f}x {r['trend']:<8} {r['confidence']:>5.0%}")

    print(f"\n  Records saved to MongoDB: {COLLECTION_NAME}")
    print("=" * 60)