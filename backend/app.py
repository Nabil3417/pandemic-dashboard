from flask import Flask, jsonify, request
from flask_cors import CORS
import random

# Import your AI Engines
from engine_bert import engine as bert_ai
from engine_mobility import mobility_ai
from engine_wastewater import wastewater_ai
from engine_alerts import alert_engine  # New Alert System

app = Flask(__name__)
CORS(app)

# Global State for Simulation
crisis_mode = False

# Database with geo-coordinates and initial signals
ZONES_DATABASE = [
    {
        "id": 1, 
        "city": "Bashundhara R/A", 
        "center": [23.8191, 90.4526], 
        "signal": "Emergency hospital shortage. High fever spikes.",
        "mobility": 88.5,
        "source_feeds": [
            {"id": 101, "type": "TWITTER", "text": "Pharmacies in Bashundhara are running out of flu meds!", "impact": "Critical"},
            {"id": 102, "type": "CLINIC", "text": "Apollo Hospital reporting 20% surge in ER admissions.", "impact": "High"}
        ]
    },
    {
        "id": 2, 
        "city": "Banani Hub", 
        "center": [23.7940, 90.4043], 
        "signal": "Normal traffic. No anomalous clusters.",
        "mobility": 42.1,
        "source_feeds": [
            {"id": 103, "type": "NEWS", "text": "Routine vaccination drive starts in Banani area.", "impact": "Low"}
        ]
    },
    {
        "id": 3, 
        "city": "Uttara Sector 4", 
        "center": [23.8759, 90.3795], 
        "signal": "Minor fever spike. Bio-markers stable.",
        "mobility": 12.4,
        "source_feeds": [
            {"id": 104, "type": "TWITTER", "text": "Uttara Sector 4 clinic had a long line this morning.", "impact": "Moderate"}
        ]
    }
]

def calculate_multi_modal_risk(zone, crisis_mode):
    """
    RESEARCH FUSION LOGIC: Fuses NLP, Mobility, and Bio-markers.
    """
    # 1. NLP Analysis (BERT)
    signal_text = "OUTBREAK ALERT: Rapid viral spread confirmed." if crisis_mode else zone['signal']
    nlp_score = bert_ai.analyze_text_signals(signal_text)
    
    # 2. Mobility Anomaly Analysis (Isolation Forest)
    lat, lng = zone['center']
    is_anomaly = mobility_ai.detect_anomaly(lat, lng)
    
    # 3. Wastewater Analysis (Biological)
    bio_load = wastewater_ai.get_localized_load(zone['id'], crisis_mode)
    
    # MULTI-MODAL WEIGHTED FUSION (Research Metric)
    fused_score = (nlp_score * 0.3) + (bio_load * 0.5)
    if is_anomaly:
        fused_score += 20
    
    final_score = min(fused_score, 100)
    
    # Risk Level Categorization
    if final_score > 70: return round(final_score), "CRITICAL", "#ef4444", nlp_score, is_anomaly, bio_load
    elif final_score > 40: return round(final_score), "MODERATE", "#f59e0b", nlp_score, is_anomaly, bio_load
    else: return round(final_score), "LOW", "#10b981", nlp_score, is_anomaly, bio_load

@app.route('/')
def home():
    return jsonify({
        "status": "System Online",
        "version": "3.2.0",
        "active_engines": ["BERT-NLP", "IsolationForest-Mobility", "Wastewater-Bio", "Tactical-Alerts"]
    })

@app.route('/api/risk-status', methods=['GET'])
def get_risk_status():
    processed_zones = []
    tactical_alerts = []
    
    for z in ZONES_DATABASE:
        # Get Scores and Categories
        score, risk, color, nlp, anomaly, bio = calculate_multi_modal_risk(z, crisis_mode)
        
        # Generate Tactical Text Summary for the UI
        summary = alert_engine.generate_summary(z['city'], {
            'nlp': nlp,
            'mobility_anomaly': anomaly,
            'wastewater': bio,
            'final': score
        })

        # Log alerts for anything above Moderate
        if score > 45:
            tactical_alerts.append({
                "id": f"alert-{z['id']}-{random.randint(100,999)}",
                "city": z['city'],
                "severity": risk,
                "message": summary
            })

        processed_zones.append({
            **z, 
            "score": score, 
            "risk": risk, 
            "color": color, 
            "summary": summary
        })
        
    return jsonify({
        "mobility_anomaly": 82.1 if crisis_mode else 12.4,
        "wastewater_load": 94.5 if crisis_mode else 45.2,
        "social_index": 9.2 if crisis_mode else 8.4,
        "zones": processed_zones,
        "alerts": tactical_alerts,
        "crisis_active": crisis_mode
    })

@app.route('/api/signals', methods=['GET'])
def get_signals():
    all_signals = []
    for z in ZONES_DATABASE:
        for feed in z['source_feeds']:
            text_content = "EMERGENCY: BERT detected rapid cluster growth!" if crisis_mode else feed['text']
            ai_score = bert_ai.analyze_text_signals(text_content)
            impact = "Critical" if ai_score > 75 else "High" if ai_score > 50 else "Low"
            
            all_signals.append({
                **feed,
                "text": text_content,
                "impact": impact,
                "city": z['city'],
                "ai_score": f"{round(ai_score)}%",
                "timestamp": "Just now" if crisis_mode else f"{random.randint(1, 10)}m ago"
            })
    return jsonify(all_signals)

@app.route('/api/simulate-crisis', methods=['POST'])
def toggle_crisis():
    global crisis_mode
    crisis_mode = not crisis_mode
    return jsonify({"status": "active" if crisis_mode else "nominal"})

@app.route('/api/forecast', methods=['GET'])
def get_forecast():
    forecast_results = []
    for z in ZONES_DATABASE:
        days = []
        base_score, _, _, _, _, _ = calculate_multi_modal_risk(z, crisis_mode)
        val = base_score
        multiplier = 1.18 if crisis_mode else 1.03
        for i in range(14):
            val = min(val * (multiplier + random.uniform(-0.02, 0.02)), 100)
            days.append({"day": f"D{i+1}", "val": round(val, 1)})
        forecast_results.append({"city": z['city'], "data": days})
    return jsonify(forecast_results)

if __name__ == '__main__':
    app.run(debug=True, port=5000)