from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
# This is required so your React app (localhost:3000) can talk to Flask (localhost:5000)
CORS(app) 

@app.route('/api/risk-status', methods=['GET'])
def get_risk_status():
    # This data simulates what your AI models will eventually produce
    return jsonify({
        "mobility_anomaly": "84%",
        "wastewater_load": "Detected",
        "social_index": "High",
        "zones": [
            {"id": 1, "name": "NSU Campus", "coords": [23.8191, 90.4526], "risk": 0.85, "color": "red"},
            {"id": 2, "name": "Banani", "coords": [23.7940, 90.4043], "risk": 0.45, "color": "orange"},
            {"id": 3, "name": "Uttara", "coords": [23.8759, 90.3795], "risk": 0.20, "color": "green"}
        ]
    })

if __name__ == '__main__':
    # Running on port 5000
    app.run(debug=True, port=5000)