import os
"""
Mobility Repository — Data Access Layer for W-DZMI
====================================================
Clean interface for Flask API endpoints to query W-DZMI data
from MongoDB. Import this in your Flask routes.

Usage in Flask:
    from data_collectors.mobility_repository import MobilityRepository
    repo = MobilityRepository()
    results = repo.get_all_zones()
"""

from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI")


class MobilityRepository:
    def __init__(self):
        self.client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
        self.db = self.client["bioguard_research"]

    def close(self):
        self.client.close()

    # ── Core Queries ────────────────────────────────────────────────────

    def get_all_zones(self):
        """Get latest W-DZMI for all zones, sorted by score desc."""
        return list(
            self.db["wdzmi_results"]
            .find({}, {"_id": 0})
            .sort("wdzmi_score", -1)
        )

    def get_zone(self, zone_id):
        """Get latest W-DZMI for a single zone."""
        return self.db["wdzmi_results"].find_one(
            {"zone_id": zone_id}, {"_id": 0}
        )

    def get_zone_history(self, zone_id, days=30):
        """Get daily W-DZMI history for a zone (last N days)."""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        docs = list(
            self.db["wdzmi_history"]
            .find(
                {"zone_id": zone_id, "timestamp": {"$gte": since}},
                {"_id": 0}
            )
            .sort("timestamp", 1)  # chronological order for charts
        )
        return docs

    def get_risk_summary(self):
        """Get risk-level distribution across all zones."""
        summary = {"critical": 0, "high": 0, "moderate": 0, "low": 0, "minimal": 0}
        for doc in self.get_all_zones():
            level = doc.get("risk_level", "minimal")
            if level in summary:
                summary[level] += 1
        return summary

    def get_summary_stats(self):
        """Get global W-DZMI summary statistics."""
        doc = self.db["wdzmi_summary"].find_one(
            {"type": "latest"}, {"_id": 0}
        )
        return doc

    # ── Signal Detail Queries ───────────────────────────────────────────

    def get_signal_detail(self, zone_id):
        """
        Get all 4 individual signal scores for a zone.
        Returns a dict with signal names as keys, each containing
        score, confidence, and trend.
        """
        zone = self.get_zone(zone_id)
        if not zone:
            return None
        return zone.get("signal_breakdown", {})

    def get_zone_neighbors(self, zone_id, zones_json_path="data/zones.json"):
        """Get W-DZMI scores for a zone and its neighbors."""
        import json
        from pathlib import Path

        zones_file = Path(__file__).resolve().parent.parent / zones_json_path
        with open(zones_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        zone_data = data["zones"]
        zone_key = str(zone_id)
        if zone_key not in zone_data:
            return []

        neighbor_ids = zone_data[zone_key].get("neighbors", [])
        # Include the zone itself + neighbors
        all_ids = [zone_id] + neighbor_ids

        results = list(
            self.db["wdzmi_results"]
            .find({"zone_id": {"$in": all_ids}}, {"_id": 0})
            .sort("wdzmi_score", -1)
        )
        return results

    # ── Comparison / Trend Queries ──────────────────────────────────────

    def get_top_zones(self, n=5):
        """Get top N zones by W-DZMI score."""
        return list(
            self.db["wdzmi_results"]
            .find({}, {"_id": 0})
            .sort("wdzmi_score", -1)
            .limit(n)
        )

    def get_bottom_zones(self, n=5):
        """Get bottom N zones by W-DZMI score."""
        return list(
            self.db["wdzmi_results"]
            .find({}, {"_id": 0})
            .sort("wdzmi_score", 1)
            .limit(n)
        )

    def get_zones_by_risk(self, risk_level):
        """Get all zones at a specific risk level."""
        return list(
            self.db["wdzmi_results"]
            .find({"risk_level": risk_level}, {"_id": 0})
            .sort("wdzmi_score", -1)
        )

    def get_last_updated(self):
        """Get the timestamp of the last W-DZMI calculation."""
        summary = self.get_summary_stats()
        if summary:
            return summary.get("timestamp")
        # Fallback: check latest history record
        latest = self.db["wdzmi_history"].find_one(
            {}, {"_id": 0, "timestamp": 1}, sort=[("timestamp", -1)]
        )
        return latest.get("timestamp") if latest else None

    # ── Flask-Ready Response Builders ───────────────────────────────────

    def api_mobility_detail(self, zone_id=None):
        """
        Build the response dict for /api/mobility-detail endpoint.
        If zone_id is None, returns all zones summary.
        If zone_id is provided, returns detailed breakdown for that zone.
        """
        if zone_id is not None:
            zone = self.get_zone(zone_id)
            if not zone:
                return {"error": f"Zone {zone_id} not found"}, 404

            history = self.get_zone_history(zone_id, days=14)
            neighbors = self.get_zone_neighbors(zone_id)

            return {
                "zone": zone,
                "history": history,
                "neighbors": neighbors,
                "last_updated": self.get_last_updated(),
            }
        else:
            zones = self.get_all_zones()
            summary = self.get_risk_summary()
            stats = self.get_summary_stats()

            return {
                "zones": zones,
                "risk_summary": summary,
                "stats": stats,
                "last_updated": self.get_last_updated(),
            }

    def api_risk_status(self):
        """
        Build the response dict for /api/risk-status endpoint.
        Returns a compact risk overview suitable for the main dashboard.
        """
        zones = self.get_all_zones()
        summary = self.get_risk_summary()
        stats = self.get_summary_stats()

        return {
            "mobility_module": "wdzmi",
            "total_zones": len(zones),
            "risk_distribution": summary,
            "avg_score": stats.get("avg_score", 0) if stats else 0,
            "max_score": stats.get("max_score", 0) if stats else 0,
            "min_score": stats.get("min_score", 0) if stats else 0,
            "top_zones": zones[:3],
            "bottom_zones": zones[-3:],
            "last_updated": self.get_last_updated(),
        }


# ── Quick Test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  Mobility Repository — Quick Test")
    print("=" * 60)

    repo = MobilityRepository()
    print("  Connected to MongoDB Atlas!")

    # Test 1: All zones
    zones = repo.get_all_zones()
    print(f"\n  Test 1 — get_all_zones(): {len(zones)} zones returned")
    for z in zones[:3]:
        print(f"    Zone {z['zone_id']}: {z['zone_name']} = {z['wdzmi_score']}")

    # Test 2: Single zone
    zone = repo.get_zone(15)
    print(f"\n  Test 2 — get_zone(15): {zone['zone_name']} = {zone['wdzmi_score']}")

    # Test 3: Risk summary
    summary = repo.get_risk_summary()
    print(f"\n  Test 3 — get_risk_summary(): {summary}")

    # Test 4: Summary stats
    stats = repo.get_summary_stats()
    if stats:
        print(f"\n  Test 4 — get_summary_stats(): avg={stats['avg_score']}, max={stats['max_score']}")

    # Test 5: Signal detail
    detail = repo.get_signal_detail(15)
    print(f"\n  Test 5 — get_signal_detail(15): {len(detail)} signals")
    for sig_name, sig_info in detail.items():
        print(f"    {sig_name}: score={sig_info['score']}, weight={sig_info['weight']}, contrib={sig_info['contribution']}")

    # Test 6: Neighbors
    neighbors = repo.get_zone_neighbors(15)
    print(f"\n  Test 6 — get_zone_neighbors(15): {len(neighbors)} zones (self + neighbors)")

    # Test 7: API responses
    api_all = repo.api_mobility_detail()
    print(f"\n  Test 7 — api_mobility_detail(): {len(api_all['zones'])} zones, keys={list(api_all.keys())}")

    api_zone = repo.api_mobility_detail(zone_id=15)
    print(f"  Test 8 — api_mobility_detail(15): {api_zone['zone']['zone_name']}, {len(api_zone.get('neighbors', []))} neighbors")

    risk = repo.api_risk_status()
    print(f"  Test 9 — api_risk_status(): avg={risk['avg_score']}, top={risk['top_zones'][0]['zone_name']}")

    repo.close()
    print("\n  All tests passed!")
    print("=" * 60)