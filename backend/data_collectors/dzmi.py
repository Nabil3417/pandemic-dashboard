import os
"""
W-DZMI: Weighted Dynamic Zone Mobility Index
=============================================
Fuses 4 mobility signals into a single 0-100 composite score per zone.

Formula:  W-DZMI = sum(weight_i * score_i)

Signal Weights:
  - Google Mobility  = 0.35
  - Social Volume    = 0.30
  - OSRM Routing     = 0.20
  - Google Trends    = 0.15
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from pymongo import MongoClient

# ── Config ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
ZONES_FILE = BASE_DIR / "data" / "zones.json"

SIGNAL_WEIGHTS = {
    "google_mobility": 0.35,
    "social_volume": 0.30,
    "osrm_routing": 0.20,
    "google_trends": 0.15,
}

MIN_SIGNALS = 1

MONGO_URI = os.getenv("MONGO_URI")


# ── MongoDB Connection ─────────────────────────────────────────────────────
def get_db():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    db = client["bioguard_research"]
    db.command("ping")
    return db, client


# ── Zone Loader ─────────────────────────────────────────────────────────────
def load_zones():
    """Load zone definitions from zones.json. Returns list of zone dicts."""
    with open(ZONES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # zones is a dict with integer keys -> convert to list of values
    zones_dict = data["zones"]
    return list(zones_dict.values())


# ── Signal Fetchers ─────────────────────────────────────────────────────────
def fetch_google_mobility(db):
    """
    Fetch latest Google Mobility score per zone.
    Collection fields: date, zone_id, avg_percent_change,
                       google_mobility_score, timestamp, zone_name
    No is_latest flag — get the document with the most recent date per zone.
    """
    coll = db["google_mobility_data"]
    result = {}

    # Get distinct zone_ids
    zone_ids = coll.distinct("zone_id")
    for zid in zone_ids:
        # Get the latest document for this zone by date
        latest = coll.find_one(
            {"zone_id": zid},
            sort=[("date", -1)]
        )
        if latest:
            score = latest.get("google_mobility_score", 0)
            pct_change = latest.get("avg_percent_change", 0)

            # Derive trend from percent change
            if pct_change > 5:
                trend = "rising"
            elif pct_change < -5:
                trend = "falling"
            else:
                trend = "stable"

            result[zid] = {
                "score": score,
                "confidence": 80,  # Google Mobility is a strong signal
                "trend": trend,
                "timestamp": latest.get("timestamp"),
            }

    return result


def fetch_social_volume(db):
    """
    Fetch latest Social Volume score per zone.
    Collection fields: zone_id, score, confidence (0-1 float),
                       trend, timestamp, zone_name
    """
    coll = db["social_volume_data"]
    docs = list(coll.find({}, {"_id": 0}))
    result = {}
    for d in docs:
        conf = d.get("confidence", 0.3)
        # Convert 0-1 float to 0-100 percentage
        if conf <= 1.0:
            conf = round(conf * 100, 1)
        result[d["zone_id"]] = {
            "score": d.get("score", 0),
            "confidence": conf,
            "trend": d.get("trend", "unknown"),
            "timestamp": d.get("timestamp"),
        }
    return result


def fetch_osrm_routing(db):
    """
    Fetch OSRM Routing data and aggregate to zone level.
    Collection fields: corridor_id, origin_zone, destination_zone,
                       weight, speed_kmh, duration_min, distance_km, timestamp
    No pre-computed mobility_score — calculate from speed_kmh.
    """
    coll = db["osrm_routing_data"]
    corridors = list(coll.find({}, {"_id": 0}))

    # Build zone -> list of corridor data
    zone_data = {}
    for c in corridors:
        score = _routing_mobility_score(c.get("speed_kmh", 0), c.get("weight", 1.0))
        for zid in [c.get("origin_zone"), c.get("destination_zone")]:
            if zid is None:
                continue
            if zid not in zone_data:
                zone_data[zid] = {"scores": []}
            zone_data[zid]["scores"].append(score)

    # Aggregate: average score per zone
    result = {}
    for zid, data in zone_data.items():
        avg_score = round(sum(data["scores"]) / len(data["scores"]), 1)
        result[zid] = {
            "score": avg_score,
            "confidence": 70,  # OSRM is real-time but corridor-level proxy
            "trend": "stable",  # Single snapshot, no historical comparison
            "timestamp": corridors[0].get("timestamp") if corridors else None,
        }

    return result


def _routing_mobility_score(speed_kmh, corridor_weight):
    """
    Convert speed to a 0-100 mobility score.
    Higher speed = more mobility (less congestion).
    Baseline: 30 km/h free-flow in Dhaka.
    """
    if speed_kmh <= 0:
        return 0
    # Speed ratio against 30 km/h baseline
    ratio = speed_kmh / 30.0
    # Scale: ratio 0->0, ratio 1->50, ratio 2->100
    score = min(100, max(0, ratio * 50))
    # Apply corridor weight
    score = score * corridor_weight
    return round(min(100, max(0, score)), 1)


def fetch_google_trends(db):
    """
    Fetch latest Google Trends signal per zone.
    Collection fields: zone_id, score, confidence (0-1 float),
                       trend, timestamp, zone_name
    """
    coll = db["google_trends_signal"]
    docs = list(coll.find({}, {"_id": 0}))
    result = {}
    for d in docs:
        conf = d.get("confidence", 0.5)
        # Convert 0-1 float to 0-100 percentage
        if conf <= 1.0:
            conf = round(conf * 100, 1)
        result[d["zone_id"]] = {
            "score": d.get("score", 0),
            "confidence": conf,
            "trend": d.get("trend", "unknown"),
            "timestamp": d.get("timestamp"),
        }
    return result


# ── Composite Calculator ───────────────────────────────────────────────────
def calculate_wdzmi(db, zones):
    """Calculate W-DZMI for all zones. Returns list sorted by score desc."""
    print("\n  Fetching signals from MongoDB...")

    signals = {
        "google_mobility": fetch_google_mobility(db),
        "social_volume": fetch_social_volume(db),
        "osrm_routing": fetch_osrm_routing(db),
        "google_trends": fetch_google_trends(db),
    }

    for sig_name, sig_data in signals.items():
        count = len(sig_data)
        w = SIGNAL_WEIGHTS[sig_name]
        print(f"    {sig_name:20s}: {count:2d} zones covered (weight={w:.2f})")

    print()
    results = []
    now = datetime.now(timezone.utc)

    for zone in zones:
        zid = zone["id"]
        zname = zone["name"]
        zname_bn = zone.get("name_bn", "")
        zone_weight = zone.get("zone_weight", 1.0)

        # Collect available signals for this zone
        available = {}
        for sig_name, sig_data in signals.items():
            if zid in sig_data:
                available[sig_name] = sig_data[zid]

        num_available = len(available)

        if num_available < MIN_SIGNALS:
            print(f"    Zone {zid:2d} ({zname:30s}): SKIPPED - only {num_available} signal(s)")
            continue

        # Redistribute weights if some signals missing
        if num_available < len(SIGNAL_WEIGHTS):
            total_w = sum(SIGNAL_WEIGHTS[s] for s in available)
            effective_weights = {s: SIGNAL_WEIGHTS[s] / total_w for s in available}
        else:
            effective_weights = dict(SIGNAL_WEIGHTS)

        # Compute weighted composite
        composite_score = 0.0
        weighted_confidence = 0.0
        signal_breakdown = {}

        for sig_name, sig_info in available.items():
            w = effective_weights[sig_name]
            s = sig_info["score"]
            c = sig_info["confidence"]
            composite_score += w * s
            weighted_confidence += w * c
            signal_breakdown[sig_name] = {
                "score": s,
                "weight": round(w, 4),
                "contribution": round(w * s, 2),
                "confidence": c,
                "trend": sig_info["trend"],
            }

        composite_score = max(0.0, min(100.0, round(composite_score, 1)))
        weighted_confidence = round(weighted_confidence, 1)

        # Dominant trend by weighted vote
        trend_votes = {}
        for sig_name in available:
            t = available[sig_name]["trend"]
            w = effective_weights[sig_name]
            trend_votes[t] = trend_votes.get(t, 0) + w
        dominant_trend = max(trend_votes, key=trend_votes.get)

        result = {
            "zone_id": zid,
            "zone_name": zname,
            "zone_name_bn": zname_bn,
            "zone_weight": zone_weight,
            "wdzmi_score": composite_score,
            "confidence": weighted_confidence,
            "trend": dominant_trend,
            "num_signals": num_available,
            "signals_used": list(available.keys()),
            "signal_breakdown": signal_breakdown,
            "risk_level": _classify_risk(composite_score),
            "timestamp": now,
            "calculated_at": now.isoformat(),
        }
        results.append(result)

        signals_str = ", ".join(
            f"{s[:4]}={signal_breakdown[s]['contribution']:.1f}" for s in available
        )
        print(
            f"    Zone {zid:2d} ({zname:30s}): "
            f"W-DZMI={composite_score:5.1f}  "
            f"Conf={weighted_confidence:4.1f}%  "
            f"Trend={dominant_trend:7s}  "
            f"Signals={num_available}  "
            f"[{signals_str}]"
        )

    results.sort(key=lambda x: x["wdzmi_score"], reverse=True)
    return results


def _classify_risk(score):
    if score >= 75:
        return "critical"
    elif score >= 55:
        return "high"
    elif score >= 35:
        return "moderate"
    elif score >= 20:
        return "low"
    else:
        return "minimal"


# ── MongoDB Storage ─────────────────────────────────────────────────────────
def save_wdzmi(db, results):
    coll_latest = db["wdzmi_results"]
    coll_history = db["wdzmi_history"]
    now = datetime.now(timezone.utc)
    upserted = 0
    history_count = 0

    for r in results:
        zid = r["zone_id"]
        coll_latest.update_one(
            {"zone_id": zid},
            {"$set": {**r, "last_updated": now}},
            upsert=True,
        )
        upserted += 1

        coll_history.insert_one({
            "zone_id": zid,
            "zone_name": r["zone_name"],
            "wdzmi_score": r["wdzmi_score"],
            "confidence": r["confidence"],
            "trend": r["trend"],
            "risk_level": r["risk_level"],
            "num_signals": r["num_signals"],
            "signal_breakdown": r["signal_breakdown"],
            "timestamp": now,
        })
        history_count += 1

    return upserted, history_count


# ── Query Helpers ───────────────────────────────────────────────────────────
def get_latest_wdzmi(db):
    coll = db["wdzmi_results"]
    return list(coll.find({}, {"_id": 0}).sort("wdzmi_score", -1))


def get_zone_wdzmi(db, zone_id):
    coll = db["wdzmi_results"]
    return coll.find_one({"zone_id": zone_id}, {"_id": 0})


def get_wdzmi_history(db, zone_id, limit=30):
    coll = db["wdzmi_history"]
    docs = list(
        coll.find({"zone_id": zone_id}, {"_id": 0})
        .sort("timestamp", -1)
        .limit(limit)
    )
    docs.reverse()
    return docs


def get_risk_summary(db):
    docs = get_latest_wdzmi(db)
    summary = {"critical": 0, "high": 0, "moderate": 0, "low": 0, "minimal": 0}
    for d in docs:
        level = d.get("risk_level", "minimal")
        if level in summary:
            summary[level] += 1
    return summary


# ── Main ────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  W-DZMI: Weighted Dynamic Zone Mobility Index Calculator")
    print(f"  Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 60)
    print(f"  Signal Weights:")
    for sig, w in SIGNAL_WEIGHTS.items():
        print(f"    {sig:20s} = {w:.2f}")
    print(f"  Minimum signals required: {MIN_SIGNALS}")
    print("=" * 60)

    zones = load_zones()
    print(f"  Loaded {len(zones)} zones from zones.json")

    db, client = get_db()
    print("  Connected to MongoDB Atlas!")

    print("\n  Calculating W-DZMI for each zone...")
    print("  " + "-" * 55)
    results = calculate_wdzmi(db, zones)

    if not results:
        print("\n  WARNING: No zones could be scored. Check signal data.")
        client.close()
        return

    # Ranking table
    print("\n  " + "=" * 80)
    print("  W-DZMI RANKING")
    print("  " + "=" * 80)
    print(f"  {'Rank':>4s}  {'Zone':<32s} {'W-DZMI':>7s}  {'Conf':>5s}  {'Risk':<10s}  {'Signals':>7s}  {'Trend':>7s}")
    print("  " + "-" * 80)

    for i, r in enumerate(results, 1):
        rm = _risk_marker(r["risk_level"])
        print(
            f"  {i:4d}  {r['zone_name']:<32s} {r['wdzmi_score']:7.1f}  "
            f"{r['confidence']:4.1f}%  {rm:<10s}  "
            f"{r['num_signals']:3d}/4      {r['trend']:>7s}"
        )

    print("  " + "=" * 80)

    # Risk summary
    summary = get_risk_summary(db)
    print(f"\n  Risk Distribution: ", end="")
    parts = [f"{level}={count}" for level, count in summary.items() if count > 0]
    print(" | ".join(parts))

    # Save
    print("\n  Saving to MongoDB...")
    upserted, history_count = save_wdzmi(db, results)
    print(f"    Upserted {upserted} latest records -> wdzmi_results")
    print(f"    Appended {history_count} history records -> wdzmi_history")

    # Global summary
    db["wdzmi_summary"].update_one(
        {"type": "latest"},
        {"$set": {
            "type": "latest",
            "total_zones": len(results),
            "avg_score": round(sum(r["wdzmi_score"] for r in results) / len(results), 1),
            "max_score": results[0]["wdzmi_score"],
            "min_score": results[-1]["wdzmi_score"],
            "risk_distribution": summary,
            "signal_weights": SIGNAL_WEIGHTS,
            "timestamp": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    print(f"    Updated summary -> wdzmi_summary")

    client.close()
    print("\n  Done! W-DZMI calculation complete.")
    print("=" * 60)


def _risk_marker(level):
    markers = {
        "critical": "[!!! CRIT]",
        "high":     "[!! HIGH]",
        "moderate": "[!  MOD ]",
        "low":      "[   LOW ]",
        "minimal":  "[  MINIM]",
    }
    return markers.get(level, "[ UNKNOWN]")


if __name__ == "__main__":
    main()