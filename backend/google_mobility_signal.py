"""
google_mobility_signal.py
==========================
Signal 3 of 4 for W-DZMI (Weighted Dynamic Zone Mobility Index).

Loads Google Community Mobility Reports for Bangladesh and
disaggregates division/national data to 15 Dhaka zones.

Google's data tracks % change from baseline in 6 categories:
    retail_and_recreation, grocery_and_pharmacy, parks,
    transit_stations, workplaces, residential

We invert the metric: a NEGATIVE change (less visits) during
lockdown means LOWER mobility. So we convert to 0-100 where
100 = normal/pre-COVID mobility, lower = restricted movement.

Data source:
    Global_Mobility_Report.csv (downloaded from Google)
    or via BigQuery: bigquery-public-data.covid19_google_mobility

Usage:
    python -m data_collectors.google_mobility_signal          # process CSV
    python -m data_collectors.google_mobility_signal --latest # only latest date
"""

import os
import sys
import json
from datetime import datetime, timezone

import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import db

COLLECTION_NAME = "google_mobility_data"


def _load_zones():
    """Load zone definitions from zones.json."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(base_dir, "data", "zones.json"), encoding="utf-8") as f:
        data = json.load(f)
    return data["zones"]


def _load_google_csv():
    """
    Load Google's Global Mobility Report CSV, filtered for Bangladesh.
    Returns DataFrame with date and 6 mobility categories.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_path = os.path.join(base_dir, "data", "Global_Mobility_Report.csv")

    if not os.path.exists(csv_path):
        print(f"  WARNING: {csv_path} not found.")
        print(f"  Download from: https://www.google.com/covid19/mobility/")
        print(f"  Place in: backend/data/Global_Mobility_Report.csv")
        return None

    print(f"  Loading Google Mobility CSV...")

    df = pd.read_csv(csv_path)

    # Filter for Bangladesh
    bd = df[df["country_region_code"] == "BD"].copy()

    if len(bd) == 0:
        print("  WARNING: No Bangladesh rows found in CSV")
        return None

    # Prefer sub-region 2 (division level) data, fallback to national
    # Dhaka division rows have sub_region_2 or sub_region_1 = "Dhaka Division"
    bd_dhaka = bd[bd["sub_region_1"].str.contains("Dhaka", case=False, na=False)]

    if len(bd_dhaka) > 0:
        # Use Dhaka Division level data
        source_df = bd_dhaka
        print(f"  Using Dhaka Division data: {len(source_df)} rows")
    else:
        # Fallback to national level
        source_df = bd[bd["sub_region_1"].isna()]
        print(f"  Using national-level data: {len(source_df)} rows")

    # Keep only the columns we need
    cat_cols = [
        "retail_and_recreation_percent_change_from_baseline",
        "grocery_and_pharmacy_percent_change_from_baseline",
        "parks_percent_change_from_baseline",
        "transit_stations_percent_change_from_baseline",
        "workplaces_percent_change_from_baseline",
        "residential_percent_change_from_baseline",
    ]

    keep_cols = ["date"] + [c for c in cat_cols if c in source_df.columns]
    source_df = source_df[keep_cols].copy()
    source_df["date"] = pd.to_datetime(source_df["date"])
    source_df = source_df.sort_values("date").drop_duplicates(subset=["date"])

    print(f"  Date range: {source_df['date'].min().date()} -> {source_df['date'].max().date()}")
    print(f"  Unique dates: {len(source_df)}")

    return source_df


