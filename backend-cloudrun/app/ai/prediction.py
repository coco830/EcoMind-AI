from __future__ import annotations

"""AI-based trend prediction for environmental monitoring data.

This module provides:
1. Prophet-based time series forecasting with seasonality support (preferred)
2. NeuralProphet as alternative (if available)
3. Confidence intervals for predictions
4. Daily seasonality detection
5. Fallback to simple average when data is insufficient

Priority: Prophet > NeuralProphet > Naive Forecast
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import structlog

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import AsyncSessionLocal
from app.services.monitoring_service import MonitoringService

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

        # Try Prophet first (lightweight, no PyTorch dependency)
        try:
            return self._predict_with_prophet(df, data, pollutant_code)
        except ImportError:
            logger.info("Prophet not installed, trying NeuralProphet")
        except Exception as e:
            logger.warning("Prophet prediction failed", error=str(e))

        # Try NeuralProphet as fallback
        try:
            return self._predict_with_neuralprophet(df, data, pollutant_code)
        except ImportError:
            logger.info("NeuralProphet not installed, using naive fallback")
        except Exception as e:
            logger.warning("NeuralProphet prediction failed", error=str(e))

        # Final fallback to naive forecast
        predictions, metrics = self._simple_average_fallback(data)
        metrics["pollutant_code"] = pollutant_code
        return predictions, "simple_average", metrics

    def _predict_with_prophet(
        self,
        df: pd.DataFrame,
        data: list[dict[str, Any]],
        pollutant_code: str,
    ) -> tuple[list[PredictionPoint], str, dict[str, float]]:
        """使用 Facebook Prophet 进行预测（轻量级，推荐）"""
        from prophet import Prophet

        logger.info("AI 预测: 使用 Prophet 模型")

        # 抑制 Prophet 的日志输出
        import logging
        logging.getLogger('prophet').setLevel(logging.WARNING)
        logging.getLogger('cmdstanpy').setLevel(logging.WARNING)

        # 配置 Prophet 模型
        model = Prophet(
            growth='linear',
            yearly_seasonality=False,
            weekly_seasonality=False,
            daily_seasonality=True,
            interval_width=0.80,
            changepoint_prior_scale=0.05,
        )

        # 训练模型
        model.fit(df)

        # 生成未来时间点
        future_points = (self.prediction_hours * 60) // self.prediction_interval_minutes
        future = model.make_future_dataframe(periods=future_points, freq=f'{self.prediction_interval_minutes}min')

        # 预测
        forecast = model.predict(future)

        # 提取未来预测（排除历史数据）
        last_historical_ts = df["ds"].max()
        future_forecast = forecast[forecast["ds"] > last_historical_ts]

        predictions: list[PredictionPoint] = []
        avg_value = df["y"].mean()

        for _, row in future_forecast.iterrows():
            ts = row["ds"].to_pydatetime()
            yhat = max(0.0, float(row["yhat"]))
            yhat_lower = max(0.0, float(row["yhat_lower"]))
            yhat_upper = max(0.0, float(row["yhat_upper"]))

            # 计算置信度
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

        # 检测预测值塌陷
        predictions = self._validate_predictions(predictions, df, data)
        if predictions is None:
            fallback_predictions, fallback_metrics = self._simple_average_fallback(data)
            fallback_metrics["error"] = "prophet_collapse_detected"
            return fallback_predictions, "simple_average", fallback_metrics

        metrics = {
            "model": "prophet",
            "data_points": len(df),
            "prediction_points": len(predictions),
            "daily_seasonality": True,
            "pollutant_code": pollutant_code,
        }

        logger.info(
            "Prophet prediction completed",
            data_points=len(df),
            predictions=len(predictions),
        )

        return predictions, "prophet", metrics

    def _predict_with_neuralprophet(
        self,
        df: pd.DataFrame,
        data: list[dict[str, Any]],
        pollutant_code: str,
    ) -> tuple[list[PredictionPoint], str, dict[str, float]]:
        """使用 NeuralProphet 进行预测（需要 PyTorch）"""
        from neuralprophet import NeuralProphet, set_log_level
        set_log_level("ERROR")

        logger.info("AI 预测: 使用 NeuralProphet 模型")

        model = NeuralProphet(
            growth="linear",
            yearly_seasonality=False,
            weekly_seasonality=False,
            daily_seasonality=True,
            n_forecasts=1,
            n_lags=0,
            learning_rate=0.1,
            epochs=50,
            batch_size=32,
            quantiles=[0.1, 0.9],
        )

        model.fit(df, freq="15min", progress=None)

        future_points = (self.prediction_hours * 60) // self.prediction_interval_minutes
        future = model.make_future_dataframe(df, periods=future_points)
        forecast = model.predict(future)

        last_historical_ts = df["ds"].max()
        future_forecast = forecast[forecast["ds"] > last_historical_ts]

        predictions: list[PredictionPoint] = []
        avg_value = df["y"].mean()
        std_value = df["y"].std()

        for _, row in future_forecast.iterrows():
            ts = row["ds"].to_pydatetime()
            yhat = float(row["yhat1"])

            if "yhat1 10.0%" in row:
                yhat_lower = float(row["yhat1 10.0%"])
                yhat_upper = float(row["yhat1 90.0%"])
            else:
                yhat_lower = yhat - 1.28 * std_value
                yhat_upper = yhat + 1.28 * std_value

            yhat = max(0.0, yhat)
            yhat_lower = max(0.0, yhat_lower)
            yhat_upper = max(0.0, yhat_upper)

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

        # 检测预测值塌陷
        predictions = self._validate_predictions(predictions, df, data)
        if predictions is None:
            fallback_predictions, fallback_metrics = self._simple_average_fallback(data)
            fallback_metrics["error"] = "neuralprophet_collapse_detected"
            return fallback_predictions, "simple_average", fallback_metrics

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

    def _validate_predictions(
        self,
        predictions: list[PredictionPoint],
        df: pd.DataFrame,
        data: list[dict[str, Any]],
    ) -> list[PredictionPoint] | None:
        """检测预测值是否异常塌陷，返回 None 表示需要降级"""
        if not predictions:
            return predictions

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
                "Prediction collapse detected, will use fallback",
                baseline_value=baseline_value,
                predicted_max=predicted_max,
                max_ratio=max_ratio,
            )
            return None

        return predictions


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
    db_session: AsyncSession | None = None,
) -> dict[str, Any]:
    """High-level function to predict pollutant trends for a device.

    Fetches historical data from MySQL and generates predictions using NeuralProphet.

    Args:
        device_id: Device identifier (MN number)
        pollutant_code: Pollutant code (default: w01018 for COD)
        hours: Hours of historical data to use for training
        prediction_hours: Hours into the future to predict
        db_session: Optional database session (creates one if not provided)

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
    # Use local time for consistency with timestamps (add timezone buffer)
    end_time = datetime.now() + timedelta(hours=9)  # UTC+8 buffer
    start_time = end_time - timedelta(hours=hours + 9)

    # 使用 MySQL MonitoringService 查询历史数据
    if db_session:
        service = MonitoringService(db_session)
        data = await service.query_monitoring_data(
            device_id=device_id,
            pollutant_code=pollutant_code,
            start_time=start_time,
            end_time=end_time,
            limit=5000,
        )
    else:
        async with AsyncSessionLocal() as session:
            service = MonitoringService(session)
            data = await service.query_monitoring_data(
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


async def predict_trend_adaptive(
    device_id: str,
    pollutant_code: str = "w01018",
    hours: int = 24,
    prediction_hours: int = 4,
    db_session: AsyncSession | None = None,
    enable_interpolation: bool = True,
    auto_downgrade: bool = True,
) -> dict[str, Any]:
    """自适应粒度时序预测（带插值和降级）

    改进版预测函数，支持：
    1. 数据质量自动评估
    2. 缺失数据智能插值
    3. 小时级 -> 日级自动降级

    Args:
        device_id: 设备 ID (MN 号)
        pollutant_code: 污染物代码
        hours: 用于训练的历史数据时长（小时）
        prediction_hours: 预测时长（小时）
        db_session: 数据库会话
        enable_interpolation: 是否启用数据插值
        auto_downgrade: 是否启用自动降级（小时级 -> 日级）

    Returns:
        预测结果字典，包含数据质量评估和降级信息
    """
    from app.services.data_interpolation import (
        DataInterpolator,
        PredictionGranularity,
        assess_and_recommend_granularity,
    )

    # 计算时间范围
    end_time = datetime.now() + timedelta(hours=9)
    start_time = end_time - timedelta(hours=hours + 9)

    # 查询历史数据
    if db_session:
        service = MonitoringService(db_session)
        data = await service.query_monitoring_data(
            device_id=device_id,
            pollutant_code=pollutant_code,
            start_time=start_time,
            end_time=end_time,
            limit=10000,
        )
    else:
        async with AsyncSessionLocal() as session:
            service = MonitoringService(session)
            data = await service.query_monitoring_data(
                device_id=device_id,
                pollutant_code=pollutant_code,
                start_time=start_time,
                end_time=end_time,
                limit=10000,
            )

    if not data:
        return {
            "device_id": device_id,
            "pollutant_code": pollutant_code,
            "time_range": {"start": start_time.isoformat(), "end": end_time.isoformat()},
            "historical_data": [],
            "predictions": [],
            "model_type": "insufficient_data",
            "granularity": None,
            "data_quality": None,
            "metrics": {},
            "message": "无历史数据可用于预测",
        }

    # 评估数据质量
    recommended_granularity, quality_metrics = assess_and_recommend_granularity(
        data, start_time, end_time
    )

    logger.info(
        "Data quality assessed for prediction",
        device_id=device_id,
        quality_score=quality_metrics.quality_score,
        coverage_rate=f"{quality_metrics.coverage_rate:.2%}",
        recommended_granularity=recommended_granularity.value,
    )

    # 确定最终使用的粒度
    if auto_downgrade:
        granularity = recommended_granularity
    else:
        granularity = PredictionGranularity.HOURLY

    # 数据插值
    interpolator = DataInterpolator()
    if enable_interpolation and quality_metrics.interpolation_needed:
        df_prepared, prep_metadata = interpolator.prepare_for_prediction(data, granularity)
        processed_data = df_prepared.to_dict("records")
        # 转换为预测器需要的格式
        processed_data = [
            {"ts": row["ds"], "value": row["y"]}
            for row in processed_data
        ]
        interpolation_applied = True
    else:
        processed_data = data
        prep_metadata = {}
        interpolation_applied = False

    # 根据粒度调整预测参数
    if granularity == PredictionGranularity.DAILY:
        # 日级预测：预测未来7天
        predictor = NeuralProphetPredictor(
            prediction_hours=prediction_hours * 6,  # 转换为更长的预测周期
            prediction_interval_minutes=1440,  # 1天 = 1440分钟
        )
        model_type_suffix = "_daily"
    elif granularity == PredictionGranularity.MINUTE_15:
        predictor = NeuralProphetPredictor(
            prediction_hours=prediction_hours,
            prediction_interval_minutes=15,
        )
        model_type_suffix = "_15min"
    else:  # HOURLY
        predictor = NeuralProphetPredictor(
            prediction_hours=prediction_hours,
            prediction_interval_minutes=60,
        )
        model_type_suffix = "_hourly"

    # 生成预测
    predictions, model_type, metrics = predictor.predict(
        processed_data, pollutant_code=pollutant_code
    )

    # 准备历史数据（用于图表展示）
    historical_data = []
    step = max(1, len(data) // 500)
    for i, point in enumerate(sorted(data, key=lambda x: x.get("ts") or x.get("timestamp") or datetime.min)):
        if i % step == 0:
            ts = point.get("ts") or point.get("timestamp")
            if isinstance(ts, datetime):
                ts = ts.isoformat()
            historical_data.append({
                "timestamp": ts,
                "value": round(float(point["value"]), 2),
            })

    # 合并指标
    metrics.update({
        "granularity": granularity.value,
        "interpolation_applied": interpolation_applied,
        "data_quality_score": quality_metrics.quality_score,
        "coverage_rate": quality_metrics.coverage_rate,
        "downgraded": granularity == PredictionGranularity.DAILY and auto_downgrade,
    })
    metrics.update(prep_metadata)

    logger.info(
        "Adaptive prediction completed",
        device_id=device_id,
        model_type=f"{model_type}{model_type_suffix}",
        granularity=granularity.value,
        prediction_points=len(predictions),
        interpolation_applied=interpolation_applied,
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
        "model_type": f"{model_type}{model_type_suffix}",
        "granularity": granularity.value,
        "data_quality": quality_metrics.to_dict(),
        "metrics": metrics,
    }
