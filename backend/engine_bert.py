# backend/engine_bert.py
def analyze_text_signals(text):
    """
    Simulates BERT processing. 
    In a full production app, you'd load a HuggingFace transformer here.
    """
    risk_keywords = {
        "fever": 15, "outbreak": 30, "hospital": 10, 
        "shortage": 20, "emergency": 25, "cough": 10
    }
    
    score = 0
    words = text.lower().split()
    for word, weight in risk_keywords.items():
        if word in words:
            score += weight
            
    return min(score, 100) # Ensure it doesn't exceed 100%