"""AI-based trend prediction for environmental monitoring data using NeuralProphet.

This module provides:
1. NeuralProphet-based time series forecasting with seasonality support
2. Confidence intervals for predictions
3. Daily seasonality detection
4. Fallback to simple average when data is insufficient
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import structlog

from app.db.tdengine_client import get_tdengine_client

# Suppress verbose logging
import logging
import warnings
import traceback

import numpy as np
import pandas as pd
warnings.filterwarnings("ignore", category=FutureWarning)
logging.getLogger('neuralprophet').setLevel(logging.WARNING)
logging.getLogger('pytorch_lightning').setLevel(logging.WARNING)

logger = structlog.get_logger()

# Minimum data points required for NeuralProphet (try as long as we have 24 points)
MIN_TRAINING_POINTS = 24


@dataclass
class PredictionPoint:
    """A single predicted data point with confidence interval."""
    timestamp: datetime
    value: float          # yhat - predicted value
    confidence: float     # Normalized confidence score (0-1)
    value_lower: float    # Lower bound of prediction
    value_upper: float    # Upper bound of prediction

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "value": round(self.value, 2),
            "confidence": round(self.confidence, 4),
            "value_lower": round(self.value_lower, 2),
            "value_upper": round(self.value_upper, 2),
        }


@dataclass
class PredictionResult:
    """Result of trend prediction."""
    device_id: str
    pollutant_code: str
    historical_data: list[dict[str, Any]]
    predictions: list[PredictionPoint]
    model_type: str  # "neuralprophet" or "simple_average"
    metrics: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "device_id": self.device_id,
            "pollutant_code": self.pollutant_code,
            "historical_data": self.historical_data,
            "predictions": [p.to_dict() for p in self.predictions],
            "model_type": self.model_type,
            "metrics": self.metrics,
        }


class NeuralProphetPredictor:
    """Trend prediction using NeuralProphet (PyTorch-based Prophet).

    Features:
    - Daily seasonality detection
    - Trend forecasting with uncertainty
    - No CmdStan dependency (pure PyTorch)
    - Graceful fallback for insufficient data
    """

    def __init__(
        self,
        prediction_hours: int = 4,
        prediction_interval_minutes: int = 15,
        confidence_level: float = 0.80,
    ) -> None:
        """Initialize the predictor.

        Args:
            prediction_hours: Hours into the future to predict
            prediction_interval_minutes: Interval between prediction points
            confidence_level: Confidence level for intervals (default: 80%)
        """
        self.prediction_hours = prediction_hours
        self.prediction_interval_minutes = prediction_interval_minutes
        self.confidence_level = confidence_level

    def _prepare_dataframe(
        self,
        data: list[dict[str, Any]],
    ) -> pd.DataFrame:
        """Prepare data for NeuralProphet model.

        NeuralProphet requires DataFrame with columns:
        - ds: datetime timestamp
        - y: target value

        Returns:
            DataFrame ready for NeuralProphet
        """
        records = []
        for point in data:
            ts = point.get("ts") or point.get("timestamp")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if ts is not None:
                # Ensure timezone-naive for NeuralProphet
                if hasattr(ts, 'tzinfo') and ts.tzinfo is not None:
                    ts = ts.replace(tzinfo=None)
                records.append({
                    "ds": ts,
                    "y": float(point["value"]),
                })

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df = df.sort_values("ds").reset_index(drop=True)

        return df

    def _simple_average_fallback(
        self,
        data: list[dict[str, Any]],
    ) -> tuple[list[PredictionPoint], dict[str, float]]:
        """Naive fallback prediction when NeuralProphet can't be used.

        延续历史末端：未来值等于最后一个值，或最近10分钟平均值，保持水平直线，
        避免兜底时出现“掉零”的用户体验问题。

        Args:
            data: Historical monitoring data points

        Returns:
            Tuple of (predictions, metrics)
        """
        if not data:
            return [], {"fallback": True, "reason": "no_data"}

        # Sort data by timestamp to get recent data
        sorted_data = []
        for point in data:
            ts = point.get("ts") or point.get("timestamp")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if ts is not None:
                if hasattr(ts, 'tzinfo') and ts.tzinfo is not None:
                    ts = ts.replace(tzinfo=None)
                sorted_data.append({"ts": ts, "value": float(point["value"])})

        if not sorted_data:
            return [], {"fallback": True, "reason": "no_valid_data"}

        # Sort ascending to make it easier to work with the last timestamp
        sorted_data.sort(key=lambda x: x["ts"])
        last_point = sorted_data[-1]
        last_ts = last_point["ts"]

        # Use Naive Forecast: future values equal to the last value
        # or, if available, the average of the last 10 minutes.
        ten_minutes_ago = last_ts - timedelta(minutes=10)
        recent_values = [
            d["value"]
            for d in sorted_data
            if d["ts"] >= ten_minutes_ago
        ]

        if recent_values:
            base_value = float(np.mean(recent_values))
        else:
            base_value = float(last_point["value"])

        # If base_value is not positive (e.g., bad data), fall back to all-data average
        if base_value <= 0:
            all_values = [d["value"] for d in sorted_data]
            if all_values:
                base_value = float(np.mean(all_values))
            else:
                base_value = 50.0  # Safe default

        std_value = base_value * 0.1

        # Generate future predictions using Naive Forecast (flat line continuation)
        predictions: list[PredictionPoint] = []
        future_points = (self.prediction_hours * 60) // self.prediction_interval_minutes

        for i in range(future_points):
            future_ts = last_ts + timedelta(minutes=(i + 1) * self.prediction_interval_minutes)

            # Confidence decreases with distance, but stays reasonable
            confidence = max(0.3, 0.6 * (1 - (i / future_points) * 0.5))

            predictions.append(PredictionPoint(
                timestamp=future_ts,
                value=round(base_value, 2),
                confidence=confidence,
                value_lower=max(0.0, round(base_value - 1.5 * std_value, 2)),
                value_upper=round(base_value + 1.5 * std_value, 2),
            ))

        metrics = {
            "fallback": True,
            "reason": "naive_forecast_last_value_or_10m_avg",
            "base_value": round(base_value, 4),
            "recent_10m_points": len(recent_values),
            "total_data_points": len(sorted_data),
        }

        logger.info(
            "Using naive fallback prediction (last value / 10m average)",
            base_value=base_value,
            recent_10m_points=len(recent_values),
        )

        return predictions, metrics

    def predict(
        self,
        data: list[dict[str, Any]],
        pollutant_code: str = "w01018",
    ) -> tuple[list[PredictionPoint], str, dict[str, float]]:
        """Generate predictions for future time points using NeuralProphet.

        Args:
            data: Historical monitoring data points
            pollutant_code: Pollutant being analyzed (for logging/metrics)

        Returns:
            Tuple of (predictions, model_type, metrics)
        """
        # Prepare DataFrame for NeuralProphet as early as possible for logging
        df = self._prepare_dataframe(data)

        logger.info(f"开始 AI 预测，数据点数: {len(df)}")

        # Check minimum data requirement
        if len(data) < 5:
            logger.warning("Insufficient data for prediction", data_points=len(data))
            return [], "insufficient_data", {
                "data_points": len(data),
                "pollutant_code": pollutant_code,
            }

        if len(df) < MIN_TRAINING_POINTS:
            logger.info(
                "Insufficient data for NeuralProphet, using fallback",
                data_points=len(df),
                min_required=MIN_TRAINING_POINTS,
            )
            predictions, metrics = self._simple_average_fallback(data)
            metrics["pollutant_code"] = pollutant_code
            return predictions, "simple_average", metrics

        try:
            logger.debug("AI 预测: 开始导入 NeuralProphet")
            # Import NeuralProphet here to avoid startup overhead
            from neuralprophet import NeuralProphet, set_log_level
            set_log_level("ERROR")
            logger.debug("AI 预测: NeuralProphet 导入完成")

            # Configure NeuralProphet model
            logger.debug("AI 预测: 初始化 NeuralProphet 模型")
            model = NeuralProphet(
                growth="linear",                # Linear trend
                yearly_seasonality=False,       # Not enough data
                weekly_seasonality=False,       # May not have weekly patterns
                daily_seasonality=True,         # Detect daily patterns
                n_forecasts=1,                  # Single step forecasting
                n_lags=0,                       # No autoregression for simplicity
                learning_rate=0.1,
                epochs=50,                      # Reduced epochs for speed
                batch_size=32,
                quantiles=[0.1, 0.9],           # For uncertainty intervals
            )
            logger.debug("AI 预测: 模型初始化完成")

            # Train the model (suppress output)
            logger.debug("AI 预测: 开始训练模型", epochs=50)
            model.fit(df, freq="15min", progress=None)
            logger.debug("AI 预测: 模型训练完成")

            # Generate future timestamps
            future_points = (self.prediction_hours * 60) // self.prediction_interval_minutes
            logger.debug("AI 预测: 生成 future dataframe", future_points=future_points)
            future = model.make_future_dataframe(
                df,
                periods=future_points,
            )
            logger.debug("AI 预测: future dataframe 生成完成", rows=len(future))

            # Generate predictions
            logger.debug("AI 预测: 开始模型预测")
            forecast = model.predict(future)
            logger.debug("AI 预测: 模型预测完成", rows=len(forecast))

            # Extract only future predictions (not in-sample)
            last_historical_ts = df["ds"].max()
            future_forecast = forecast[forecast["ds"] > last_historical_ts]

            predictions: list[PredictionPoint] = []
            avg_value = df["y"].mean()
            std_value = df["y"].std()

            for _, row in future_forecast.iterrows():
                ts = row["ds"].to_pydatetime()
                yhat = float(row["yhat1"])  # NeuralProphet uses yhat1

                # Calculate bounds from quantiles if available
                if "yhat1 10.0%" in row:
                    yhat_lower = float(row["yhat1 10.0%"])
                    yhat_upper = float(row["yhat1 90.0%"])
                else:
                    # Fallback: use std-based bounds
                    yhat_lower = yhat - 1.28 * std_value  # 80% CI
                    yhat_upper = yhat + 1.28 * std_value

                # Ensure non-negative values
                yhat = max(0.0, yhat)
                yhat_lower = max(0.0, yhat_lower)
                yhat_upper = max(0.0, yhat_upper)

                # Calculate confidence based on interval width
                interval_width = yhat_upper - yhat_lower
                relative_width = interval_width / avg_value if avg_value > 0 else 1.0
                confidence = max(0.1, min(0.95, 1.0 - relative_width * 0.3))

                predictions.append(PredictionPoint(
                    timestamp=ts,
                    value=yhat,
                    confidence=confidence,
                    value_lower=yhat_lower,
                    value_upper=yhat_upper,
                ))

            # Detect obviously bad predictions (e.g., all values collapse near zero)
            # and fall back to naive continuation to avoid charts dropping to 0.
            if predictions:
                last_value = float(df["y"].iloc[-1])
                recent_window = df["y"].tail(min(40, len(df)))
                baseline_value = float(recent_window.mean()) if not recent_window.empty else last_value
                baseline_value = max(baseline_value, last_value)

                predicted_max = max(p.value for p in predictions)
                predicted_avg = sum(p.value for p in predictions) / len(predictions)
                max_ratio = (predicted_max / baseline_value) if baseline_value > 0 else 1.0
                avg_ratio = (predicted_avg / baseline_value) if baseline_value > 0 else 1.0
                collapse_detected = baseline_value > 0 and (
                    max_ratio < 0.5 or avg_ratio < 0.3 or predicted_max < 1.0
                )

                if collapse_detected:
                    logger.warning(
                        "NeuralProphet predictions collapsed, switching to naive fallback",
                        baseline_value=baseline_value,
                        predicted_max=predicted_max,
                        predicted_avg=predicted_avg,
                        max_ratio=max_ratio,
                        avg_ratio=avg_ratio,
                    )
                    fallback_predictions, fallback_metrics = self._simple_average_fallback(data)
                    fallback_metrics.update({
                        "error": "neuralprophet_low_values",
                        "baseline_value": round(baseline_value, 4),
                        "predicted_max": round(predicted_max, 4),
                        "predicted_avg": round(predicted_avg, 4),
                        "max_ratio": round(max_ratio, 4),
                        "avg_ratio": round(avg_ratio, 4),
                    })
                    return fallback_predictions, "simple_average", fallback_metrics

            # Calculate model metrics
            metrics = {
                "model": "neuralprophet",
                "data_points": len(df),
                "prediction_points": len(predictions),
                "daily_seasonality": True,
                "epochs": 50,
                "pollutant_code": pollutant_code,
            }

            logger.info(
                "NeuralProphet prediction completed",
                data_points=len(df),
                predictions=len(predictions),
            )

            return predictions, "neuralprophet", metrics

        except ImportError as e:
            logger.error(
                "NeuralProphet not installed, using fallback",
                error=str(e),
                traceback=traceback.format_exc(),
            )
            predictions, metrics = self._simple_average_fallback(data)
            metrics["pollutant_code"] = pollutant_code
            metrics["error"] = "neuralprophet_not_installed"
            return predictions, "simple_average", metrics

        except Exception as e:
            logger.error(
                "NeuralProphet prediction failed, using fallback",
                error=str(e),
                traceback=traceback.format_exc(),
            )
            predictions, metrics = self._simple_average_fallback(data)
            metrics["pollutant_code"] = pollutant_code
            metrics["error"] = str(e)
            return predictions, "simple_average", metrics


# Backward compatibility aliases
ProphetPredictor = NeuralProphetPredictor
TrendPredictor = NeuralProphetPredictor

# Global predictor instance
_predictor: NeuralProphetPredictor | None = None


def get_predictor() -> NeuralProphetPredictor:
    """Get or create global predictor instance."""
    global _predictor
    if _predictor is None:
        _predictor = NeuralProphetPredictor()
    return _predictor


async def predict_trend(
    device_id: str,
    pollutant_code: str = "w01018",
    hours: int = 24,
    prediction_hours: int = 4,
) -> dict[str, Any]:
    """High-level function to predict pollutant trends for a device.

    Fetches historical data from TDengine and generates predictions using NeuralProphet.

    Args:
        device_id: Device identifier (MN number)
        pollutant_code: Pollutant code (default: w01018 for COD)
        hours: Hours of historical data to use for training
        prediction_hours: Hours into the future to predict

    Returns:
        Dictionary containing:
        - device_id: Device identifier
        - pollutant_code: Pollutant analyzed
        - time_range: Historical data time range
        - historical_data: Simplified historical data for charting
        - predictions: Predicted future values with confidence intervals
        - model_type: Type of model used ("neuralprophet" or "simple_average")
        - metrics: Model performance metrics
    """
    client = get_tdengine_client()

    # Use local time for consistency with mock mode timestamps
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)

    # Query historical data
    data = await client.query_monitoring_data(
        device_id=device_id,
        pollutant_code=pollutant_code,
        start_time=start_time,
        end_time=end_time,
        limit=5000,
    )

    if not data:
        return {
            "device_id": device_id,
            "pollutant_code": pollutant_code,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
            },
            "historical_data": [],
            "predictions": [],
            "model_type": "insufficient_data",
            "metrics": {},
            "message": "无历史数据可用于预测",
        }

    # Create predictor with custom prediction horizon
    predictor = NeuralProphetPredictor(prediction_hours=prediction_hours)

    # Generate predictions
    predictions, model_type, metrics = predictor.predict(data, pollutant_code=pollutant_code)

    # Prepare simplified historical data for frontend charting
    # Downsample if too many points (max 500 for better visualization)
    historical_data = []
    step = max(1, len(data) // 500)  # Max 500 points for charting

    for i, point in enumerate(sorted(data, key=lambda x: x.get("ts") or x.get("timestamp") or datetime.min)):
        if i % step == 0:
            ts = point.get("ts") or point.get("timestamp")
            if isinstance(ts, datetime):
                ts = ts.isoformat()
            historical_data.append({
                "timestamp": ts,
                "value": round(float(point["value"]), 2),
            })

    logger.info(
        "Trend prediction completed",
        device_id=device_id,
        pollutant_code=pollutant_code,
        historical_points=len(data),
        prediction_points=len(predictions),
        model_type=model_type,
    )

    return {
        "device_id": device_id,
        "pollutant_code": pollutant_code,
        "time_range": {
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
        },
        "historical_data": historical_data,
        "predictions": [p.to_dict() for p in predictions],
        "model_type": model_type,
        "metrics": metrics,
    }
