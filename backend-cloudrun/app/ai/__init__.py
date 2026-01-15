"""AI module for anomaly detection, analysis, and prediction."""

from app.ai.anomaly_detection import (
    IsolationForestDetector,
    detect_anomalies,
    AnomalyResult,
    AnomalyType,
)
from app.ai.prediction import (
    NeuralProphetPredictor,
    ProphetPredictor,  # Backward compatibility alias
    TrendPredictor,    # Backward compatibility alias
    predict_trend,
    PredictionPoint,
    PredictionResult,
)

__all__ = [
    "IsolationForestDetector",
    "detect_anomalies",
    "AnomalyResult",
    "AnomalyType",
    "NeuralProphetPredictor",
    "ProphetPredictor",    # Backward compatibility
    "TrendPredictor",      # Backward compatibility
    "predict_trend",
    "PredictionPoint",
    "PredictionResult",
]
