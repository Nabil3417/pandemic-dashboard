from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import json
import random
import numpy as np
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
import time

# ─── T-08: LOAD TRAINED FUSION CLASSIFIER ──────────────────────────────────
_fusion_classifier = None
_fusion_scaler = None
_fusion_feature_importances = {}
_fusion_model_info = {}

def _load_fusion_classifier():
    """
    T-08 — Load the trained GradientBoosting fusion classifier + scaler.
    Falls back gracefully if model files are not found (uses fixed weights).
    """
    global _fusion_classifier, _fusion_scaler, _fusion_feature_importances, _fusion_model_info

    model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')
    classifier_path = os.path.join(model_dir, 'fusion_classifier.pkl')
    scaler_path = os.path.join(model_dir, 'fusion_scaler.pkl')
    results_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 'data', 'fusion_training_results.json')

    if not os.path.exists(classifier_path):
        print("⚠️  Fusion classifier not found — using fixed-weight fallback")
        return False

    try:
        import joblib
        _fusion_classifier = joblib.load(classifier_path)
        _fusion_scaler = joblib.load(scaler_path)

        # Extract feature importances
        if hasattr(_fusion_classifier, 'feature_importances_'):
            _fusion_feature_importances = {
                "nlp_proxy":        round(float(_fusion_classifier.feature_importances_[0]), 4),
                "wastewater_proxy": round(float(_fusion_classifier.feature_importances_[1]), 4),
                "mobility_score":   round(float(_fusion_classifier.feature_importances_[2]), 4),
            }

        # Load training results for metadata
        if os.path.exists(results_path):
            with open(results_path, 'r') as f:
                _fusion_model_info = json.load(f)

        print("✅ T-08: Fusion classifier loaded (GradientBoosting)")
        print(f"   Feature importances: NLP={_fusion_feature_importances.get('nlp_proxy',0):.4f}, "
              f"SymptomSearch={_fusion_feature_importances.get('wastewater_proxy',0):.4f}, "
              f"Mobility={_fusion_feature_importances.get('mobility_score',0):.4f}")
        return True
    except Exception as e:
        print(f"⚠️  Failed to load fusion classifier: {e} — using fixed-weight fallback")
        _fusion_classifier = None
        _fusion_scaler = None
        return False

# Load at startup — runs once when Flask starts
_fusion_loaded = _load_fusion_classifier()


# ─── PERFORMANCE CACHES ─────────────────────────────────────────────────
_risk_cache = {"data": None, "ts": 0}
RISK_CACHE_TTL = 300  # 5 minutes

_mobility_cache = {"data": None, "ts": 0}
MOBILITY_CACHE_TTL = 120  # 2 minutes

