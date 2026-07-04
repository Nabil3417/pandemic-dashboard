"""
google_trends_signal.py
========================
Signal 4 of 4 for W-DZMI (Weighted Dynamic Zone Mobility Index).

Reads EXISTING Google Trends symptom search data from MongoDB
(trends_data collection, populated by google_trends_collector.py)
and converts it to a mobility-relevant 0-100 score.

Logic:
    High symptom search volume = high population digital activity
    = proxy for zone-level human activity and mobility awareness.

    We DON'T use the symptom meaning — we use the VOLUME as an
    activity signal. More searches = more people are active online
    in that zone's demographic.

Usage:
    python -m data_collectors.google_trends_signal
"""

import os
import sys
import json
from datetime import datetime, timezone, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import db

COLLECTION_NAME = "google_trends_signal"


def _load_zones():
    """Load zone definitions from zones.json."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(base_dir, "data", "zones.json"), encoding="utf-8") as f:
        data = json.load(f)
    return data["zones"]


def compute_zone_scores():
    """
    Read trends_data from MongoDB, compute 0-100 scores per zone.
    Returns dict: {zone_id: {score, trend, latest_value, confidence}}
    """
    zones = _load_zones()
    trends_coll = db["trends_data"]
    output_coll = db[COLLECTION_NAME]
    now = datetime.now(timezone.utc)

    results = {}

    for zone_id_str, zone_info in zones.items():
        zone_id = int(zone_id_str)
        zone_weight = zone_info["zone_weight"]

        # Get all trend records for this zone, sorted by date
        trend_docs = list(
            trends_coll.find({"zone_id": zone_id}).sort("date", 1)
        )

        if not trend_docs:
            results[zone_id] = {
                "score": None,
                "trend": "no_data",
                "confidence": 0.0,
            }
            continue

        # Extract symptom_score values
        scores = [doc.get("symptom_score", 0) for doc in trend_docs]
        dates = [doc.get("date") for doc in trend_docs]

        latest_score = scores[-1] if scores else 0

        # Normalize to 0-100 (Google Trends is already 0-100)
        # Apply zone weight
        weighted_score = latest_score * zone_weight
        final_score = round(min(max(weighted_score, 0), 100), 2)

        # Trend: compare recent vs previous
        trend = "stable"
        if len(scores) >= 8:
            recent_avg = sum(scores[-4:]) / 4
            prev_avg = sum(scores[-8:-4]) / 4
            diff = recent_avg - prev_avg
            if diff > 5:
                trend = "rising"
            elif diff < -5:
                trend = "falling"

        # Confidence based on data volume
        n_points = len(scores)
        if n_points >= 50:
            confidence = 0.85
        elif n_points >= 20:
            confidence = 0.70
        elif n_points >= 5:
            confidence = 0.50
        else:
            confidence = 0.25

        record = {
            "zone_id": zone_id,
            "zone_name": zone_info["name"],
            "score": final_score,
            "raw_symptom_score": latest_score,
            "trend": trend,
            "data_points": n_points,
            "date_range": {
                "start": str(dates[0]) if dates else None,
                "end": str(dates[-1]) if dates else None,
            },
            "confidence": confidence,
            "timestamp": now,
        }

        # Save to MongoDB (upsert)
        output_coll.update_one(
            {"zone_id": zone_id},
            {"$set": record},
            upsert=True,
        )

        results[zone_id] = record

    return results


def get_trends_score(zone_id):
    """Get latest Google Trends signal score for one zone."""
    collection = db[COLLECTION_NAME]
    doc = collection.find_one({"zone_id": zone_id})
    if doc:
        return {
            "score": doc.get("score"),
            "trend": doc.get("trend"),
            "confidence": doc.get("confidence", 0),
            "raw_symptom_score": doc.get("raw_symptom_score"),
        }
    return None


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  Google Trends Signal Calculator")
    print(f"  Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 60)

    results = compute_zone_scores()

    # Separate zones with data vs without
    has_data = {k: v for k, v in results.items() if v.get("score") is not None}
    no_data = {k: v for k, v in results.items() if v.get("score") is None}

    if has_data:
        print(f"\n  Zones with Google Trends data ({len(has_data)}):\n")
        print(f"  {'Zone':<30} {'Score':>6} {'Raw':>6} {'Trend':<8} {'Points':>6} {'Conf':>5}")
        print(f"  {'-'*70}")

        for zone_id in sorted(has_data, key=lambda z: has_data[z]["score"] or 0, reverse=True):
            r = has_data[zone_id]
            raw = r.get("raw_symptom_score", 0)
            print(f"  {r['zone_name']:<30} {r['score']:>6.1f} {raw:>6.1f} {r['trend']:<8} {r['data_points']:>6} {r['confidence']:>5.0%}")

    if no_data:
        print(f"\n  Zones without Google Trends data ({len(no_data)}):")
        for zone_id in no_data:
            r = no_data[zone_id]
            print(f"    Zone {zone_id}: {r['zone_name']}")

    print(f"\n  Records saved to MongoDB: {COLLECTION_NAME}")
    print("=" * 60)