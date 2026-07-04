from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import json
import random
from datetime import datetime

# AI Engines
from engine_bert import engine as bert_ai
from engine_mobility import mobility_ai
from engine_wastewater import wastewater_ai
from engine_alerts import alert_engine

# Database
from database import (
    social_posts,
    risk_snapshots,
    save_risk_snapshot,
    get_unprocessed_posts,
    update_post_bert_score,
    get_recent_posts_by_zone,
    get_zone_avg_bert_score
)

app = Flask(__name__)
CORS(app)

# Global crisis toggle
crisis_mode = False

# Zone definitions now live here as the single source of truth.
# In Week 2 we will move this into MongoDB zones_collection.
ZONES = [
    # ── DNCC Zones ──────────────────────────────────────────
    {
        "id": 1,
        "city": "Uttara",
        "area": "Uttara Sectors 1-14, Uttarkhan, Dakshinkhan, Khilkhet",
        "corporation": "DNCC",
        "center": [23.8759, 90.3795],
        "signal": "Monitoring residential sectors. Baseline activity.",
        "mobility": 45.0,
    },
    {
        "id": 2,
        "city": "Mirpur",
        "area": "Mirpur-1, Mirpur-2, Mirpur-10, Mirpur-11, Pallabi, Rupnagar",
        "corporation": "DNCC",
        "center": [23.8223, 90.3654],
        "signal": "High density residential zone. Normal signals.",
        "mobility": 52.0,
    },
    {
        "id": 3,
        "city": "Gulshan & Banani",
        "area": "Gulshan 1 & 2, Banani, Baridhara, Mohakhali, Tejgaon",
        "corporation": "DNCC",
        "center": [23.7940, 90.4043],
        "signal": "Commercial hub. Normal traffic patterns.",
        "mobility": 42.1,
    },
    {
        "id": 4,
        "city": "Agargaon & Kafrul",
        "area": "Agargaon, Shewrapara, Kazipara, Kafrul, Taltala",
        "corporation": "DNCC",
        "center": [23.7751, 90.3668],
        "signal": "Government zone. Stable biosignals.",
        "mobility": 38.0,
    },
    {
        "id": 5,
        "city": "Farmgate & Karwan Bazar",
        "area": "Farmgate, Kawran Bazar, Sher-e-Bangla Nagar",
        "corporation": "DNCC",
        "center": [23.7527, 90.3894],
        "signal": "High foot traffic commercial area.",
        "mobility": 67.0,
    },
    {
        "id": 6,
        "city": "Diabari & Ashkona",
        "area": "Diabari, Ashkona, Kawlar",
        "corporation": "DNCC",
        "center": [23.9012, 90.3456],
        "signal": "Peripheral zone. Low density signals.",
        "mobility": 22.0,
    },
    {
        "id": 7,
        "city": "Uttarkhan & Faidabad",
        "area": "Faidabad, Barua, Jamun",
        "corporation": "DNCC",
        "center": [23.9123, 90.4234],
        "signal": "Outskirts zone. Baseline monitoring.",
        "mobility": 18.0,
    },
    {
        "id": 8,
        "city": "Dakshinkhan & Dumni",
        "area": "Dumni, Satarkul",
        "corporation": "DNCC",
        "center": [23.8934, 90.4456],
        "signal": "Residential outskirts. Stable readings.",
        "mobility": 20.0,
    },
    {
        "id": 9,
        "city": "Vatara & Kuril",
        "area": "Vatara, Kuril, Nurerchala, Khilbaritech",
        "corporation": "DNCC",
        "center": [23.8234, 90.4234],
        "signal": "Mixed zone near Bashundhara. Monitoring.",
        "mobility": 35.0,
    },
    {
        "id": 10,
        "city": "Badda & Aftabnagar",
        "area": "Uttar Badda, Madhya Badda, Beraid, Aftabnagar",
        "corporation": "DNCC",
        "center": [23.7845, 90.4234],
        "signal": "Residential zone. Normal biosignals.",
        "mobility": 41.0,
    },
    # ── DSCC Zones ──────────────────────────────────────────
    {
        "id": 11,
        "city": "Ramna & Motijheel",
        "area": "Ramna, Motijheel, Paltan, Shahbagh, Segunbagicha",
        "corporation": "DSCC",
        "center": [23.7234, 90.4123],
        "signal": "Central business district. High mobility.",
        "mobility": 72.0,
    },
    {
        "id": 12,
        "city": "Khilgaon & Mugda",
        "area": "Khilgaon, Mugda, Basabo, Shantinagar, Malibagh",
        "corporation": "DSCC",
        "center": [23.7345, 90.4345],
        "signal": "Dense residential area. Monitoring active.",
        "mobility": 55.0,
    },
    {
        "id": 13,
        "city": "Dhanmondi & Azimpur",
        "area": "Dhanmondi, Lalbagh, Azimpur, Hazaribagh, Kalabagan",
        "corporation": "DSCC",
        "center": [23.7456, 90.3789],
        "signal": "Hospital cluster zone. High health activity.",
        "mobility": 60.0,
    },
    {
        "id": 14,
        "city": "Wari & Jatrabari",
        "area": "Wari, Sutrapur, Kotowali, Bangsal, Gendaria, Jatrabari",
        "corporation": "DSCC",
        "center": [23.7123, 90.4234],
        "signal": "Old Dhaka high density. Elevated baseline.",
        "mobility": 65.0,
    },
    # ── Special Research Zone ────────────────────────────────
    {
        "id": 15,
        "city": "Bashundhara R/A (NSU)",
        "area": "Bashundhara, Norda, North South University Campus",
        "corporation": "DNCC",
        "center": [23.8191, 90.4526],
        "signal": "Primary research zone. NSU campus monitoring.",
        "mobility": 88.5,
    },
]


