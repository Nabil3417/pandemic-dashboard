"""
BioGuard AI — Mobility Anomaly Detection Engine
================================================
Architecture:
  - IsolationForest  → per-zone model, detects individual anomalies
  - HDBSCAN          → hierarchical density clustering
                       adapts to varying population density per zone
                       outperforms DBSCAN in heterogeneous urban areas
  - Combined score   → single mobility risk value (0-100)

Why HDBSCAN over DBSCAN:
  Dhaka has extreme density variation — Wari (Old Dhaka) is one of
  the densest areas in the world while Diabari is sparse suburban.
  DBSCAN uses one fixed radius (epsilon) for all zones — wrong.
  HDBSCAN finds clusters automatically adapting to local density.

Why per-zone IsolationForest:
  A global model trained on all zones treats low-density zone
  coordinates as anomalous when evaluated against high-density zones.
  Each zone needs its own normal baseline.

Reference:
  Campello et al. 2013 — Density-Based Clustering Based on
  Hierarchical Density Estimates. ECML/PKDD.
"""

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import hdbscan
import random

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
    points = []
    for _ in range(n):
        lat = center_lat + random.gauss(0, spread)
        lng = center_lng + random.gauss(0, spread)
        points.append([lat, lng])
    return points


def _generate_anomalous_points(center_lat, center_lng, spread,
                                n=20, crisis_mode=False):
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

    def __init__(self):
        print("🗺️  Initializing Mobility Detection Engine...")
        print("   Primary:   IsolationForest (per-zone, individual anomaly)")
        print("   Secondary: HDBSCAN (density-adaptive cluster detection)")
        print("   Coverage:  15 Dhaka City Corporation zones")
        print("   Reference: Campello et al. 2013, ECML/PKDD")

        self.zone_models      = {}
        self.zone_scalers     = {}
        self.isolation_forest = None
        self.scaler           = StandardScaler()
        self.trained          = False

        self._train()
        print("✅ Mobility engine ready!")

    def _train(self):
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

    def detect_anomaly(self, lat, lng):
        if not self.trained:
            return False
        point  = np.array([[lat, lng]])
        scaled = self.scaler.transform(point)
        pred   = self.isolation_forest.predict(scaled)
        return bool(pred[0] == -1)

    def analyze_zone_mobility(self, zone_id, crisis_mode=False):
        if zone_id not in ZONE_PROFILES:
            zone_id = 15

        profile  = ZONE_PROFILES[zone_id]
        lat, lng = profile['center']
        spread   = DENSITY_SPREAD[profile['density']]
        min_pts  = profile['min_cluster']
        model    = self.zone_models[zone_id]
        scaler   = self.zone_scalers[zone_id]

        n_anomalous = 40 if crisis_mode else 18
        normal_pts  = _generate_normal_points(lat, lng, spread, n=220)
        anom_pts    = _generate_anomalous_points(
            lat, lng, spread, n=n_anomalous, crisis_mode=crisis_mode
        )

        all_points = normal_pts + anom_pts
        points_arr = np.array(all_points)
        scaled_pts = scaler.transform(points_arr)

        predictions   = model.predict(scaled_pts)
        anomaly_mask  = predictions == -1
        anomaly_pts   = points_arr[anomaly_mask]
        is_anomaly    = bool(np.any(anomaly_mask))
        anomaly_count = int(np.sum(anomaly_mask))

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
            pattern = "Multiple anomaly clusters — possible crowding event"
        else:
            pattern = "High cluster density — mass behavioral change"

        base_score    = 8.0
        anomaly_ratio = anomaly_count / len(all_points)
        base_score   += anomaly_ratio * 35

        cluster_bonus = {0: 0, 1: 15, 2: 25, 3: 35}
        base_score   += cluster_bonus.get(min(cluster_count, 3), 35)

        if cluster_size >= 5:  base_score += 5
        if cluster_size >= 10: base_score += 8
        if cluster_size >= 20: base_score += 10
        if crisis_mode:        base_score += 20

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

    def get_engine_status(self):
        return {
            "isolation_forest": "active (per-zone)" if self.trained else "failed",
            "clustering":       "HDBSCAN (density-adaptive)",
            "zones_covered":    len(ZONE_PROFILES),
            "zone_models":      len(self.zone_models),
            "contamination":    "5%",
            "reference":        "Campello et al. 2013, ECML/PKDD",
            "status":           "ready" if self.trained else "error",
        }


mobility_ai = MobilityDetectionEngine()


if __name__ == "__main__":
    print("\n" + "=" * 85)
    print("TESTING HDBSCAN MOBILITY DETECTION ENGINE")
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

    print("\n--- CRISIS MODE TEST (Zone 14 Wari — highest density) ---")
    normal = mobility_ai.analyze_zone_mobility(14, crisis_mode=False)
    crisis = mobility_ai.analyze_zone_mobility(14, crisis_mode=True)
    print(f"Normal: score={normal['mobility_score']:>5.1f}  "
          f"clusters={normal['cluster_count']}  "
          f"pattern={normal['pattern']}")
    print(f"Crisis: score={crisis['mobility_score']:>5.1f}  "
          f"clusters={crisis['cluster_count']}  "
          f"pattern={crisis['pattern']}")

    print("\n--- DENSITY ADAPTATION TEST ---")
    diabari  = mobility_ai.analyze_zone_mobility(6)
    farmgate = mobility_ai.analyze_zone_mobility(5)
    wari     = mobility_ai.analyze_zone_mobility(14)
    print(f"Low    density — Diabari  : score={diabari['mobility_score']:>5.1f}  "
          f"clusters={diabari['cluster_count']}")
    print(f"High   density — Farmgate : score={farmgate['mobility_score']:>5.1f}  "
          f"clusters={farmgate['cluster_count']}")
    print(f"V.High density — Wari     : score={wari['mobility_score']:>5.1f}  "
          f"clusters={wari['cluster_count']}")

    print("\nENGINE STATUS:")
    for key, val in mobility_ai.get_engine_status().items():
        print(f"  {key}: {val}")
    print("=" * 85)