"""
BioGuard AI — Google Trends Symptom-Search Collector
=====================================================
REPLACES the synthetic wastewater generator with a REAL data source.

Why Google Trends as a wastewater proxy:
  Bangladesh has no public wastewater-surveillance API (the real one —
  icddr,b / UVA / IEDCR sewage program — publishes weekly aggregate
  results but not a bulk-downloadable raw dataset). Google Trends search
  volume for symptom terms is a well-established, peer-reviewed proxy
  for population-level illness burden ("Google Flu Trends" and many
  successors), it is 100% real user behavior data, and it is free and
  immediately available via the public Google Trends API.

  Reference:
    Ginsberg, J., et al. Detecting influenza epidemics using search
    engine query data. Nature, 2009.
    Mavragani, A. & Ochoa, G. Google Trends in Infodemiology and
    Infoveillance: Methodology Framework. JMIR Public Health Surveill, 2019.

What this script does:
  1. Queries Google Trends for a set of Bangla + English symptom/illness
     search terms, geo-restricted to Bangladesh (geo='BD').
  2. Uses an "anchor term" technique to make separate 5-term batches
     comparable (Google Trends normalizes each request to its own
     0-100 scale, so raw scores across batches aren't directly
     comparable without a shared reference term).
  3. Pulls interest_by_region to get relative search intensity across
     Bangladesh's 8 administrative divisions — used to confirm Dhaka's
     share of national symptom-search volume.
  4. Disaggregates the national/Dhaka-division weekly signal down to
     the 15 BioGuard zones using the SAME zone-weight table already
     used for mobility disaggregation in engine_mobility.py
     (_get_zone_weights). This keeps the methodology consistent and
     documented — Google Trends does not report at ward/neighborhood
     resolution, so zone-level values are a disaggregation, not a
     direct measurement. This limitation should be stated explicitly
     in the research write-up.
  5. Saves results to MongoDB (`trends_data` collection) AND to a local
     CSV cache (`data/dhaka_zone_symptom_trends.csv`) so the system can
     run offline / avoid Google Trends rate limits on every restart,
     mirroring the existing dhaka_zone_mobility_2020_2022.csv pattern.

Usage:
    cd backend/
    python -m data_collectors.google_trends_collector          # incremental (recent weeks)
    python -m data_collectors.google_trends_collector --backfill  # full 2020-2022 history

Rate limits:
  Google Trends (via pytrends) has no official API key but does rate
  limit aggressively. This script sleeps between requests and retries
  with exponential backoff on 429s. Expect a full backfill to take
  several minutes.
"""

import os
import sys
import time
import random
import argparse
from datetime import datetime

import numpy as np
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from pytrends.request import TrendReq
except ImportError:
    print("❌ pytrends not installed. Run: pip install pytrends")
    sys.exit(1)

from database import (
    save_trends_snapshot,
    zones_collection,
)

# ─────────────────────────────────────────────────────────────
# ZONE DEFINITIONS — must mirror engine_mobility.py / app.py
# ─────────────────────────────────────────────────────────────
ZONE_NAMES = {
    1:  "Uttara",
    2:  "Mirpur",
    3:  "Gulshan & Banani",
    4:  "Agargaon & Kafrul",
    5:  "Farmgate & Karwan Bazar",
    6:  "Diabari & Ashkona",
    7:  "Uttarkhan & Faidabad",
    8:  "Dakshinkhan & Dumni",
    9:  "Vatara & Kuril",
    10: "Badda & Aftabnagar",
    11: "Ramna & Motijheel",
    12: "Khilgaon & Mugda",
    13: "Dhanmondi & Azimpur",
    14: "Wari & Jatrabari",
    15: "Bashundhara R/A (NSU)",
}

# Same weights used in engine_mobility.py's _get_zone_weights().
# Kept identical on purpose — both mobility and symptom-search signals
# are disaggregated from a city/national value using the same
# density/activity-based proxy for zone population weight.
ZONE_WEIGHTS = {
    1:  0.65, 2:  0.80, 3:  0.70, 4:  0.55, 5:  0.90,
    6:  0.35, 7:  0.30, 8:  0.32, 9:  0.60, 10: 0.58,
    11: 0.95, 12: 0.75, 13: 0.78, 14: 0.88, 15: 1.10,
}