# ─── DISEASE KEYWORDS (shared for health relevance scoring) ──────────────────
DISEASE_KEYWORDS = [
    'dengue', 'cholera', 'malaria', 'pneumonia', 'diarrhea',
    'outbreak', 'epidemic', 'pandemic', 'infection', 'virus',
    'infected', 'contagious', 'quarantine', 'mortality', 'pathogen',
    'fever', 'cough', 'respiratory', 'icu', 'admitted',
    'hospitalized', 'death toll', 'case count', 'symptoms',
    'patients', 'spread', 'transmission',
    'ডেঙ্গু', 'কলেরা', 'ম্যালেরিয়া', 'নিউমোনিয়া', 'ডায়রিয়া',
    'প্রাদুর্ভাব', 'মহামারী', 'সংক্রমণ', 'ভাইরাস', 'আক্রান্ত',
    'হাসপাতালে ভর্তি', 'মৃত্যুহার', 'শ্বাসকষ্ট', 'রোগতত্ত্ব',
    'হাম', 'রুবেলা', 'যক্ষ্মা', 'হেপাটাইটিস',
    'প্রকোপ', 'উপসর্গ', 'রোগী', 'মৃত্যু',
    'ভয়াবহ', 'সতর্ক', 'ক্রমবর্ধমান',
]


def health_relevance(text):
    """Returns multiplier 0.3-1.0 based on disease keyword density."""
    text_lower = text.lower()
    matches = sum(1 for kw in DISEASE_KEYWORDS if kw in text_lower)
    if matches >= 2:
        return 1.0
    elif matches >= 1:
        return 0.85
    else:
        return 0.3


def score_unprocessed_posts():
    """
    Finds posts in MongoDB that haven't been scored yet,
    runs BERT on them with health relevance multiplier, and writes the score back.
    Processes up to 50 per call.
    Called on every /api/risk-status request.
    """
    unprocessed = get_unprocessed_posts(limit=50)
    for post in unprocessed:
        raw_score = bert_ai.analyze_text_signals(post['text'])
        relevance = health_relevance(post['text'])
        final_score = round(raw_score * relevance, 1)
        update_post_bert_score(post['_id'], final_score)


