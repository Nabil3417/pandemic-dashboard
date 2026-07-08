"""
Mobility API Routes — Flask Blueprint for W-DZMI endpoints
===========================================================
Plug into app.py with:
    from routes.mobility_routes import mobility_bp
    app.register_blueprint(mobility_bp)

Endpoints:
  GET /api/mobility              — All zones W-DZMI summary
  GET /api/mobility/<zone_id>    — Single zone detail + history + neighbors
  GET /api/mobility/risk         — Risk distribution overview
  GET /api/mobility/ranking      — Top/bottom N zones
  GET /api/mobility/signals/<zone_id>  — Signal breakdown for a zone
  GET /api/mobility/history/<zone_id>  — Zone W-DZMI history
  GET /api/mobility/history-batch     — Batch history for multiple zones
"""

from flask import Blueprint, jsonify, Response, request
import json as _json
import time

mobility_bp = Blueprint("mobility", __name__)


# ── Cached MongoDB Connection ────────────────────────────────────────────
# Reuse a single MongoClient instead of creating one per request.
# This avoids 1-2s TCP handshake to MongoDB Atlas on every call.
_repo = None
_repo_ts = 0
_REPO_TTL = 300  # recreate connection every 5 min to stay fresh


def _get_repo():
    global _repo, _repo_ts
    now = time.time()
    if _repo is None or (now - _repo_ts) > _REPO_TTL:
        from data_collectors.mobility_repository import MobilityRepository
        _repo = MobilityRepository()
        _repo_ts = now
    return _repo


