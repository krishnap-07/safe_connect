from typing import Tuple
import pandas as pd
import joblib
import os
import sys
sys.path.insert(
    0, r"D:\SAFE_ROUTE (Disaster_management)\SAFE_ROUTE (Disaster_management)\SAFE_CONNECT\.venv311\Lib\site-packages")

# Global variable to hold the loaded model
_rf_pipeline = None


def load_severity_model():
    """Loads the pre-trained Random Forest model."""
    global _rf_pipeline
    if _rf_pipeline is None:
        model_path = os.path.join("models", "severity_rf_model.pkl")
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Severity model not found at {model_path}. Please run train_severity_model.py first.")
        _rf_pipeline = joblib.load(model_path)
    return _rf_pipeline


def _severity_from_score(score: int) -> str:
    """Converts a 0-100 score into a string priority label."""
    if score >= 80:
        return "CRITICAL"
    elif score >= 50:
        return "HIGH"
    elif score >= 30:
        return "MEDIUM"
    return "LOW"


def predict_severity(report_text: str, disaster_type: str, human_count: int, damage_level: str) -> Tuple[str, int]:
    """
    Feeds real-time incident data into the Random Forest model to predict severity.

    Returns:
        Tuple[str, int]: (Severity Label, Severity Score 0-100)
    """
    model = load_severity_model()

    # Create a DataFrame for a single inference request
    # Scikit-learn Pipelines expect DataFrame columns to match training features exactly
    input_data = pd.DataFrame([{
        "report_text": report_text,
        "disaster_type": disaster_type,
        "human_count": human_count,
        "damage_level": damage_level or "Unknown"
    }])

    # Predict score
    predicted_score = float(model.predict(input_data)[0])

    # Cap between 0 and 100 just in case
    predicted_score = max(0, min(100, int(round(predicted_score))))

    priority_label = _severity_from_score(predicted_score)

    return priority_label, predicted_score
