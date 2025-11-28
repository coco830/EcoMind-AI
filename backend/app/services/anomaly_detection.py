"""AI-based anomaly detection service using XGBoost."""

import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import structlog
from xgboost import XGBClassifier

from app.core.config import get_settings
from app.db.tdengine import get_tdengine_client

settings = get_settings()
logger = structlog.get_logger()


class AnomalyDetector:
    """XGBoost-based anomaly detector for environmental monitoring data."""

    def __init__(self, model_path: str | None = None) -> None:
        self.model: XGBClassifier | None = None
        self.model_path = model_path
        self.threshold = settings.anomaly_threshold
        self._is_trained = False

        if model_path and Path(model_path).exists():
            self._load_model(model_path)

    def _load_model(self, path: str) -> None:
        """Load pre-trained model from file."""
        try:
            with open(path, "rb") as f:
                self.model = pickle.load(f)
            self._is_trained = True
            logger.info("Anomaly detection model loaded", path=path)
        except Exception as e:
            logger.error("Failed to load model", path=path, error=str(e))

    def save_model(self, path: str) -> None:
        """Save trained model to file."""
        if self.model is None:
            raise ValueError("No model to save")
        with open(path, "wb") as f:
            pickle.dump(self.model, f)
        logger.info("Model saved", path=path)

    def _extract_features(self, data: list[dict[str, Any]]) -> np.ndarray:
        """Extract features from time-series data for anomaly detection.

        Features:
        - Current value
        - Rolling mean (last 5 points)
        - Rolling std (last 5 points)
        - Rate of change
        - Hour of day (cyclical)
        """
        if len(data) < 5:
            return np.array([])

        values = np.array([d["value"] for d in data])
        features = []

        for i in range(4, len(values)):
            window = values[max(0, i - 4) : i + 1]
            current = values[i]
            mean = np.mean(window)
            std = np.std(window) if len(window) > 1 else 0
            rate = (current - values[i - 1]) if i > 0 else 0

            # Extract hour from timestamp
            ts = data[i].get("ts")
            if isinstance(ts, datetime):
                hour = ts.hour
            else:
                hour = 12  # Default

            # Cyclical encoding for hour
            hour_sin = np.sin(2 * np.pi * hour / 24)
            hour_cos = np.cos(2 * np.pi * hour / 24)

            features.append([current, mean, std, rate, hour_sin, hour_cos])

        return np.array(features)

    def train(
        self,
        normal_data: list[dict[str, Any]],
        anomaly_data: list[dict[str, Any]] | None = None,
    ) -> None:
        """Train the anomaly detection model.

        If anomaly_data is not provided, uses one-class approach where
        extreme deviations from normal are labeled as anomalies.
        """
        normal_features = self._extract_features(normal_data)
        if len(normal_features) == 0:
            raise ValueError("Insufficient data for training")

        if anomaly_data and len(anomaly_data) >= 5:
            # Supervised training with labeled anomalies
            anomaly_features = self._extract_features(anomaly_data)
            X = np.vstack([normal_features, anomaly_features])
            y = np.concatenate([
                np.zeros(len(normal_features)),
                np.ones(len(anomaly_features)),
            ])
        else:
            # Semi-supervised: create synthetic anomalies
            # Consider points > 3 std from mean as anomalies
            values = normal_features[:, 0]
            mean, std = np.mean(values), np.std(values)
            y = np.where(np.abs(values - mean) > 3 * std, 1, 0)
            X = normal_features

        self.model = XGBClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            objective="binary:logistic",
            eval_metric="auc",
            use_label_encoder=False,
        )
        self.model.fit(X, y)
        self._is_trained = True

        logger.info(
            "Model trained",
            samples=len(X),
            anomaly_ratio=np.mean(y),
        )

    def predict(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Predict anomalies in data.

        Returns list of dicts with original data plus anomaly_score and is_anomaly.
        """
        if not self._is_trained or self.model is None:
            # Fall back to statistical detection
            return self._statistical_detection(data)

        features = self._extract_features(data)
        if len(features) == 0:
            return data

        proba = self.model.predict_proba(features)[:, 1]

        results = []
        for i, (point, score) in enumerate(zip(data[4:], proba)):
            point_copy = dict(point)
            point_copy["anomaly_score"] = float(score)
            point_copy["is_anomaly"] = score >= self.threshold
            results.append(point_copy)

        return results

    def _statistical_detection(
        self,
        data: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Fallback statistical anomaly detection using z-score."""
        if len(data) < 2:
            return data

        values = np.array([d["value"] for d in data])
        mean, std = np.mean(values), np.std(values)

        results = []
        for i, point in enumerate(data):
            point_copy = dict(point)
            if std > 0:
                z_score = abs(values[i] - mean) / std
                score = min(z_score / 3.0, 1.0)  # Normalize to 0-1
            else:
                score = 0.0

            point_copy["anomaly_score"] = score
            point_copy["is_anomaly"] = score >= self.threshold
            results.append(point_copy)

        return results

    async def detect_realtime(
        self,
        device_id: str,
        pollutant_code: str,
        current_value: float,
    ) -> dict[str, Any]:
        """Real-time anomaly detection for incoming data point."""
        # Get recent historical data for context
        client = get_tdengine_client()
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=1)

        historical = await client.query_monitoring_data(
            device_id=device_id,
            pollutant_code=pollutant_code,
            start_time=start_time,
            end_time=end_time,
            limit=60,
        )

        if len(historical) < 5:
            return {
                "value": current_value,
                "anomaly_score": 0.0,
                "is_anomaly": False,
                "reason": "Insufficient historical data",
            }

        # Add current value to historical data
        historical.append({
            "ts": datetime.utcnow(),
            "value": current_value,
            "device_id": device_id,
            "pollutant_code": pollutant_code,
        })

        # Run detection
        results = self.predict(historical)
        if results:
            latest = results[-1]
            return {
                "value": current_value,
                "anomaly_score": latest["anomaly_score"],
                "is_anomaly": latest["is_anomaly"],
                "reason": "AI detection" if self._is_trained else "Statistical detection",
            }

        return {
            "value": current_value,
            "anomaly_score": 0.0,
            "is_anomaly": False,
            "reason": "Detection failed",
        }


# Global detector instance
_detector: AnomalyDetector | None = None


def get_anomaly_detector() -> AnomalyDetector:
    """Get or create global anomaly detector instance."""
    global _detector
    if _detector is None:
        _detector = AnomalyDetector()
    return _detector
