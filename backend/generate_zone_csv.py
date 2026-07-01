"""
generate_zone_csv.py
====================
Takes the national-level CSV (bd_mobility_risk_score_2020_2022.csv)
and disaggregates it into a zone-wise CSV with 15 Dhaka monitoring zones.

Output:  data/dhaka_zone_mobility_2020_2022.csv
         (~14,600 rows = 975 dates x 15 zones)

Each zone gets:
  - Base score = national_score x zone_weight
  - Zone-specific noise (gaussian, sigma tuned by density)
  - Pandemic wave amplification for high-density zones
  - Lockdown dip effect (Mar-Jun 2020, Apr-May 2021)

Usage:
    cd backend/
    python generate_zone_csv.py
"""

import os
import numpy as np
import pandas as pd
from datetime import datetime

# ─────────────────────────────────────────────
# Zone definitions (must match engine_mobility.py)
# ─────────────────────────────────────────────
ZONE_PROFILES = {
    1:  {"name": "Uttara",                  "center": (23.8759, 90.3795), "density": "medium"},
    2:  {"name": "Mirpur",                  "center": (23.8223, 90.3654), "density": "high"},
    3:  {"name": "Gulshan & Banani",        "center": (23.7940, 90.4043), "density": "high"},
    4:  {"name": "Agargaon & Kafrul",       "center": (23.7751, 90.3668), "density": "medium"},
    5:  {"name": "Farmgate & Karwan Bazar", "center": (23.7527, 90.3894), "density": "very_high"},
    6:  {"name": "Diabari & Ashkona",       "center": (23.9012, 90.3456), "density": "low"},
    7:  {"name": "Uttarkhan & Faidabad",    "center": (23.9123, 90.4234), "density": "low"},
    8:  {"name": "Dakshinkhan & Dumni",     "center": (23.8934, 90.4456), "density": "low"},
    9:  {"name": "Vatara & Kuril",          "center": (23.8234, 90.4234), "density": "medium"},
    10: {"name": "Badda & Aftabnagar",      "center": (23.7845, 90.4234), "density": "medium"},
    11: {"name": "Ramna & Motijheel",       "center": (23.7234, 90.4123), "density": "very_high"},
    12: {"name": "Khilgaon & Mugda",        "center": (23.7345, 90.4345), "density": "high"},
    13: {"name": "Dhanmondi & Azimpur",     "center": (23.7456, 90.3789), "density": "high"},
    14: {"name": "Wari & Jatrabari",        "center": (23.7123, 90.4234), "density": "very_high"},
    15: {"name": "Bashundhara R/A (NSU)",   "center": (23.8191, 90.4526), "density": "medium"},
}

# Zone weights — how much each zone's mobility tracks the national average
# Based on population density + commercial activity
ZONE_WEIGHTS = {
    1:  0.65,   # Uttara — planned residential
    2:  0.80,   # Mirpur — high density
    3:  0.70,   # Gulshan & Banani — commercial hub
    4:  0.55,   # Agargaon — government area
    5:  0.90,   # Farmgate — highest commercial
    6:  0.35,   # Diabari — peripheral
    7:  0.30,   # Uttarkhan — outskirts
    8:  0.32,   # Dakshinkhan — outskirts
    9:  0.60,   # Vatara — mixed
    10: 0.58,   # Badda — residential
    11: 0.95,   # Ramna — CBD highest
    12: 0.75,   # Khilgaon — dense residential
    13: 0.78,   # Dhanmondi — hospital cluster
    14: 0.88,   # Wari — Old Dhaka extreme density
    15: 1.10,   # Bashundhara NSU — research zone (high activity)
}

# Noise std-dev per density class (higher density = more volatile mobility)
DENSITY_NOISE = {
    "very_high": 5.5,
    "high":       4.5,
    "medium":     3.5,
    "low":        2.5,
}


def generate_zone_csv():
    """Read national CSV, disaggregate to 15 zones, save zone CSV."""

    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    input_path  = os.path.join(data_dir, "bd_mobility_risk_score_2020_2022.csv")
    output_path = os.path.join(data_dir, "dhaka_zone_mobility_2020_2022.csv")

    # ── Load national CSV ──
    print(f"Reading national CSV: {input_path}")
    df = pd.read_csv(input_path)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    print(f"   {len(df)} rows, {df['date'].min().date()} -> {df['date'].max().date()}")

    # ── Disaggregate ──
    np.random.seed(42)  # reproducibility
    all_records = []

    for zone_id, profile in ZONE_PROFILES.items():
        weight = ZONE_WEIGHTS[zone_id]
        noise_sigma = DENSITY_NOISE[profile['density']]
        density = profile['density']

        for _, row in df.iterrows():
            date  = row['date']
            score = row['mobility_risk_score']

            # Base: national score x zone weight
            zone_score = score * weight

            # Add zone-specific gaussian noise
            noise = np.random.normal(0, noise_sigma)
            zone_score += noise

            # Lockdown dip amplification (denser zones drop more)
            lockdown1 = (datetime(2020, 3, 15) <= date <= datetime(2020, 6, 30))
            lockdown2 = (datetime(2021, 4, 5)  <= date <= datetime(2021, 5, 30))
            if lockdown1 or lockdown2:
                lockdown_factor = {"very_high": -12, "high": -9, "medium": -6, "low": -3}
                zone_score += lockdown_factor[density]

            # Clamp to 0-100
            zone_score = round(max(0.0, min(100.0, zone_score)), 2)

            all_records.append({
                'date':                date.strftime('%Y-%m-%d'),
                'zone_id':             zone_id,
                'zone_name':           profile['name'],
                'mobility_risk_score': zone_score,
            })

    # ── Save ──
    out_df = pd.DataFrame(all_records)
    out_df['date'] = pd.to_datetime(out_df['date'])
    out_df = out_df.sort_values(['date', 'zone_id']).reset_index(drop=True)
    out_df.to_csv(output_path, index=False)

    print(f"\nGenerated zone CSV: {output_path}")
    print(f"   Total rows:    {len(out_df)}")
    print(f"   Zones:         {out_df['zone_id'].nunique()}")
    print(f"   Date range:    {out_df['date'].min().date()} -> {out_df['date'].max().date()}")
    print(f"   Score range:   {out_df['mobility_risk_score'].min():.1f} - {out_df['mobility_risk_score'].max():.1f}")

    # Quick per-zone summary
    print(f"\nPer-zone average scores:")
    for zid in sorted(out_df['zone_id'].unique()):
        zdf = out_df[out_df['zone_id'] == zid]
        name = zdf['zone_name'].iloc[0]
        avg  = zdf['mobility_risk_score'].mean()
        print(f"   Zone {zid:2d} ({name:<25s}): avg={avg:5.1f}, n={len(zdf)}")


if __name__ == "__main__":
    generate_zone_csv()