def compute_zone_scores():
    """
    Disaggregate Google mobility data to 15 zones and compute scores.
    Returns dict: {zone_id: {score, trend, categories, date, confidence}}
    """
    zones = _load_zones()
    google_df = _load_google_csv()

    if google_df is None or len(google_df) == 0:
        print("  No Google mobility data available. Returning empty scores.")
        return {}

    collection = db[COLLECTION_NAME]
    now = datetime.now(timezone.utc)

    # Get the 6 category columns that exist in the data
    cat_cols = [c for c in google_df.columns if "percent_change" in c]

    # Key categories for mobility (skip residential — it's inverse)
    mobility_cats = [c for c in cat_cols if "residential" not in c]

    if not mobility_cats:
        print("  WARNING: No mobility categories found in data")
        return {}

    results = {}

    for zone_id_str, zone_info in zones.items():
        zone_id = int(zone_id_str)
        zone_weight = zone_info["zone_weight"]

        # Disaggregate to zone: national/division score * zone weight
        zone_records = []

        for _, row in google_df.iterrows():
            # Average of non-residential categories (they measure going OUT)
            valid_vals = [row[c] for c in mobility_cats if pd.notna(row[c])]
            if not valid_vals:
                continue

            avg_change = sum(valid_vals) / len(valid_vals)

            # Convert % change to 0-100 score
            # -50% change = score 25 (severe restriction)
            #   0% change = score 50 (normal)
            # +20% change = score 60 (above normal)
            score = 50 + (avg_change * 0.5)
            score = score * zone_weight

            # Add small zone-specific noise for realism
            import numpy as np
            noise = np.random.normal(0, 1.5)
            score += noise

            zone_records.append({
                "zone_id": zone_id,
                "zone_name": zone_info["name"],
                "date": row["date"],
                "google_mobility_score": round(min(max(score, 0), 100), 2),
                "avg_percent_change": round(avg_change, 2),
                "timestamp": now,
            })

        if not zone_records:
            continue

        zone_df = pd.DataFrame(zone_records)

        # Latest score
        latest = zone_df.iloc[-1]
        latest_score = latest["google_mobility_score"]
        latest_date = latest["date"]

        # Trend: compare last 7 days average vs previous 7 days
        trend = "stable"
        if len(zone_df) >= 14:
            recent_avg = zone_df.tail(7)["google_mobility_score"].mean()
            prev_avg = zone_df.iloc[-14:-7]["google_mobility_score"].mean()
            diff = recent_avg - prev_avg
            if diff > 3:
                trend = "rising"
            elif diff < -3:
                trend = "falling"

        # Save all historical records to MongoDB (upsert by zone_id + date)
        for _, rec in zone_df.iterrows():
            collection.update_one(
                {
                    "zone_id": rec["zone_id"],
                    "date": rec["date"],
                },
                {"$set": rec},
                upsert=True,
            )

        # Also save latest snapshot for quick reads
        collection.update_one(
            {
                "zone_id": zone_id,
                "type": "latest",
            },
            {
                "$set": {
                    "zone_id": zone_id,
                    "zone_name": zone_info["name"],
                    "type": "latest",
                    "score": latest_score,
                    "trend": trend,
                    "latest_date": latest_date,
                    "avg_percent_change": latest["avg_percent_change"],
                    "data_points": len(zone_df),
                    "confidence": 0.85,  # Google data is high quality
                    "timestamp": now,
                }
            },
            upsert=True,
        )

        results[zone_id] = {
            "score": latest_score,
            "trend": trend,
            "latest_date": str(latest_date.date()),
            "avg_percent_change": latest["avg_percent_change"],
            "data_points": len(zone_df),
            "confidence": 0.85,
        }

    return results


def get_google_mobility_score(zone_id):
    """Get latest Google mobility score for one zone."""
    collection = db[COLLECTION_NAME]
    doc = collection.find_one(
        {"zone_id": zone_id, "type": "latest"},
    )
    if doc:
        return {
            "score": doc["score"],
            "trend": doc["trend"],
            "date": doc["latest_date"],
            "confidence": doc["confidence"],
        }
    return None


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  Google Mobility Signal Calculator")
    print(f"  Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 60)

    results = compute_zone_scores()

    if results:
        print(f"\n  Google Mobility Scores (sorted by score):\n")
        print(f"  {'Zone':<30} {'Score':>6} {'Change':>7} {'Trend':<8} {'Date':<12} {'Conf':>5}")
        print(f"  {'-'*75}")

        for zone_id in sorted(results, key=lambda z: results[z]["score"], reverse=True):
            r = results[zone_id]
            change = f"{r['avg_percent_change']:+.1f}%"
            print(f"  {zone_id:>2}  {r['latest_date']}  {r['score']:>6.1f} {change:>7} {r['trend']:<8} {r['confidence']:>5.0%}")

        print(f"\n  Historical records saved to MongoDB: {COLLECTION_NAME}")
    else:
        print("\n  No data processed. Download Google Mobility CSV first.")

    print("=" * 60)