def get_nlp_score_for_zone(zone_id, crisis_mode):
    """
    Gets NLP score for a zone.
    Priority: real MongoDB average → fallback to live BERT on crisis signal.
    """
    if crisis_mode:
        return bert_ai.analyze_text_signals(
            "OUTBREAK ALERT: Rapid viral spread confirmed. Hospitals overwhelmed."
        )

    # Try to get real average from MongoDB first
    avg = get_zone_avg_bert_score(zone_id)
    if avg is not None:
        return round(avg, 2)

    # Fallback — score the zone's default signal text
    zone = next((z for z in ZONES if z['id'] == zone_id), None)
    if zone:
        return bert_ai.analyze_text_signals(zone['signal'])
    return 20.0


def calculate_multi_modal_risk(zone, crisis_mode):
    """
    RESEARCH FUSION LOGIC — fuses NLP, Mobility, and Wastewater scores.
    Now reads NLP score from real MongoDB data where available.
    """
    # 1. NLP score — from real MongoDB posts or fallback
    nlp_score = get_nlp_score_for_zone(zone['id'], crisis_mode)

    # 2. Mobility anomaly — IsolationForest
    mobility_result = mobility_ai.analyze_zone_mobility(zone['id'], crisis_mode)
    is_anomaly      = mobility_result['is_anomaly']
    cluster_size    = mobility_result['cluster_size']
    mobility_score  = mobility_result['mobility_score']

    # 3. Wastewater viral load
    bio_load = wastewater_ai.get_localized_load(zone['id'], crisis_mode)

    # MULTI-MODAL WEIGHTED FUSION
    fused_score = (nlp_score * 0.25) + (bio_load * 0.40) + (mobility_score * 0.35)
    final_score = min(round(fused_score), 100)

    # Risk level
    if final_score > 70:
        risk, color = "CRITICAL", "#ef4444"
    elif final_score > 40:
        risk, color = "MODERATE", "#f59e0b"
    else:
        risk, color = "LOW", "#10b981"

    # Save snapshot to MongoDB every time we calculate
    save_risk_snapshot(
        zone_id=zone['id'],
        city=zone['city'],
        nlp_score=nlp_score,
        mobility_anomaly=is_anomaly,
        wastewater_score=bio_load,
        fused_score=final_score,
        risk_level=risk,
        cluster_size=cluster_size,
        mobility_score=mobility_score
    )

    return final_score, risk, color, nlp_score, is_anomaly, bio_load


# ─────────────────────────────────────────────
# API ENDPOINTS
# ─────────────────────────────────────────────

@app.route('/')
def home():
    return jsonify({
        "status":         "System Online",
        "version":        "4.0.0",
        "active_engines": [
            "BanglaBERT-NLP",
            "IsolationForest-Mobility",
            "Wastewater-ARIMA",
            "XGBoost-Fusion",
            "MongoDB-Atlas"
        ]
    })


@app.route('/api/risk-status', methods=['GET'])
def get_risk_status():
    # Score any unprocessed posts first
    score_unprocessed_posts()

    processed_zones = []
    tactical_alerts = []

    for z in ZONES:
        score, risk, color, nlp, anomaly, bio = calculate_multi_modal_risk(
            z, crisis_mode
        )

        summary = alert_engine.generate_summary(z['city'], {
            'nlp':              nlp,
            'mobility_anomaly': anomaly,
            'wastewater':       bio,
            'final':            score
        })

        if score > 45:
            tactical_alerts.append({
                "id":       f"alert-{z['id']}-{random.randint(100,999)}",
                "city":     z['city'],
                "severity": risk,
                "message":  summary
            })

        processed_zones.append({
            **z,
            "score":   score,
            "risk":    risk,
            "color":   color,
            "summary": summary
        })

    return jsonify({
        "mobility_anomaly": 82.1 if crisis_mode else 12.4,
        "wastewater_load":  94.5 if crisis_mode else 45.2,
        "social_index":     9.2  if crisis_mode else 8.4,
        "zones":            processed_zones,
        "alerts":           tactical_alerts,
        "crisis_active":    crisis_mode
    })


