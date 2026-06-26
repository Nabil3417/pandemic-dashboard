# backend/engine_wastewater.py
import random

class WastewaterEngine:
    def __init__(self):
        # Base concentration of viral RNA in sewage (copies/mL)
        self.baseline_concentration = 45.0 

    def get_localized_load(self, zone_id, crisis_mode):
        """
        Simulates PCR-detected viral load in sewage.
        Wastewater often spikes 4-7 days BEFORE clinical symptoms appear.
        """
        if crisis_mode:
            # Simulate an exponential spike (Outbreak scenario)
            return round(random.uniform(85.0, 99.9), 2)
        
        # High-density zones like Bashundhara (ID: 1) might have slightly higher base loads
        if zone_id == 1:
            return round(random.uniform(50.0, 65.0), 2)
        
        # Normal/Low activity
        return round(random.uniform(10.0, 35.0), 2)

# Create the instance that app.py is looking for
wastewater_ai = WastewaterEngine()