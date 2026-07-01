"""
BioGuard AI — Mobility Anomaly Detection Engine  v4.1
========================================================
Dual-mode architecture:
  Mode 1 — IsolationForest + HDBSCAN  (real-time anomaly detection per zone)
  Mode 2 — CSV-backed ARIMA time-series (historical trends + forecasting)

Data sources:
  - dhaka_zone_mobility_2020_2022.csv  (zone-level weekly mobility, 15 zones)
  - bd_mobility_risk_score_2020_2022.csv  (national-level, fallback)

Why HDBSCAN over DBSCAN:
  Dhaka has extreme density variation — Wari (Old Dhaka) is one of
  the densest areas in the world while Diabari is sparse suburban.
  DBSCAN uses one fixed radius (epsilon) for all zones — wrong.
  HDBSCAN finds clusters automatically adapting to local density.

Why per-zone IsolationForest:
  A global model trained on all zones treats low-density zone
  coordinates as anomalous when evaluated against high-density zones.

Reference:
  Campello et al. 2013 — Density-Based Clustering Based on
  Hierarchical Density Estimates. ECML/PKDD.
"""

import os
import re
import random
import numpy as np
from datetime import datetime, timedelta

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import hdbscan

# ─────────────────────────────────────────────
# Zone definitions (mirrors app.py ZONES)
# ─────────────────────────────────────────────
ZONE_PROFILES = {
    1:  {"name": "Uttara",                  "center": (23.8759, 90.3795), "density": "medium",    "min_cluster": 5},
    2:  {"name": "Mirpur",                  "center": (23.8223, 90.3654), "density": "high",       "min_cluster": 8},
    3:  {"name": "Gulshan & Banani",        "center": (23.7940, 90.4043), "density": "medium",    "min_cluster": 5},
    4:  {"name": "Agargaon & Kafrul",       "center": (23.7751, 90.3668), "density": "medium",    "min_cluster": 5},
    5:  {"name": "Farmgate & Karwan Bazar", "center": (23.7527, 90.3894), "density": "very_high", "min_cluster": 10},
    6:  {"name": "Diabari & Ashkona",       "center": (23.9012, 90.3456), "density": "low",       "min_cluster": 3},
    7:  {"name": "Uttarkhan & Faidabad",    "center": (23.9123, 90.4234), "density": "low",       "min_cluster": 3},
    8:  {"name": "Dakshinkhan & Dumni",     "center": (23.8934, 90.4456), "density": "low",       "min_cluster": 3},
    9:  {"name": "Vatara & Kuril",          "center": (23.8234, 90.4234), "density": "medium",    "min_cluster": 5},
    10: {"name": "Badda & Aftabnagar",      "center": (23.7845, 90.4234), "density": "medium",    "min_cluster": 5},
    11: {"name": "Ramna & Motijheel",       "center": (23.7234, 90.4123), "density": "very_high", "min_cluster": 10},
    12: {"name": "Khilgaon & Mugda",        "center": (23.7345, 90.4345), "density": "high",      "min_cluster": 8},
    13: {"name": "Dhanmondi & Azimpur",     "center": (23.7456, 90.3789), "density": "high",      "min_cluster": 8},
    14: {"name": "Wari & Jatrabari",        "center": (23.7123, 90.4234), "density": "very_high", "min_cluster": 10},
    15: {"name": "Bashundhara R/A (NSU)",   "center": (23.8191, 90.4526), "density": "medium",    "min_cluster": 5},
}

DENSITY_SPREAD = {
    "low":       0.015,
    "medium":    0.010,
    "high":      0.007,
    "very_high": 0.005,
}


def _generate_normal_points(center_lat, center_lng, spread, n=300):
    """Generate normally distributed GPS points around a zone center."""
    points = []
    for _ in range(n):
        lat = center_lat + random.gauss(0, spread)
        lng = center_lng + random.gauss(0, spread)
        points.append([lat, lng])
    return points


def _generate_anomalous_points(center_lat, center_lng, spread,
                                n=20, crisis_mode=False):
    """Generate anomalous GPS points (crowding clusters)."""
    points  = []
    offsets = [0.018, -0.018, 0.025] if crisis_mode else [0.015, -0.015]
    n_each  = n // len(offsets)
    for offset in offsets:
        for _ in range(n_each):
            lat = center_lat + offset + random.gauss(0, spread * 0.3)
            lng = center_lng + offset + random.gauss(0, spread * 0.3)
            points.append([lat, lng])
    return points


