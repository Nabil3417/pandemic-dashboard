from flask import Flask, jsonify, request
from flask_cors import CORS
import os
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


def score_unprocessed_posts():
    """
    Finds posts in MongoDB that haven't been scored yet,
    runs BERT on them, and writes the score back to the document.
    Called on every /api/risk-status request.
    """
    unprocessed = get_unprocessed_posts(limit=10)
    for post in unprocessed:
        score = bert_ai.analyze_text_signals(post['text'])
        update_post_bert_score(post['_id'], score)


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
    lat, lng = zone['center']
    mobility_result = mobility_ai.analyze_zone_mobility(zone['id'], crisis_mode)
    is_anomaly      = mobility_result['is_anomaly']
    cluster_size    = mobility_result['cluster_size']
    mobility_score  = mobility_result['mobility_score']
    # 3. Wastewater viral load
    bio_load = wastewater_ai.get_localized_load(zone['id'], crisis_mode)

    # MULTI-MODAL WEIGHTED FUSION
    fused_score = (nlp_score * 0.3) + (bio_load * 0.5) + (mobility_score * 0.2)
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
                "timestamp": "No real data yet — run simulator"
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
    forecast_results = []
    for z in ZONES:
        days = []
        base_score, _, _, _, _, _ = calculate_multi_modal_risk(z, crisis_mode)
        val = base_score
        multiplier = 1.18 if crisis_mode else 1.03
        for i in range(14):
            val = min(val * (multiplier + random.uniform(-0.02, 0.02)), 100)
            days.append({"day": f"D{i+1}", "val": round(val, 1)})
        forecast_results.append({"city": z['city'], "data": days})
    return jsonify(forecast_results)


@app.route('/api/db-stats', methods=['GET'])
def get_db_stats():
    """
    New endpoint — shows what's in your MongoDB.
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)