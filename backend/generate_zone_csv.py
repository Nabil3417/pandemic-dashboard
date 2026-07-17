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

# Zone definitions — loaded from zones.json (single source of truth)
from zones_loader import ZONE_PROFILES, ZONE_WEIGHTS

# Noise std-dev per density class
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