# backend/engine_bert.py
from transformers import pipeline
import torch

class BertInferenceEngine:
    def __init__(self):
        # Using distilbert: fast, lightweight, and perfect for real-time dashboards
        self.device = 0 if torch.cuda.is_available() else -1
        print(f"--- Initializing BERT Engine on {'GPU' if self.device == 0 else 'CPU'} ---")
        
        # This model is pre-trained to understand sentiment and urgency
        self.classifier = pipeline(
            "sentiment-analysis", 
            model="distilbert-base-uncased-finetuned-sst-2-english",
            device=self.device
        )

    def analyze_text_signals(self, text):
        """
        Actually processes text through BERT and returns a 0-100 risk score.
        """
        try:
            result = self.classifier(text)[0]
            label = result['label']
            confidence = result['score']

            # Logic: Negative sentiment in a medical context = High Risk
            if label == "NEGATIVE":
                # Convert confidence to a high-range risk score (70-100)
                return round(70 + (confidence * 30), 2)
            else:
                # Positive/Neutral sentiment = Low-range risk score (0-40)
                return round(confidence * 40, 2)
        except Exception as e:
            print(f"BERT Inference Error: {e}")
            return 20.0  # Default neutral score on error

# Singleton instance to be used by app.py
engine = BertInferenceEngine()