# Zone definitions now live here as the single source of truth.
ZONES = [
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
    Called on every /api/risk-status cache miss.
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


def _fuse_with_classifier(nlp_score, wastewater_score, mobility_score):
    """
    T-08 — Use trained GradientBoosting classifier to produce a fused risk score.
    Takes raw 0-100 signal values, scales them, runs predict_proba(outbreak),
    and converts the outbreak probability to a 0-100 risk score.

    Returns: (fused_score: float, method: str)
    """
    features = np.array([[nlp_score, wastewater_score, mobility_score]])
    scaled = _fusion_scaler.transform(features)

    # predict_proba returns [P(normal), P(outbreak)]
    proba = _fusion_classifier.predict_proba(scaled)[0]
    outbreak_prob = proba[1]  # probability of class 1 (outbreak)

    # Convert to 0-100 risk score
    fused_score = min(round(outbreak_prob * 100), 100)
    return fused_score, "gradient_boosting"


def calculate_multi_modal_risk(zone, crisis_mode):
    """
    T-08 — Fuses NLP, Mobility, and Symptom Search scores.
    Uses GradientBoosting classifier if available (trained in A-NEW-2),
    falls back to fixed-weight linear fusion otherwise.
    """
    # 1. NLP score — from real MongoDB posts or fallback
    nlp_score = get_nlp_score_for_zone(zone['id'], crisis_mode)

    # 2. Mobility anomaly — IsolationForest
    mobility_result = mobility_ai.analyze_zone_mobility(zone['id'], crisis_mode)
    is_anomaly      = mobility_result['is_anomaly']
    cluster_size    = mobility_result['cluster_size']
    mobility_score  = mobility_result['mobility_score']

    # 3. Symptom Search (formerly "wastewater") — ARIMA on Google Trends
    bio_load = wastewater_ai.get_localized_load(zone['id'], crisis_mode)

    # ── T-08: FUSION — Classifier or Fixed Weights ────────────────────
    if _fusion_classifier is not None:
        fused_score, fusion_method = _fuse_with_classifier(
            nlp_score, bio_load, mobility_score
        )
    else:
        # Legacy fixed-weight fusion (pre-T-08)
        fused_score = (nlp_score * 0.25) + (bio_load * 0.40) + (mobility_score * 0.35)
        fused_score = min(round(fused_score), 100)
        fusion_method = "fixed_weights"

    final_score = fused_score

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

    return final_score, risk, color, nlp_score, is_anomaly, bio_load, fusion_method


# ─────────────────────────────────────────────
# API ENDPOINTS
# ─────────────────────────────────────────────

@app.route('/')
def home():
    return jsonify({
        "status":         "System Online",
        "version":        "5.0.0",
        "fusion_method":  "gradient_boosting" if _fusion_classifier else "fixed_weights",
        "active_engines": [
            "BanglaBERT-NLP",
            "IsolationForest-Mobility",
            "SymptomSearch-ARIMA",
            "GradientBoosting-Fusion" if _fusion_classifier else "FixedWeight-Fusion",
            "MongoDB-Atlas"
        ]
    })


@app.route('/api/risk-status', methods=['GET'])
def get_risk_status():
    # Return cached result if fresh (Dashboard polls every 5s, cache now lasts 5 min)
    import threading
    now = time.time()
    if _risk_cache["data"] and (now - _risk_cache["ts"]) < RISK_CACHE_TTL:
        return jsonify(_risk_cache["data"])

    # Score unprocessed posts in background (non-blocking)
    threading.Thread(target=score_unprocessed_posts, daemon=True).start()

    processed_zones = []
    tactical_alerts = []

    for z in ZONES:
        score, risk, color, nlp, anomaly, bio, fusion_method = calculate_multi_modal_risk(
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

    # T-08: Determine which fusion method was used for ALL zones
    active_method = "gradient_boosting" if _fusion_classifier else "fixed_weights"

    result = {
        "mobility_anomaly":  82.1 if crisis_mode else 12.4,
        "wastewater_load":   94.5 if crisis_mode else 45.2,
        "social_index":      9.2  if crisis_mode else 8.4,
        "zones":             processed_zones,
        "alerts":            tactical_alerts,
        "crisis_active":     crisis_mode,
        # T-08: New fields
        "fusion_method":     active_method,
        "feature_importances": _fusion_feature_importances if _fusion_classifier else {
            "nlp_proxy": 0.25, "wastewater_proxy": 0.40, "mobility_score": 0.35
        },
    }
    _risk_cache["data"] = result
    _risk_cache["ts"] = time.time()
    return jsonify(result)


@app.route('/api/signals', methods=['GET'])
def get_signals():
    """
    Now reads REAL posts from MongoDB instead of hardcoded feed items.
    Falls back to hardcoded if MongoDB has no data yet.
    """
    all_signals = []

    for z in ZONES:
        real_posts = get_recent_posts_by_zone(z['id'], limit=3)

        if real_posts:
            for post in real_posts:
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
    _risk_cache["ts"] = 0  # invalidate cache so next request recalculates
    return jsonify({
        "status": "active" if crisis_mode else "nominal"
    })


@app.route('/api/forecast', methods=['GET'])
def get_forecast():
    """
    Returns 14-day ARIMA forecast for all zones.
    Symptom Search forecast: ARIMA on Google Trends series (engine_wastewater.py)
    Mobility forecast:   ARIMA on historical mobility CSV (engine_mobility.py)
    """
    from engine_mobility import get_zone_mobility_forecast

    forecast_results = []
    for z in ZONES:
        zone_id = z['id']
        wastewater_forecast = wastewater_ai.get_zone_forecast(zone_id, days=14)
        mobility_forecast   = get_zone_mobility_forecast(zone_id, days=14)

        days = []
        for i in range(14):
            wf = wastewater_forecast[i] if i < len(wastewater_forecast) else 30.0
            mf = mobility_forecast[i]   if i < len(mobility_forecast)   else 30.0

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
    """Shows what's in MongoDB."""
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


@app.route('/api/nlp-evaluation', methods=['GET'])
def get_nlp_evaluation():
    """Returns combined NLP evaluation results for PredictiveEngine.jsx panel."""
    _data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

    def _load(filename):
        try:
            with open(os.path.join(_data_dir, filename), 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    nlp_eval = _load('nlp_evaluation_results.json')
    finetuning = _load('finetuning_results.json')
    banglish_abl = _load('banglish_ablation.json')

    if nlp_eval is None:
        return jsonify({
            "status": "not_evaluated",
            "message": "Run: cd backend && python evaluate_nlp.py",
            "nlp_evaluation": None, "finetuning_results": None, "banglish_ablation": None
        })

    return jsonify({
        "status": "evaluated",
        "nlp_evaluation": nlp_eval,
        "finetuning_results": finetuning,
        "banglish_ablation": banglish_abl
    })


@app.route('/api/fusion-results', methods=['GET'])
def get_fusion_results():
    """Returns fusion classifier training results."""
    _path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data',
                         'fusion_training_results.json')
    try:
        with open(_path, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    except FileNotFoundError:
        return jsonify({"status": "not_trained", "message": "Run: cd backend && python train_fusion.py"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/fusion-info', methods=['GET'])
def get_fusion_info():
    """
    T-08 — Returns live fusion classifier status and feature importances.
    Used by the frontend to display the GB model panel.
    """
    info = {
        "active":          _fusion_classifier is not None,
        "method":          "gradient_boosting" if _fusion_classifier else "fixed_weights",
        "feature_importances": _fusion_feature_importances if _fusion_classifier else {
            "nlp_proxy": 0.25, "wastewater_proxy": 0.40, "mobility_score": 0.35
        },
    }

    if _fusion_classifier is not None and _fusion_model_info:
        best = _fusion_model_info.get('best_model', {})
        info["model_name"] = best.get('name', 'unknown')
        info["cv_f1_mean"] = best.get('cv_f1_mean', None)
        info["cv_f1_sd"] = best.get('cv_f1_sd', None)
        info["cv_auc_mean"] = best.get('cv_auc_mean', None)
        info["f1_improvement_over_baseline"] = best.get('f1_improvement_over_baseline', None)
        info["model_comparison"] = _fusion_model_info.get('model_comparison', [])

    return jsonify(info)


@app.route('/api/system-summary', methods=['GET'])
def get_system_summary():
    """Single endpoint with all key paper numbers."""
    _data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

    def _load(filename):
        try:
            with open(os.path.join(_data_dir, filename), 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    eval_res = _load('evaluation_results.json')
    nlp_eval = _load('nlp_evaluation_results.json')
    finetune = _load('finetuning_results.json')
    banglish = _load('banglish_ablation.json')
    fusion = _load('fusion_training_results.json')

    def _safe(obj, *keys, default=None):
        for k in keys:
            if obj is None: return default
            obj = obj.get(k, default) if isinstance(obj, dict) else default
        return obj

    return jsonify({
        "combined_f1": _safe(eval_res, 'combined_model', 'f1_score'),
        "combined_auc": _safe(eval_res, 'combined_model', 'roc_auc'),
        "nlp_base_f1": _safe(finetune, 'base_model', 'overall', 'f1'),
        "nlp_finetuned_f1": _safe(finetune, 'finetuned_model', 'overall', 'f1'),
        "nlp_evaluated_f1": _safe(nlp_eval, 'overall', 'f1'),
        "banglish_improvement": _safe(banglish, 'f1_improvement'),
        "fusion_improvement_over_baseline": _safe(fusion, 'best_model', 'f1_improvement_over_baseline'),
        "early_warning_avg_weeks": _safe(eval_res, 'early_warning', 'avg_lead_weeks'),
        "total_eval_weeks": _safe(eval_res, 'total_weeks', default=156),
        "languages_tested": 11,
        "train_samples": _safe(finetune, 'training_config', 'train_samples'),
        "test_samples": _safe(finetune, 'training_config', 'test_samples'),
        "fusion_trained": fusion is not None,
        "fusion_method": "gradient_boosting" if _fusion_classifier else "fixed_weights",
    })


# ─── COLLECTION MANAGEMENT ENDPOINTS ─────────────────────────────────────────

@app.route('/api/collection-status', methods=['GET'])
def get_collection_status():
    """Returns collection stats: last run, platform breakdown, recent count."""
    from scheduler import STATE_FILE
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
    from scheduler import job_social_media
    import threading
    thread = threading.Thread(target=job_social_media, daemon=True)
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


# ─── W-DZMI MOBILITY API (with cached MongoDB connection) ───────────────────
from routes.mobility_routes import mobility_bp
app.register_blueprint(mobility_bp)

# ─── AUTO SCHEDULER ────────────────────────────────────────────────────────
from scheduler import start_scheduler
start_scheduler()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)