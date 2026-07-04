"""
osrm_routing_signal.py
======================
Signal 1 of 4 for W-DZMI (Weighted Dynamic Zone Mobility Index).

Fetches real-time travel times for 25 Dhaka corridors using the
free OSRM public demo server (OpenStreetMap routing, no API key).

Data flow:
    corridors.json -> OSRM API -> MongoDB (osrm_routing_data collection)

Usage:
    python -m data_collectors.osrm_routing_signal          # one-off fetch
    python -m data_collectors.osrm_routing_signal --loop   # continuous every 2 hrs
"""

import os
import sys
import time
import json
from datetime import datetime, timedelta

import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import db

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
OSRM_BASE_URL = "https://router.project-osrm.org/route/v1/driving"
REQUEST_DELAY = 3        # seconds between requests (be polite)
REQUEST_TIMEOUT = 15     # seconds before giving up on one request
COLLECTION_NAME = "osrm_routing_data"


def _load_config():
    """Load zones.json and corridors.json from data/ directory."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")

    with open(os.path.join(data_dir, "zones.json"), encoding="utf-8") as f:
        zones = json.load(f)

    with open(os.path.join(data_dir, "corridors.json"), encoding="utf-8") as f:
        corridors = json.load(f)

    return zones, corridors


def _fetch_route(origin_coords, destination_coords):
    """
    Query OSRM for one corridor. Returns dict with duration_sec, distance_m.
    Returns None on failure.
    """
    origin = f"{origin_coords[1]},{origin_coords[0]}"
    dest = f"{destination_coords[1]},{destination_coords[0]}"
    url = f"{OSRM_BASE_URL}/{origin};{dest}?overview=false"

    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == "Ok" and data.get("routes"):
                route = data["routes"][0]
                return {
                    "duration_sec": route["duration"],
                    "distance_m": route["distance"],
                }
        else:
            print(f"       OSRM returned status {resp.status_code}")
    except requests.exceptions.Timeout:
        print(f"       Timeout ({REQUEST_TIMEOUT}s)")
    except requests.exceptions.RequestException as e:
        print(f"       Request error: {e}")

    return None


def fetch_all_corridors():
    """
    Fetch travel times for ALL 25 corridors.
    Returns list of result dicts. Each has corridor info + travel data.
    """
    zones, corridors_config = _load_config()
    corridors = corridors_config["corridors"]
    collection = db[COLLECTION_NAME]

    now = datetime.utcnow()
    results = []
    success_count = 0
    fail_count = 0

    print(f"  Fetching travel times for {len(corridors)} corridors...")

    for i, cor in enumerate(corridors):
        print(f"  [{i+1:2d}/{len(corridors)}] {cor['id']}: {cor['name']}...", end=" ", flush=True)

        route_data = _fetch_route(cor["origin_coords"], cor["destination_coords"])

        if route_data is None:
            fail_count += 1
            print("FAILED")
            continue

        success_count += 1
        duration_min = round(route_data["duration_sec"] / 60, 2)
        distance_km = round(route_data["distance_m"] / 1000, 2)

        record = {
            "corridor_id": cor["id"],
            "corridor_name": cor["name"],
            "origin_zone": cor["origin_zone"],
            "destination_zone": cor["destination_zone"],
            "weight": cor["weight"],
            "type": cor["type"],
            "duration_sec": route_data["duration_sec"],
            "duration_min": duration_min,
            "distance_m": route_data["distance_m"],
            "distance_km": distance_km,
            "speed_kmh": round(distance_km / (duration_min / 60), 2) if duration_min > 0 else 0,
            "timestamp": now,
            "date": now.strftime("%Y-%m-%d"),
            "hour": now.hour,
            "weekday": now.strftime("%A"),
        }

        # Save to MongoDB
        collection.insert_one(record)
        results.append(record)
        print(f"{duration_min} min  ({distance_km} km)")

        # Be polite to OSRM
        if i < len(corridors) - 1:
            time.sleep(REQUEST_DELAY)

    print(f"\n  Done: {success_count} success, {fail_count} failed")
    return results


def get_latest_routing_data():
    """
    Get the most recent routing snapshot for all corridors.
    Returns dict: corridor_id -> record
    """
    collection = db[COLLECTION_NAME]

    # Get the latest timestamp in the collection
    latest = collection.find_one(sort=[("timestamp", -1)])
    if not latest:
        return {}

    latest_time = latest["timestamp"]
    # Get all records from the same fetch batch (within 10 min window)
    cutoff = latest_time - timedelta(minutes=10)
    docs = collection.find({"timestamp": {"$gte": cutoff}})

    return {doc["corridor_id"]: doc for doc in docs}


def get_zone_routing_score(zone_id):
    """
    Calculate a routing-based mobility score for a single zone.
    Score = weighted average of (100 - congestion_ratio) for corridors
    touching this zone. Higher score = more mobility (faster travel).
    Returns 0-100 score.
    """
    zones, corridors_config = _load_config()
    latest = get_latest_routing_data()

    if not latest:
        return None  # No data available yet

    zone = zones["zones"][str(zone_id)]
    zone_weight = zone["zone_weight"]

    weighted_speed_sum = 0
    total_weight = 0

    for cor in corridors_config["corridors"]:
        if cor["origin_zone"] != zone_id and cor["destination_zone"] != zone_id:
            continue

        data = latest.get(cor["id"])
        if not data:
            continue

        # Speed is our mobility proxy
        speed = data.get("speed_kmh", 0)
        if speed <= 0:
            continue

        # Normalize: assume free-flow speed ~30 km/h in Dhaka
        # Higher speed = less congestion = higher mobility
        normalized = min((speed / 30.0) * 100, 100)

        weighted_speed_sum += normalized * cor["weight"]
        total_weight += cor["weight"]

    if total_weight == 0:
        return None

    raw_score = (weighted_speed_sum / total_weight) * zone_weight
    return round(min(max(raw_score, 0), 100), 2)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print(f"  OSRM Routing Signal Collector")
    print(f"  Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 60)

    results = fetch_all_corridors()

    if results:
        print(f"\n  Records saved to MongoDB: {COLLECTION_NAME}")
        print(f"  Total corridors fetched: {len(results)}")

        avg_speed = sum(r["speed_kmh"] for r in results) / len(results)
        avg_time = sum(r["duration_min"] for r in results) / len(results)
        print(f"  Avg speed: {avg_speed:.1f} km/h")
        print(f"  Avg travel time: {avg_time:.1f} min")

    print("=" * 60)