# ── Helper ────────────────────────────────────────────────────────────────────
def _jsonify(data, status=200):
    """Convert datetime objects for JSON serialization."""
    import datetime

    def _serialize(obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    return Response(
        _json.dumps(data, default=_serialize),
        mimetype="application/json",
        status=status,
    )


# ── In-memory cache for /api/mobility ─────────────────────────────────────
_mobility_cache = {"data": None, "ts": 0}
_MOBILITY_CACHE_TTL = 120  # 2 minutes — W-DZMI doesn't change every second


# ── Endpoints ─────────────────────────────────────────────────────────────────

@mobility_bp.route("/api/mobility", methods=["GET"])
def get_all_mobility():
    """Get W-DZMI scores for all zones, sorted by score descending. (Cached)"""
    now = time.time()
    if _mobility_cache["data"] and (now - _mobility_cache["ts"]) < _MOBILITY_CACHE_TTL:
        return _jsonify(_mobility_cache["data"])

    try:
        repo = _get_repo()
        data = repo.api_mobility_detail()
        result = {"success": True, "data": data}
        _mobility_cache["data"] = result
        _mobility_cache["ts"] = now
        return _jsonify(result)
    except Exception as e:
        return _jsonify({"success": False, "error": str(e)}, 500)


@mobility_bp.route("/api/mobility/<int:zone_id>", methods=["GET"])
def get_mobility_detail(zone_id):
    """Get detailed W-DZMI for a single zone + history + neighbors."""
    try:
        repo = _get_repo()
        data = repo.api_mobility_detail(zone_id=zone_id)
        if isinstance(data, tuple) and len(data) == 2:
            return _jsonify({"success": False, "error": f"Zone {zone_id} not found"}, 404)
        return _jsonify({"success": True, "data": data})
    except Exception as e:
        return _jsonify({"success": False, "error": str(e)}, 500)


@mobility_bp.route("/api/mobility/risk", methods=["GET"])
def get_risk_overview():
    """Get risk distribution and summary stats."""
    try:
        repo = _get_repo()
        data = repo.api_risk_status()
        return _jsonify({"success": True, "data": data})
    except Exception as e:
        return _jsonify({"success": False, "error": str(e)}, 500)


# Cache for /api/mobility/ranking
_ranking_cache = {"data": None, "ts": 0}
_RANKING_CACHE_TTL = 120  # 2 minutes


@mobility_bp.route("/api/mobility/ranking", methods=["GET"])
def get_mobility_ranking():
    """Get top and bottom zones by W-DZMI score. (Cached)"""
    now = time.time()
    cache_key = request.args.get("n", "5")
    if _ranking_cache["data"] and _ranking_cache["ts"] and (now - _ranking_cache["ts"]) < _RANKING_CACHE_TTL and _ranking_cache.get("key") == cache_key:
        return _jsonify(_ranking_cache["data"])

    try:
        repo = _get_repo()
        n = request.args.get("n", 5, type=int)
        n = min(n, 15)

        top = repo.get_top_zones(n)
        bottom = repo.get_bottom_zones(n)
        summary = repo.get_risk_summary()

        result = {
            "success": True,
            "data": {
                "top_zones": top,
                "bottom_zones": bottom,
                "risk_distribution": summary,
                "total_zones": 15,
            },
        }
        _ranking_cache["data"] = result
        _ranking_cache["ts"] = now
        _ranking_cache["key"] = cache_key
        return _jsonify(result)
    except Exception as e:
        return _jsonify({"success": False, "error": str(e)}, 500)


@mobility_bp.route("/api/mobility/signals/<int:zone_id>", methods=["GET"])
def get_signal_breakdown(zone_id):
    """Get individual signal scores for a zone (for radar/breakdown charts)."""
    try:
        repo = _get_repo()
        zone = repo.get_zone(zone_id)
        if not zone:
            return _jsonify({"success": False, "error": f"Zone {zone_id} not found"}, 404)

        breakdown = repo.get_signal_detail(zone_id)

        return _jsonify({
            "success": True,
            "data": {
                "zone": {
                    "zone_id": zone["zone_id"],
                    "zone_name": zone["zone_name"],
                    "wdzmi_score": zone["wdzmi_score"],
                    "confidence": zone["confidence"],
                    "trend": zone["trend"],
                    "risk_level": zone["risk_level"],
                    "num_signals": zone["num_signals"],
                },
                "signals": breakdown,
            },
        })
    except Exception as e:
        return _jsonify({"success": False, "error": str(e)}, 500)


# Cache for history endpoints — avoids repeated MongoDB queries
_history_cache = {"data": {}, "ts": 0}
_HISTORY_CACHE_TTL = 120  # 2 minutes


@mobility_bp.route("/api/mobility/history/<int:zone_id>", methods=["GET"])
def get_zone_history(zone_id):
    """Get W-DZMI history for a zone (for trend charts)."""
    now = time.time()
    cache_key = f"{zone_id}"

    # Refresh all history cache if TTL expired
    if (now - _history_cache["ts"]) > _HISTORY_CACHE_TTL:
        _history_cache["data"] = {}
        _history_cache["ts"] = now

    if cache_key in _history_cache["data"]:
        return _jsonify(_history_cache["data"][cache_key])

    try:
        repo = _get_repo()
        days = request.args.get("days", 7, type=int)
        days = min(days, 90)

        history = repo.get_zone_history(zone_id, days=days)

        result = {
            "success": True,
            "data": {
                "zone_id": zone_id,
                "days": days,
                "history": history,
                "count": len(history),
            },
        }
        _history_cache["data"][cache_key] = result
        return _jsonify(result)
    except Exception as e:
        return _jsonify({"success": False, "error": str(e)}, 500)


@mobility_bp.route("/api/mobility/history-batch", methods=["GET"])
def get_zone_history_batch():
    """
    Batch endpoint — get W-DZMI history for multiple zones in ONE request.
    Query: ?zones=1,2,3,4,5&days=7
    Avoids 15 separate HTTP round-trips from the frontend.
    """
    now = time.time()

    # Refresh all history cache if TTL expired
    if (now - _history_cache["ts"]) > _HISTORY_CACHE_TTL:
        _history_cache["data"] = {}
        _history_cache["ts"] = now

    try:
        zone_str = request.args.get("zones", "")
        days = request.args.get("days", 7, type=int)
        days = min(days, 90)

        zone_ids = [int(z.strip()) for z in zone_str.split(",") if z.strip().isdigit()]
        if not zone_ids:
            return _jsonify({"success": False, "error": "No valid zone IDs provided"}, 400)

        # Cap at 15 to prevent abuse
        zone_ids = zone_ids[:15]

        repo = _get_repo()
        results = {}

        for zid in zone_ids:
            # Check cache first
            if str(zid) in _history_cache["data"]:
                results[zid] = _history_cache["data"][str(zid)]
                continue

            history = repo.get_zone_history(zid, days=days)
            zone_result = {
                "success": True,
                "data": {
                    "zone_id": zid,
                    "days": days,
                    "history": history,
                    "count": len(history),
                },
            }
            _history_cache["data"][str(zid)] = zone_result
            results[zid] = zone_result

        return _jsonify({
            "success": True,
            "data": results,
            "cached_at": now,
        })
    except Exception as e:
        return _jsonify({"success": False, "error": str(e)}, 500)