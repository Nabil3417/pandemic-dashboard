# backend/engine_alerts.py

class AlertSystem:
    def generate_summary(self, city, scores):
        """
        Analyzes multimodal scores and generates a tactical summary.
        """
        nlp = scores.get('nlp', 0)
        mobility = scores.get('mobility_anomaly', False)
        bio = scores.get('wastewater', 0)
        final = scores.get('final', 0)

        if final < 40:
            return f"Condition Nominal: {city} showing baseline biological and social metrics."

        reasons = []
        if bio > 70: reasons.append("a significant Wastewater viral spike")
        if nlp > 70: reasons.append("critical social media symptom reports")
        if mobility: reasons.append("unusual crowd clustering (Spatial Anomaly)")

        reason_text = " and ".join(reasons) if reasons else "elevated risk markers"
        
        if final > 75:
            return f"URGENT: High risk detected in {city} due to {reason_text}. Immediate clinical validation recommended."
        else:
            return f"CAUTION: Increasing risk in {city}. Monitoring {reason_text}."

alert_engine = AlertSystem()