class MobilityDetectionEngine:
    """
    Dual-mode mobility engine for BioGuard AI.

    Mode 1 — Real-time anomaly detection:
        IsolationForest (per-zone) + HDBSCAN clustering
        -> detect crowding events and behavioral changes

    Mode 2 — CSV-backed time-series:
        Load zone-level mobility CSV, run ARIMA per zone
        -> historical trends, forecasting, national score
    """

    def __init__(self):
        print("=" * 70)
        print("  BioGuard AI — Mobility Anomaly Detection Engine v4.1")
        print("=" * 70)

        # -- Mode 1: Anomaly detection models --
        self.zone_models      = {}
        self.zone_scalers     = {}
        self.isolation_forest = None
        self.scaler           = StandardScaler()
        self.trained          = False

        # -- Mode 2: CSV + ARIMA time-series --
        self.zone_data        = {}
        self.national_data    = None
        self.arima_models     = {}
        self.csv_loaded       = False
        self.data_source      = "none"

        # -- Computed values (used by app.py) --
        self._current_national_score = None
        self.zone_stats              = {}

        # -- Initialize both modes --
        self._train_anomaly_models()
        self._load_csv_data()
        self._compute_zone_stats()

        print("  Status: READY")
        print("=" * 70)

    # =============================================
    # MODE 1: ISOLATION FOREST + HDBSCAN
    # =============================================

    def _train_anomaly_models(self):
        """Train per-zone IsolationForest + global model."""
        print("  [1/3] Training IsolationForest models (15 zones)...")
        all_global_points = []

        for zone_id, profile in ZONE_PROFILES.items():
            lat, lng = profile['center']
            spread   = DENSITY_SPREAD[profile['density']]
            normal   = _generate_normal_points(lat, lng, spread, n=300)
            data     = np.array(normal)

            zone_scaler = StandardScaler()
            scaled      = zone_scaler.fit_transform(data)

            zone_model = IsolationForest(
                n_estimators=100,
                contamination=0.05,
                random_state=42
            )
            zone_model.fit(scaled)

            self.zone_models[zone_id]  = zone_model
            self.zone_scalers[zone_id] = zone_scaler
            all_global_points.extend(normal)

        global_data = np.array(all_global_points)
        self.scaler.fit(global_data)
        scaled_global = self.scaler.transform(global_data)
        self.isolation_forest = IsolationForest(
            n_estimators=100, contamination=0.05, random_state=42
        )
        self.isolation_forest.fit(scaled_global)
        self.trained = True
        print("        Done - 15 zone models + 1 global model trained.")

    def detect_anomaly(self, lat, lng):
        """Check if a single GPS point is anomalous (global model)."""
        if not self.trained:
            return False
        point  = np.array([[lat, lng]])
        scaled = self.scaler.transform(point)
        pred   = self.isolation_forest.predict(scaled)
        return bool(pred[0] == -1)

    def analyze_zone_mobility(self, zone_id, crisis_mode=False):
        """
        Analyze mobility for a single zone.

        Called by app.py calculate_multi_modal_risk().
        Returns dict with: is_anomaly, cluster_size, mobility_score, ...

        If CSV data is loaded, enhances the score with ARIMA trend info.
        """
        if zone_id not in ZONE_PROFILES:
            zone_id = 15

        profile  = ZONE_PROFILES[zone_id]
        lat, lng = profile['center']
        spread   = DENSITY_SPREAD[profile['density']]
        min_pts  = profile['min_cluster']
        model    = self.zone_models[zone_id]
        scaler   = self.zone_scalers[zone_id]

        # -- Generate simulation points --
        n_anomalous = 40 if crisis_mode else 18
        normal_pts  = _generate_normal_points(lat, lng, spread, n=220)
        anom_pts    = _generate_anomalous_points(
            lat, lng, spread, n=n_anomalous, crisis_mode=crisis_mode
        )

        all_points = normal_pts + anom_pts
        points_arr = np.array(all_points)
        scaled_pts = scaler.transform(points_arr)

        # -- IsolationForest prediction --
        predictions   = model.predict(scaled_pts)
        anomaly_mask  = predictions == -1
        anomaly_pts   = points_arr[anomaly_mask]
        is_anomaly    = bool(np.any(anomaly_mask))
        anomaly_count = int(np.sum(anomaly_mask))

        # -- HDBSCAN clustering on anomalies --
        cluster_count = 0
        cluster_size  = 0
        noise_points  = 0
        pattern       = "Normal movement patterns"

        if len(anomaly_pts) >= min_pts:
            clusterer = hdbscan.HDBSCAN(
                min_cluster_size=min_pts,
                min_samples=max(2, min_pts // 2),
                cluster_selection_epsilon=0.005,
                metric='euclidean'
            )
            labels        = clusterer.fit_predict(anomaly_pts)
            unique_labels = set(labels)
            unique_labels.discard(-1)
            cluster_count = len(unique_labels)
            noise_points  = int(np.sum(labels == -1))

            if cluster_count > 0:
                cluster_size = int(max(
                    np.sum(labels == lbl) for lbl in unique_labels
                ))

        if cluster_count == 0:
            pattern = "Normal movement patterns"
        elif cluster_count == 1 and cluster_size < 10:
            pattern = "Minor anomaly cluster detected"
        elif cluster_count == 1 and cluster_size >= 10:
            pattern = "Significant crowding detected"
        elif cluster_count == 2:
            pattern = "Multiple anomaly clusters - possible crowding event"
        else:
            pattern = "High cluster density - mass behavioral change"

        # -- Score computation --
        base_score    = 8.0
        anomaly_ratio = anomaly_count / len(all_points)
        base_score   += anomaly_ratio * 35

        cluster_bonus = {0: 0, 1: 15, 2: 25, 3: 35}
        base_score   += cluster_bonus.get(min(cluster_count, 3), 35)

        if cluster_size >= 5:  base_score += 5
        if cluster_size >= 10: base_score += 8
        if cluster_size >= 20: base_score += 10
        if crisis_mode:        base_score += 20

        # -- Enhance with CSV trend if available --
        if self.csv_loaded and zone_id in self.zone_stats:
            trend = self.zone_stats[zone_id].get('trend', 'stable')
            if trend == 'rising':
                base_score += 5
            elif trend == 'falling':
                base_score -= 3

        mobility_score = min(round(base_score, 2), 100.0)

        return {
            "is_anomaly":     is_anomaly,
            "cluster_count":  cluster_count,
            "cluster_size":   cluster_size,
            "noise_points":   noise_points,
            "anomaly_count":  anomaly_count,
            "total_points":   len(all_points),
            "mobility_score": mobility_score,
            "pattern":        pattern,
            "density_class":  profile['density'],
        }

    # =============================================
    # MODE 2: CSV-BACKED ARIMA TIME-SERIES
    # =============================================

    def _load_csv_data(self):
        """Load zone-level mobility CSV (primary) or national CSV (fallback)."""
        print("  [2/3] Loading mobility data...")

        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(base_dir, "data")

        # -- Try zone-level CSV first --
        zone_csv = os.path.join(data_dir, "dhaka_zone_mobility_2020_2022.csv")
        if os.path.exists(zone_csv):
            self._load_zone_csv(zone_csv)
            return

        # -- Fallback to national CSV --
        national_csv = os.path.join(data_dir, "bd_mobility_risk_score_2020_2022.csv")
        if os.path.exists(national_csv):
            self._load_national_csv(national_csv)
            return

        # -- No CSV found -- generate synthetic fallback --
        print("        No CSV files found. Using synthetic fallback data.")
        self._generate_synthetic_data()
        self.csv_loaded = True
        self.data_source = "synthetic-fallback"

    def _load_zone_csv(self, filepath):
        """Load zone-level mobility CSV (15 zones x weekly data)."""
        try:
            import pandas as pd

            df = pd.read_csv(filepath)
            df['date'] = pd.to_datetime(df['date'])

            # Detect the zone identifier column
            zone_col = None
            for col in ['zone_id', 'zone_name', 'zone', 'Zone']:
                if col in df.columns:
                    zone_col = col
                    break

            if zone_col is None:
                print(f"        WARNING: No zone column found in {os.path.basename(filepath)}")
                print(f"        Columns available: {list(df.columns)}")
                return

            print(f"        Zone column detected: '{zone_col}'")
            print(f"        Sample values: {df[zone_col].unique()[:5].tolist()}")

            # Split into per-zone DataFrames
            for zone_id in ZONE_PROFILES:
                zone_df = None

                if zone_col == 'zone_id' and df[zone_col].dtype in [int, float]:
                    # Numeric zone_id column -- direct match
                    zone_df = df[df[zone_col] == zone_id].copy()
                else:
                    # String zone column -- try multiple matching strategies

                    # Strategy 1: Extract "Zone-{N}" pattern and match number
                    mask = df[zone_col].apply(
                        lambda x: bool(re.search(rf'Zone[-_]?{zone_id}[\b_-]', str(x)))
                    )
                    if mask.sum() > 0:
                        zone_df = df[mask].copy()

                    # Strategy 2: Check if zone_id number appears at start
                    if zone_df is None or len(zone_df) == 0:
                        mask = df[zone_col].apply(
                            lambda x: str(x).strip().startswith(f"Zone-{zone_id}_") or
                                     str(x).strip().startswith(f"Zone_{zone_id}_") or
                                     str(x).strip() == f"Zone-{zone_id}" or
                                     str(x).strip() == f"Zone_{zone_id}"
                        )
                        if mask.sum() > 0:
                            zone_df = df[mask].copy()

                    # Strategy 3: Partial name match against ZONE_PROFILES name
                    if zone_df is None or len(zone_df) == 0:
                        profile_name = ZONE_PROFILES[zone_id]['name']
                        for keyword in profile_name.split(' & '):
                            keyword = keyword.split(' ')[0]
                            if keyword.lower() in ['and', 'the', 'r/a', 'r/a']:
                                continue
                            mask = df[zone_col].str.contains(
                                keyword, case=False, na=False
                            )
                            if mask.sum() > 0:
                                zone_df = df[mask].copy()
                                break

                if zone_df is not None and len(zone_df) > 0:
                    zone_df = zone_df.sort_values('date').reset_index(drop=True)
                    self.zone_data[zone_id] = zone_df

            loaded_zones = len(self.zone_data)
            self.csv_loaded = True
            self.data_source = f"zone-csv ({loaded_zones} zones from {os.path.basename(filepath)})"

            # Also store full national view
            self.national_data = df

            print(f"        Loaded: {os.path.basename(filepath)}")
            print(f"        Zones with data: {loaded_zones}/15")
            print(f"        Date range: {df['date'].min().date()} -> {df['date'].max().date()}")
            print(f"        Total records: {len(df)}")

        except Exception as e:
            print(f"        ERROR loading zone CSV: {e}")
            print("        Falling back to national CSV...")
            national_csv = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "data",
                "bd_mobility_risk_score_2020_2022.csv"
            )
            if os.path.exists(national_csv):
                self._load_national_csv(national_csv)
            else:
                self._generate_synthetic_data()
                self.csv_loaded = True
                self.data_source = "synthetic-fallback"

    def _load_national_csv(self, filepath):
        """Load national-level mobility CSV and disaggregate to zones."""
        try:
            import pandas as pd

            df = pd.read_csv(filepath)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)

            self.national_data = df

            # Disaggregate national data to zones using weights
            zone_weights = self._get_zone_weights()
            for zone_id, weight in zone_weights.items():
                zone_df = df.copy()
                score_col = None
                for col in ['mobility_risk_score', 'risk_score', 'score', 'mobility_score']:
                    if col in zone_df.columns:
                        score_col = col
                        break
                if score_col:
                    noise = np.random.normal(0, 3, len(zone_df))
                    zone_df['mobility_risk_score'] = (
                        zone_df[score_col] * weight + noise
                    ).clip(0, 100)
                self.zone_data[zone_id] = zone_df

            self.csv_loaded = True
            self.data_source = f"national-csv-disaggregated ({os.path.basename(filepath)})"

            print(f"        Loaded: {os.path.basename(filepath)} (national, disaggregated)")
            print(f"        Date range: {df['date'].min().date()} -> {df['date'].max().date()}")
            print(f"        Total records: {len(df)}")

        except Exception as e:
            print(f"        ERROR loading national CSV: {e}")
            print("        Falling back to synthetic data...")
            self._generate_synthetic_data()
            self.csv_loaded = True
            self.data_source = "synthetic-fallback"

    def _get_zone_weights(self):
        """Zone weights for national-to-zone disaggregation."""
        return {
            1:  0.65,   # Uttara
            2:  0.80,   # Mirpur
            3:  0.70,   # Gulshan & Banani
            4:  0.55,   # Agargaon
            5:  0.90,   # Farmgate
            6:  0.35,   # Diabari
            7:  0.30,   # Uttarkhan
            8:  0.32,   # Dakshinkhan
            9:  0.60,   # Vatara
            10: 0.58,   # Badda
            11: 0.95,   # Ramna
            12: 0.75,   # Khilgaon
            13: 0.78,   # Dhanmondi
            14: 0.88,   # Wari
            15: 1.10,   # Bashundhara NSU
        }

    def _generate_synthetic_data(self):
        """Generate synthetic weekly mobility data for all 15 zones."""
        print("        Generating synthetic zone mobility data...")

        try:
            import pandas as pd

            start_date = datetime(2020, 1, 1)
            end_date   = datetime(2022, 12, 31)
            weeks = pd.date_range(start=start_date, end=end_date, freq='W')

            zone_weights = self._get_zone_weights()
            all_records = []

            for zone_id, weight in zone_weights.items():
                for i, week_date in enumerate(weeks):
                    t = i / len(weeks)
                    wave = 30 + 25 * np.sin(t * 4 * np.pi) + 10 * np.sin(t * 8 * np.pi)
                    lockdown_effect = -15 if datetime(2020, 3, 15) <= week_date <= datetime(2020, 6, 30) else 0
                    base = wave * weight + lockdown_effect + np.random.normal(0, 4)
                    score = round(max(0, min(100, base)), 2)

                    all_records.append({
                        'date': week_date.strftime('%Y-%m-%d'),
                        'zone_id': zone_id,
                        'zone_name': ZONE_PROFILES[zone_id]['name'],
                        'mobility_risk_score': score,
                    })

            df = pd.DataFrame(all_records)
            df['date'] = pd.to_datetime(df['date'])

            self.national_data = df
            for zone_id in ZONE_PROFILES:
                self.zone_data[zone_id] = df[df['zone_id'] == zone_id].copy()

            print(f"        Generated {len(all_records)} records for 15 zones")
            print(f"        Date range: {start_date.date()} -> {end_date.date()}")

        except ImportError:
            print("        WARNING: pandas not available, synthetic data disabled.")
            self.csv_loaded = False

    def _compute_zone_stats(self):
        """Compute summary statistics for each zone (used by API endpoints)."""
        print("  [3/3] Computing zone statistics...")
        self.zone_stats = {}
        self._current_national_score = 35.0

        if not self.csv_loaded:
            defaults = {
                1: 45.0, 2: 52.0, 3: 42.0, 4: 38.0, 5: 67.0,
                6: 22.0, 7: 18.0, 8: 20.0, 9: 35.0, 10: 41.0,
                11: 72.0, 12: 55.0, 13: 60.0, 14: 65.0, 15: 88.5,
            }
            for zone_id, score in defaults.items():
                self.zone_stats[zone_id] = {
                    'name': ZONE_PROFILES[zone_id]['name'],
                    'current_score': score,
                    'mean': score,
                    'std': 5.0,
                    'trend': 'stable',
                    'data_points': 0,
                }
            self._current_national_score = 45.0
            print("        Using default zone statistics (no CSV data).")
            return

        try:
            import pandas as pd
            all_latest = []

            for zone_id, zone_df in self.zone_data.items():
                if len(zone_df) == 0:
                    continue

                score_col = None
                for col in ['mobility_risk_score', 'risk_score', 'score', 'mobility_score']:
                    if col in zone_df.columns:
                        score_col = col
                        break

                if score_col is None:
                    continue

                scores = zone_df[score_col].dropna()
                if len(scores) == 0:
                    continue

                latest = scores.iloc[-1]
                mean   = scores.mean()
                std    = scores.std()

                trend = 'stable'
                if len(scores) >= 8:
                    recent_avg  = scores.iloc[-4:].mean()
                    previous_avg = scores.iloc[-8:-4].mean()
                    diff = recent_avg - previous_avg
                    if diff > 3:
                        trend = 'rising'
                    elif diff < -3:
                        trend = 'falling'

                self.zone_stats[zone_id] = {
                    'name':          ZONE_PROFILES[zone_id]['name'],
                    'current_score': round(float(latest), 2),
                    'mean':          round(float(mean), 2),
                    'std':           round(float(std), 2) if not pd.isna(std) else 0.0,
                    'trend':         trend,
                    'data_points':   len(scores),
                }
                all_latest.append(float(latest))

            if all_latest:
                self._current_national_score = round(
                    float(np.mean(all_latest)), 2
                )
            print(f"        Computed stats for {len(self.zone_stats)} zones")
            print(f"        National mobility score: {self._current_national_score}")

        except Exception as e:
            print(f"        ERROR computing stats: {e}")
            self._current_national_score = 35.0

    # =============================================
    # PROPERTIES (called by app.py)
    # =============================================

    @property
    def current_national_score(self):
        """
        Current national-level mobility score (0-100).
        Called by app.py:
            national_mobility = mobility_ai.current_national_score
        """
        if self._current_national_score is not None:
            return self._current_national_score
        return 35.0

    # =============================================
    # API METHODS (called by app.py endpoints)
    # =============================================

    def get_engine_status(self):
        """
        Returns engine status dict.
        Called by app.py /api/engine-status endpoint.
        """
        return {
            "status":           "ready" if self.trained else "error",
            "isolation_forest": "active (per-zone)" if self.trained else "failed",
            "clustering":       "HDBSCAN (density-adaptive)",
            "zones_covered":    len(ZONE_PROFILES),
            "zone_models":      len(self.zone_models),
            "contamination":    "5%",
            "data_source":      self.data_source,
            "csv_loaded":       self.csv_loaded,
            "arima_zones":      len(self.arima_models),
            "national_score":   self.current_national_score,
            "reference":        "Campello et al. 2013, ECML/PKDD",
        }

    def get_historical_data(self, days=90):
        """
        Returns historical mobility data points.
        Called by app.py /api/mobility-history endpoint.
        Returns list of dicts with date, score, zone info.

        FIXED: Uses CSV's own max date instead of datetime.now()
        so historical data always returns results even when
        the CSV covers 2020-2022 and today is 2025+.
        """
        if not self.csv_loaded or self.national_data is None:
            return self._synthetic_history(days)

        try:
            import pandas as pd

            df = self.national_data.copy()

            score_col = None
            for col in ['mobility_risk_score', 'risk_score', 'score', 'mobility_score']:
                if col in df.columns:
                    score_col = col
                    break

            if score_col is None:
                return self._synthetic_history(days)

            # *** FIX: Use CSV's max date, NOT datetime.now() ***
            max_date = df['date'].max()
            cutoff   = max_date - timedelta(days=days)
            df       = df[df['date'] >= cutoff].sort_values('date')

            # If zone-level data, aggregate to daily national average
            if 'zone_id' in df.columns:
                daily = df.groupby(df['date'].dt.date)[score_col].mean().reset_index()
                daily.columns = ['date', 'score']
                daily['score'] = daily['score'].round(2)
            else:
                daily = df[['date', score_col]].copy()
                daily.columns = ['date', 'score']

            result = []
            for _, row in daily.iterrows():
                result.append({
                    "date":  row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date']),
                    "score": round(float(row['score']), 2),
                })

            return result

        except Exception as e:
            print(f"  ERROR in get_historical_data: {e}")
            return self._synthetic_history(days)

    def _synthetic_history(self, days=90):
        """Generate synthetic historical data when no CSV is available."""
        result = []
        base = 35.0
        for i in range(days):
            date = datetime.now() - timedelta(days=days - i)
            base += random.uniform(-2, 2)
            base = max(10, min(90, base))
            result.append({
                "date":  date.strftime('%Y-%m-%d'),
                "score": round(base, 2),
            })
        return result

    def get_risk_scores(self):
        """Returns current risk scores for all zones."""
        scores = {}
        for zone_id, stats in self.zone_stats.items():
            scores[zone_id] = {
                "name":  stats['name'],
                "score": stats['current_score'],
                "trend": stats['trend'],
                "mean":  stats['mean'],
            }
        return scores

    def get_zone_forecast(self, zone_id, periods=14):
        """
        ARIMA-based forecast for a specific zone.
        Returns list of {date, predicted_score} dicts.
        """
        if zone_id not in self.zone_data:
            return []

        zone_df = self.zone_data[zone_id]

        score_col = None
        for col in ['mobility_risk_score', 'risk_score', 'score', 'mobility_score']:
            if col in zone_df.columns:
                score_col = col
                break

        if score_col is None:
            return []

        try:
            from statsmodels.tsa.arima.model import ARIMA

            series = zone_df[score_col].dropna().values
            if len(series) < 20:
                return []

            model = ARIMA(series, order=(2, 1, 2))
            fitted = model.fit()

            forecast = fitted.forecast(steps=periods)
            last_date = zone_df['date'].iloc[-1]

            results = []
            for i, val in enumerate(forecast):
                pred_date = last_date + timedelta(weeks=i + 1)
                results.append({
                    "date":  pred_date.strftime('%Y-%m-%d'),
                    "predicted_score": round(float(val), 2),
                })

            return results

        except ImportError:
            series = zone_df[score_col].dropna().values
            if len(series) < 5:
                return []

            recent_trend = (series[-1] - series[-5]) / 5
            last_val = series[-1]
            last_date = zone_df['date'].iloc[-1]

            results = []
            for i in range(periods):
                pred_val = last_val + recent_trend * (i + 1)
                pred_date = last_date + timedelta(weeks=i + 1)
                results.append({
                    "date":  pred_date.strftime('%Y-%m-%d'),
                    "predicted_score": round(float(max(0, min(100, pred_val))), 2),
                })

            return results

        except Exception as e:
            print(f"  ERROR in get_zone_forecast(zone {zone_id}): {e}")
            return []

    def _match_zone(self, zone_id):
        """Match a zone ID to its profile. Returns profile dict or default."""
        if zone_id in ZONE_PROFILES:
            return ZONE_PROFILES[zone_id]
        return ZONE_PROFILES[15]


