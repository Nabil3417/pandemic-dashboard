from flask import Flask, jsonify, request
from flask_cors import CORS
import random

app = Flask(__name__)
CORS(app)

# Global State for Simulation
crisis_mode = False

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

def calculate_risk(signal_text, mobility_score):
    risk_keywords = ["emergency", "shortage", "fever", "spike", "outbreak", "critical"]
    base_score = sum(20 if word in signal_text.lower() else 0 for word in risk_keywords)
    final_score = min((base_score * 0.6) + (mobility_score * 0.4), 100)
    
    if final_score > 65: return round(final_score), "CRITICAL", "#ef4444"
    elif final_score > 35: return round(final_score), "MODERATE", "#f59e0b"
    else: return round(final_score), "LOW", "#10b981"

@app.route('/api/risk-status', methods=['GET'])
def get_risk_status():
    processed = []
    m_anomaly = 78.4 if crisis_mode else 12.4
    w_load = 92.1 if crisis_mode else 45.2
    
    for z in ZONES_DATABASE:
        current_mobility = min(z['mobility'] + 40, 99) if crisis_mode else z['mobility']
        current_signal = "OUTBREAK DETECTED: Rapid viral spread confirmed." if crisis_mode else z['signal']
        
        score, risk, color = calculate_risk(current_signal, current_mobility)
        processed.append({**z, "score": score, "risk": risk, "color": color, "mobility": current_mobility})
        
    return jsonify({
        "mobility_anomaly": m_anomaly,
        "wastewater_load": w_load,
        "social_index": 9.8 if crisis_mode else 8.4,
        "zones": processed,
        "crisis_active": crisis_mode
    })

# --- MISSING ROUTE ADDED BELOW ---
@app.route('/api/signals', methods=['GET'])
def get_signals():
    """Provides the raw intelligence feed for the Signal Intel page"""
    all_signals = []
    for z in ZONES_DATABASE:
        for feed in z['source_feeds']:
            # If crisis mode is on, we upgrade all impacts to Critical
            impact_level = "Critical" if crisis_mode else feed['impact']
            text_content = "EMERGENCY: BERT detected rapid cluster growth!" if crisis_mode else feed['text']
            
            all_signals.append({
                "id": feed['id'],
                "type": feed['type'],
                "text": text_content,
                "impact": impact_level,
                "city": z['city'],
                "timestamp": f"{random.randint(1, 10)}m ago"
            })
    return jsonify(all_signals)
# --------------------------------

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
        val = z['mobility']
        multiplier = 1.25 if crisis_mode else (1.12 if "shortage" in z['signal'].lower() else 1.01)
        for i in range(14):
            val = min(val * (multiplier + random.uniform(-0.02, 0.02)), 100)
            days.append({"day": f"D{i+1}", "val": round(val, 1)})
        forecast_results.append({"city": z['city'], "data": days})
    return jsonify(forecast_results)

if __name__ == '__main__':
    app.run(debug=True, port=5000)