@app.route('/api/signals', methods=['GET'])
def get_signals():
    """
    Now reads REAL posts from MongoDB instead of hardcoded feed items.
    Falls back to hardcoded if MongoDB has no data yet.
    """
    all_signals = []

    for z in ZONES:
        # Get real posts from MongoDB for this zone
        real_posts = get_recent_posts_by_zone(z['id'], limit=3)

        if real_posts:
            for post in real_posts:
                # Use stored BERT score if available, else score live
                if post.get('bert_score') is not None:
                    ai_score = post['bert_score']
                else:
                    ai_score = bert_ai.analyze_text_signals(post['text'])

                text = "EMERGENCY: Rapid cluster growth detected!" \
                    if crisis_mode else post['text']

                impact = (
                    "Critical" if ai_score > 75 else
                    "High"     if ai_score > 50 else
                    "Low"
                )

                all_signals.append({
                    "id":        str(post['_id']),
                    "type":      post.get('platform', 'SOCIAL'),
                    "text":      text,
                    "impact":    impact,
                    "city":      z['city'],
                    "ai_score":  f"{round(ai_score)}%",
                    "timestamp": post['timestamp'].strftime("%Y-%m-%d %H:%M")
                                 if isinstance(post['timestamp'], datetime)
                                 else str(post['timestamp'])
                })
        else:
            # Fallback if no real data yet — use zone signal text
            ai_score = bert_ai.analyze_text_signals(z['signal'])
            impact = (
                "Critical" if ai_score > 75 else
                "High"     if ai_score > 50 else
                "Low"
            )
            all_signals.append({
                "id":        f"fallback-{z['id']}",
                "type":      "SYSTEM",
                "text":      z['signal'],
                "impact":    impact,
                "city":      z['city'],
                "ai_score":  f"{round(ai_score)}%",
                "timestamp": "No real data yet"
            })

    return jsonify(all_signals)


@app.route('/api/simulate-crisis', methods=['POST'])
def toggle_crisis():
    global crisis_mode
    crisis_mode = not crisis_mode
    return jsonify({
        "status": "active" if crisis_mode else "nominal"
    })


@app.route('/api/forecast', methods=['GET'])
def get_forecast():
    """
    Returns 14-day ARIMA forecast for all zones.
    Replaces fake random math with real model predictions.
    Wastewater forecast: ARIMA on Google Trends series (engine_wastewater.py)
    Mobility forecast:   ARIMA on historical mobility CSV (engine_mobility.py)
    """
    from engine_mobility import get_zone_mobility_forecast

    forecast_results = []
    for z in ZONES:
        zone_id = z['id']
        # Real ARIMA forecasts from both engines
        wastewater_forecast = wastewater_ai.get_zone_forecast(zone_id, days=14)
        mobility_forecast   = get_zone_mobility_forecast(zone_id, days=14)

        days = []
        for i in range(14):
            wf = wastewater_forecast[i] if i < len(wastewater_forecast) else 30.0
            mf = mobility_forecast[i]   if i < len(mobility_forecast)   else 30.0

            # Fused forecast score — same weights as risk calculation
            fused_val = round((wf * 0.7) + (mf * 0.3), 1)
            days.append({
                "day":              f"D{i+1}",
                "val":              fused_val,
                "wastewater_pred":  wf,
                "mobility_pred":    mf,
            })

        forecast_results.append({
            "city":    z['city'],
            "zone_id": zone_id,
            "data":    days,
        })

    return jsonify(forecast_results)