# ─────────────────────────────────────────────────────────────
# SEARCH TERMS
# ─────────────────────────────────────────────────────────────
# Batches of <=4 real terms + 1 shared anchor term (5 max per
# pytrends payload). "fever" is used as the anchor since it appears
# in every batch and lets us rescale batches onto one common index.
ANCHOR_TERM = "fever"

SEARCH_BATCHES = [
    [ANCHOR_TERM, "dengue symptoms", "flu treatment", "covid symptoms", "cough remedy"],
    [ANCHOR_TERM, "hospital admission", "doctor appointment", "diarrhea treatment", "vaccine"],
    [ANCHOR_TERM, "জ্বর", "ডেঙ্গু", "কাশি", "হাসপাতাল"],   # Bangla batch
]

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _pytrends_client():
    return TrendReq(hl='en-US', tz=360, timeout=(10, 30), retries=3, backoff_factor=0.5)


def _fetch_batch_with_retry(pytrends, kw_list, timeframe, geo, max_retries=5):
    """Fetches one batch, retrying with exponential backoff on 429s."""
    for attempt in range(max_retries):
        try:
            pytrends.build_payload(kw_list, timeframe=timeframe, geo=geo)
            df = pytrends.interest_over_time()
            return df
        except Exception as e:
            wait = (2 ** attempt) + random.uniform(0, 2)
            print(f"   ⚠️  Batch failed ({e}). Retrying in {wait:.1f}s "
                  f"(attempt {attempt + 1}/{max_retries})...")
            time.sleep(wait)
    print(f"   ❌ Batch permanently failed after {max_retries} retries: {kw_list}")
    return None


def fetch_national_symptom_index(timeframe="today 12-m", geo="BD"):
    """
    PRIMARY METHOD.
    Fetches all search-term batches, rescales them onto a common index
    using the shared anchor term, and returns one combined weekly
    'symptom search intensity' series for Bangladesh (0-100 scale,
    real Google Trends data).
    """
    pytrends = _pytrends_client()
    all_series = []
    anchor_means = []

    for i, batch in enumerate(SEARCH_BATCHES):
        print(f"📡 Fetching batch {i+1}/{len(SEARCH_BATCHES)}: {batch}")
        df = _fetch_batch_with_retry(pytrends, batch, timeframe, geo)
        time.sleep(2 + random.uniform(0, 2))  # be polite between requests

        if df is None or df.empty:
            continue

        if 'isPartial' in df.columns:
            df = df.drop(columns=['isPartial'])

        anchor_mean = df[ANCHOR_TERM].mean()
        if anchor_mean <= 0:
            anchor_mean = 1.0  # avoid div-by-zero
        anchor_means.append(anchor_mean)

        # Rescale every non-anchor term in this batch relative to the
        # anchor term's mean, so all batches land on a comparable scale.
        rescaled = df.drop(columns=[ANCHOR_TERM]).div(anchor_mean)
        all_series.append(rescaled)

    if not all_series:
        print("   ❌ No batches succeeded — check network / rate limits.")
        return None

    combined = pd.concat(all_series, axis=1)
    # Composite weekly index = mean of all rescaled symptom terms,
    # then renormalized back to a 0-100-ish scale using the average
    # anchor magnitude across batches.
    composite = combined.mean(axis=1) * np.mean(anchor_means)
    composite = (composite / composite.max()) * 100 if composite.max() > 0 else composite

    result = pd.DataFrame({
        "date": composite.index,
        "symptom_index": composite.values.round(2),
    })
    return result


def fetch_division_weights(geo="BD"):
    """
    Fetches interest_by_region across Bangladesh's 8 divisions for the
    anchor+core terms, to confirm Dhaka's relative share of national
    symptom-search volume. Used only as a sanity check / documentation
    artifact — actual zone disaggregation uses ZONE_WEIGHTS.
    """
    pytrends = _pytrends_client()
    try:
        pytrends.build_payload(SEARCH_BATCHES[0], timeframe="today 12-m", geo=geo)
        region_df = pytrends.interest_by_region(resolution='REGION', inc_low_vol=True)
        return region_df
    except Exception as e:
        print(f"   ⚠️  Could not fetch regional breakdown: {e}")
        return None


