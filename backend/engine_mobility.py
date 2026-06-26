# backend/engine_mobility.py
import numpy as np
from sklearn.ensemble import IsolationForest

class MobilityEngine:
    def __init__(self):
        # contamination=0.1 assumes 10% of data might be outliers
        self.model = IsolationForest(contamination=0.1, random_state=42)
        
        # Simulating historical 'Normal' GPS pings for training
        # Centered around Dhaka coordinates
        self.history = np.random.normal(loc=23.8, scale=0.01, size=(100, 2)) 
        self.model.fit(self.history)

    def detect_anomaly(self, lat, lng):
        """
        Predicts if a current coordinate is an outlier
        Returns True for Anomaly, False for Normal
        """
        current_coord = np.array([[lat, lng]])
        prediction = self.model.predict(current_coord)
        
        # Isolation Forest returns -1 for anomalies
        return True if prediction[0] == -1 else False

# Create the instance that app.py is looking for
mobility_ai = MobilityEngine()