@app.route('/api/db-stats', methods=['GET'])
def get_db_stats():
    """
    Shows what's in MongoDB.
    Useful to verify data collection is working.
    """
    return jsonify({
        "total_posts":       social_posts.count_documents({}),
        "processed_posts":   social_posts.count_documents(
                                 {"bert_score": {"$ne": None}}
                             ),
        "unprocessed_posts": social_posts.count_documents(
                                 {"bert_score": None}
                             ),
        "total_snapshots":   risk_snapshots.count_documents({}),
        "simulated_posts":   social_posts.count_documents(
                                 {"simulated": True}
                             ),
        "real_posts":        social_posts.count_documents(
                                 {"simulated": {"$ne": True}}
                             ),
    })


@app.route('/api/engine-status', methods=['GET'])
def get_engine_status():
    return jsonify(bert_ai.get_engine_status())


@app.route('/api/evaluation-results', methods=['GET'])
def get_evaluation_results():
    """Returns pre-computed model evaluation metrics from evaluate.py output."""
    results_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'evaluation_results.json')
    try:
        with open(results_path, 'r') as f:
            results = json.load(f)
        return jsonify(results)
    except FileNotFoundError:
        return jsonify({
            "error": "evaluation_results.json not found — run python evaluate.py first"
        }), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── COLLECTION MANAGEMENT ENDPOINTS ─────────────────────────────────────────

@app.route('/api/collection-status', methods=['GET'])
def get_collection_status():
    """Returns collection stats: last run, platform breakdown, recent count."""
    from data_collectors.scheduler import STATE_FILE
    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        state = {"last_run": None}

    platform_pipeline = [
        {"$match": {"simulated": {"$ne": True}}},
        {"$group": {"_id": "$platform", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    platform_counts = {doc["_id"]: doc["count"] for doc in social_posts.aggregate(platform_pipeline)}

    from datetime import timedelta
    yesterday = datetime.now() - timedelta(hours=24)
    recent_count = social_posts.count_documents({
        "simulated": {"$ne": True},
        "timestamp": {"$gte": yesterday}
    })
    unprocessed = social_posts.count_documents({
        "simulated": {"$ne": True},
        "bert_score": None
    })

    return jsonify({
        "last_run": state.get("last_run"),
        "next_run_in_hours": 12,
        "total_posts": social_posts.count_documents({"simulated": {"$ne": True}}),
        "recent_24h": recent_count,
        "unprocessed": unprocessed,
        "platforms": platform_counts,
    })


@app.route('/api/trigger-collection', methods=['POST'])
def trigger_collection():
    """Triggers a full collection run in a background thread."""
    from data_collectors.scheduler import run_collection_job
    import threading
    thread = threading.Thread(target=run_collection_job, daemon=True)
    thread.start()
    return jsonify({"status": "started", "message": "Collection started in background."})


@app.route('/api/posts', methods=['GET'])
def get_posts():
    """Returns paginated posts with optional platform filter."""
    platform = request.args.get('platform', None)
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))

    query = {"simulated": {"$ne": True}}
    if platform and platform != "ALL":
        query["platform"] = platform

    posts = list(social_posts.find(
        query,
        sort=[("timestamp", -1)],
        skip=offset,
        limit=limit
    ))

    result = []
    for post in posts:
        result.append({
            "id": str(post["_id"]),
            "text": post["text"][:200] + ("..." if len(post["text"]) > 200 else ""),
            "platform": post.get("platform", "Unknown"),
            "channel": post.get("channel", ""),
            "zone_id": post.get("zone_id"),
            "location_name": post.get("location_name", ""),
            "bert_score": post.get("bert_score"),
            "timestamp": post["timestamp"].strftime("%Y-%m-%d %H:%M")
                         if isinstance(post["timestamp"], datetime)
                         else str(post["timestamp"]),
            "source_url": post.get("source_url", ""),
        })

    total = social_posts.count_documents(query)
    return jsonify({"posts": result, "total": total, "limit": limit, "offset": offset})


# ─── W-DZMI MOBILITY API ────────────────────────────────────────────────────
from routes.mobility_routes import mobility_bp
app.register_blueprint(mobility_bp)

# ─── AUTO SCHEDULER ────────────────────────────────────────────────────────
from data_collectors.scheduler import start_scheduler
start_scheduler()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)