def disaggregate_to_zones(national_df):
    """
    Takes the national weekly symptom_index series and disaggregates it
    into 15 zone-level series using ZONE_WEIGHTS, with small zone-specific
    gaussian noise (same approach as generate_zone_csv.py for mobility).
    Returns a long-format DataFrame: date, zone_id, zone_name, symptom_score.
    """
    records = []
    for _, row in national_df.iterrows():
        date = row['date']
        base = row['symptom_index']
        for zone_id, weight in ZONE_WEIGHTS.items():
            noise = np.random.normal(0, 2.5)
            score = round(max(0, min(100, base * weight + noise)), 2)
            records.append({
                "date":          date,
                "zone_id":       zone_id,
                "zone_name":     ZONE_NAMES[zone_id],
                "symptom_score": score,
                "source":        "google_trends",
            })
    return pd.DataFrame(records)


def save_to_mongo(zone_df):
    """Writes each zone-week record to MongoDB via database.save_trends_snapshot."""
    count = 0
    for _, row in zone_df.iterrows():
        save_trends_snapshot(
            zone_id=int(row['zone_id']),
            zone_name=row['zone_name'],
            date=row['date'],
            symptom_score=float(row['symptom_score']),
            source=row['source'],
        )
        count += 1
    print(f"   💾 Saved {count} zone-week records to MongoDB (trends_data collection)")


def save_to_csv(zone_df, filename="dhaka_zone_symptom_trends.csv"):
    """Writes/append to the local CSV cache, mirroring the mobility CSV pattern."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(base_dir, "data", filename)

    if os.path.exists(out_path):
        existing = pd.read_csv(out_path)
        existing['date'] = pd.to_datetime(existing['date'])
        zone_df = zone_df.copy()
        zone_df['date'] = pd.to_datetime(zone_df['date'])
        merged = pd.concat([existing, zone_df]).drop_duplicates(
            subset=['date', 'zone_id'], keep='last'
        )
        merged = merged.sort_values(['date', 'zone_id'])
        merged.to_csv(out_path, index=False)
        print(f"   💾 Updated CSV cache: {out_path} ({len(merged)} total rows)")
    else:
        zone_df.to_csv(out_path, index=False)
        print(f"   💾 Created CSV cache: {out_path} ({len(zone_df)} rows)")


# ─────────────────────────────────────────────────────────────
# MAIN COLLECTOR
# ─────────────────────────────────────────────────────────────

def run_collector(timeframe="today 12-m"):
    """
    Incremental collection — pulls the most recent window (default 12
    months) of REAL Google Trends symptom-search data for Bangladesh,
    disaggregates it to zones, and saves to MongoDB + CSV cache.
    """
    print("🚀 Starting Google Trends Symptom-Search Collector (REAL DATA)")
    print(f"   Timeframe: {timeframe}   Geo: Bangladesh (BD)")
    print(f"   Search batches: {len(SEARCH_BATCHES)}  |  Anchor term: '{ANCHOR_TERM}'")
    print()

    national_df = fetch_national_symptom_index(timeframe=timeframe)
    if national_df is None:
        print("❌ Collection failed — no data retrieved.")
        return 0

    print(f"\n✅ Retrieved {len(national_df)} weekly national data points "
          f"({national_df['date'].min()} → {national_df['date'].max()})")

    zone_df = disaggregate_to_zones(national_df)
    save_to_csv(zone_df)
    save_to_mongo(zone_df)

    print(f"\n{'=' * 60}")
    print(f"✅ COLLECTION COMPLETE — {len(zone_df)} zone-week records")
    print(f"   Real weeks: {national_df['date'].nunique()}  x  15 zones")
    print(f"{'=' * 60}")
    return len(zone_df)


def run_backfill():
    """
    Full historical backfill (2020-01-01 to 2022-12-31), to match the
    date range of the existing mobility dataset. Google Trends only
    returns weekly-resolution data automatically once the requested
    range exceeds ~9 months, so a single 3-year request already comes
    back as weekly points — no manual chunking needed.
    """
    return run_collector(timeframe="2020-01-01 2022-12-31")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backfill", action="store_true",
                         help="Pull full 2020-2022 history instead of last 12 months")
    args = parser.parse_args()

    if args.backfill:
        run_backfill()
    else:
        run_collector()