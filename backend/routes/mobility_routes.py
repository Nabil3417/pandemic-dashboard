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
"""

from flask import Blueprint, jsonify, Response
import json as _json

mobility_bp = Blueprint("mobility", __name__)


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


# ── Endpoints ─────────────────────────────────────────────────────────────────

@mobility_bp.route("/api/mobility", methods=["GET"])
def get_all_mobility():
    """Get W-DZMI scores for all zones, sorted by score descending."""
    from data_collectors.mobility_repository import MobilityRepository

    repo = MobilityRepository()
    try:
        data = repo.api_mobility_detail()
        return _jsonify({
            "success": True,
            "data": data,
        })
    except Exception as e:
        return _jsonify({"success": False, "error": str(e)}, 500)
    finally:
        repo.close()


@mobility_bp.route("/api/mobility/<int:zone_id>", methods=["GET"])
def get_mobility_detail(zone_id):
    """Get detailed W-DZMI for a single zone + history + neighbors."""
    from data_collectors.mobility_repository import MobilityRepository

    repo = MobilityRepository()
    try:
        data = repo.api_mobility_detail(zone_id=zone_id)
        if isinstance(data, tuple) and len(data) == 2:
            # Error case (404)
            return _jsonify({"success": False, "error": f"Zone {zone_id} not found"}, 404)
        return _jsonify({
            "success": True,
            "data": data,
        })
    except Exception as e:
        return _jsonify({"success": False, "error": str(e)}, 500)
    finally:
        repo.close()


@mobility_bp.route("/api/mobility/risk", methods=["GET"])
def get_risk_overview():
    """Get risk distribution and summary stats."""
    from data_collectors.mobility_repository import MobilityRepository

    repo = MobilityRepository()
    try:
        data = repo.api_risk_status()
        return _jsonify({
            "success": True,
            "data": data,
        })
    except Exception as e:
        return _jsonify({"success": False, "error": str(e)}, 500)
    finally:
        repo.close()


@mobility_bp.route("/api/mobility/ranking", methods=["GET"])
def get_mobility_ranking():
    """Get top and bottom zones by W-DZMI score."""
    from flask import request
    from data_collectors.mobility_repository import MobilityRepository

    repo = MobilityRepository()
    try:
        n = request.args.get("n", 5, type=int)
        n = min(n, 15)  # Cap at 15

        top = repo.get_top_zones(n)
        bottom = repo.get_bottom_zones(n)
        summary = repo.get_risk_summary()

        return _jsonify({
            "success": True,
            "data": {
                "top_zones": top,
                "bottom_zones": bottom,
                "risk_distribution": summary,
                "total_zones": 15,
            },
        })
    except Exception as e:
        return _jsonify({"success": False, "error": str(e)}, 500)
    finally:
        repo.close()


@mobility_bp.route("/api/mobility/signals/<int:zone_id>", methods=["GET"])
def get_signal_breakdown(zone_id):
    """Get individual signal scores for a zone (for radar/breakdown charts)."""
    from data_collectors.mobility_repository import MobilityRepository

    repo = MobilityRepository()
    try:
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
    finally:
        repo.close()


@mobility_bp.route("/api/mobility/history/<int:zone_id>", methods=["GET"])
def get_zone_history(zone_id):
    """Get W-DZMI history for a zone (for trend charts)."""
    from flask import request
    from data_collectors.mobility_repository import MobilityRepository

    repo = MobilityRepository()
    try:
        days = request.args.get("days", 14, type=int)
        days = min(days, 90)  # Cap at 90 days

        history = repo.get_zone_history(zone_id, days=days)

        return _jsonify({
            "success": True,
            "data": {
                "zone_id": zone_id,
                "days": days,
                "history": history,
                "count": len(history),
            },
        })
    except Exception as e:
        return _jsonify({"success": False, "error": str(e)}, 500)
    finally:
        repo.close()