# =============================================
# MODULE-LEVEL INSTANCE (imported by app.py)
# =============================================
mobility_ai = MobilityDetectionEngine()


# =============================================
# STANDALONE TESTING
# =============================================
if __name__ == "__main__":
    print("\n" + "=" * 85)
    print("TESTING MOBILITY DETECTION ENGINE v4.1")
    print("=" * 85)

    print(f"\n{'Zone':<28} {'Density':<10} {'Score':>6} "
          f"{'Clusters':>9} {'Size':>6} {'Pattern'}")
    print("-" * 100)

    for zone_id, profile in ZONE_PROFILES.items():
        result = mobility_ai.analyze_zone_mobility(zone_id)
        print(
            f"{profile['name']:<28} {profile['density']:<10} "
            f"{result['mobility_score']:>6.1f} "
            f"{result['cluster_count']:>9} "
            f"{result['cluster_size']:>6} "
            f"{result['pattern']}"
        )

    print("\n--- CRISIS MODE TEST (Zone 14 Wari) ---")
    normal = mobility_ai.analyze_zone_mobility(14, crisis_mode=False)
    crisis = mobility_ai.analyze_zone_mobility(14, crisis_mode=True)
    print(f"Normal: score={normal['mobility_score']:>5.1f}  "
          f"clusters={normal['cluster_count']}  "
          f"pattern={normal['pattern']}")
    print(f"Crisis: score={crisis['mobility_score']:>5.1f}  "
          f"clusters={crisis['cluster_count']}  "
          f"pattern={crisis['pattern']}")

    print(f"\n--- NATIONAL SCORE ---")
    print(f"Current national mobility score: {mobility_ai.current_national_score}")

    print(f"\n--- HISTORICAL DATA (last 30 days) ---")
    history = mobility_ai.get_historical_data(days=30)
    print(f"Data points returned: {len(history)}")
    if history:
        print(f"First: {history[0]}")
        print(f"Last:  {history[-1]}")

    print("\n--- ENGINE STATUS ---")
    for key, val in mobility_ai.get_engine_status().items():
        print(f"  {key}: {val}")

    print("\n--- ZONE STATS ---")
    for zone_id, stats in mobility_ai.zone_stats.items():
        print(f"  Zone {zone_id:>2} ({stats['name']:<25}): "
              f"score={stats['current_score']:>5.1f}  "
              f"trend={stats['trend']:<7}  "
              f"pts={stats['data_points']}")

    print("=" * 85)