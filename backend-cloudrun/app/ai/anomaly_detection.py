from __future__ import annotations

"""AI-based anomaly detection using IsolationForest algorithm.

This module provides:
1. IsolationForest-based statistical anomaly detection
2. Rule-based detection (Flag 'D' for device fault, constant values)
3. Hybrid detection combining both approaches
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID

import numpy as np
import structlog
from sqlalchemy import select
from sklearn.ensemble import IsolationForest

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import AsyncSessionLocal
from app.models.device import Device
from app.services.alarm_service import AlarmService
from app.services.monitoring_service import MonitoringService

logger = structlog.get_logger()


class AnomalyType(str, Enum):
    """Types of detected anomalies."""
    VALUE_ANOMALY = "数值异常"      # Statistical outlier detected by IsolationForest
    DEVICE_FAULT = "设备故障"       # Flag marked as 'D' (device fault)
    CONSTANT_VALUE = "恒值异常"     # Value unchanged for extended period
    SPIKE = "突变异常"              # Sudden spike in value
    NORMAL = "正常"                 # No anomaly detected


@dataclass
class AnomalyResult:
    """Result of anomaly detection for a single data point."""
    timestamp: datetime
    value: float
    is_anomaly: bool
    anomaly_type: AnomalyType
    anomaly_score: float  # -1 to 1, where -1 is most anomalous
    flag: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "value": self.value,
            "is_anomaly": self.is_anomaly,
            "anomaly_type": self.anomaly_type.value,
            "anomaly_score": round(self.anomaly_score, 4),
            "flag": self.flag,
            "reason": self.reason,
        }


class IsolationForestDetector:
    """Isolation Forest based anomaly detector for environmental monitoring data.

    Uses sklearn's IsolationForest algorithm which is effective for:
    - Detecting outliers without labeled data
    - Working with high-dimensional data
    - Fast training and prediction
    """

    def __init__(
        self,
        contamination: float = 0.1,
        n_estimators: int = 100,
        constant_threshold_minutes: int = 60,
        spike_threshold_multiplier: float = 3.0,
    ) -> None:
        """Initialize the detector.

        Args:
            contamination: Expected proportion of outliers (0.0 to 0.5)
            n_estimators: Number of trees in the forest
            constant_threshold_minutes: Duration to consider values as constant
            spike_threshold_multiplier: Multiplier for spike detection (vs std dev)
        """
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.constant_threshold_minutes = constant_threshold_minutes
        self.spike_threshold_multiplier = spike_threshold_multiplier
        self.model: IsolationForest | None = None

    def _prepare_features(self, data: list[dict[str, Any]]) -> np.ndarray:
        """Extract features from monitoring data for IsolationForest.

        Features:
        - Current value (normalized)
        - Rate of change from previous point
        - Rolling mean deviation (5-point window)
        - Rolling std (5-point window)
        """
        if len(data) < 5:
            return np.array([])

        values = np.array([d["value"] for d in data], dtype=float)

        # Normalize values
        mean_val = np.mean(values)
        std_val = np.std(values)
        if std_val == 0:
            std_val = 1.0  # Avoid division by zero

        features = []
        for i in range(len(values)):
            # Current normalized value
            norm_value = (values[i] - mean_val) / std_val

            # Rate of change
            if i > 0:
                rate = values[i] - values[i - 1]
            else:
                rate = 0.0

            # Rolling statistics (5-point window)
            window_start = max(0, i - 4)
            window = values[window_start:i + 1]
            rolling_mean = np.mean(window)
            rolling_std = np.std(window) if len(window) > 1 else 0.0

            # Deviation from rolling mean
            mean_deviation = values[i] - rolling_mean

            features.append([
                norm_value,
                rate,
                mean_deviation,
                rolling_std,
            ])

        return np.array(features)

    def _detect_constant_values(
        self,
        data: list[dict[str, Any]],
    ) -> set[int]:
        """Detect indices where values have been constant for threshold duration.

        Returns set of indices that are part of constant-value sequences.
        """
        if len(data) < 2:
            return set()

        constant_indices = set()
        values = [d["value"] for d in data]
        timestamps = [d.get("ts") or d.get("timestamp") for d in data]

        # Find sequences of identical values
        i = 0
        while i < len(values):
            j = i
            # Find end of constant sequence
            while j < len(values) and values[j] == values[i]:
                j += 1

            # Check if sequence duration exceeds threshold
            if j - i >= 2:  # At least 2 consecutive values
                start_ts = timestamps[i]
                end_ts = timestamps[j - 1]

                if start_ts and end_ts:
                    if isinstance(start_ts, str):
                        start_ts = datetime.fromisoformat(start_ts.replace("Z", "+00:00"))
                    if isinstance(end_ts, str):
                        end_ts = datetime.fromisoformat(end_ts.replace("Z", "+00:00"))

                    duration = (end_ts - start_ts).total_seconds() / 60

                    if duration >= self.constant_threshold_minutes:
                        # Mark all indices in this sequence as constant
                        for k in range(i, j):
                            constant_indices.add(k)

            i = j if j > i else i + 1

        return constant_indices

    def _detect_spikes(self, data: list[dict[str, Any]]) -> set[int]:
        """Detect sudden spikes in values.

        A spike is defined as a value that deviates more than
        spike_threshold_multiplier * std from the rolling mean.
        """
        if len(data) < 5:
            return set()

        spike_indices = set()
        values = np.array([d["value"] for d in data], dtype=float)

        for i in range(2, len(values)):
            # Use previous points for baseline
            window = values[max(0, i - 5):i]
            if len(window) < 2:
                continue

            mean = np.mean(window)
            std = np.std(window)

            if std > 0:
                deviation = abs(values[i] - mean) / std
                if deviation > self.spike_threshold_multiplier:
                    spike_indices.add(i)

        return spike_indices

    def detect_anomalies(
        self,
        data: list[dict[str, Any]],
    ) -> list[AnomalyResult]:
        """Detect anomalies in monitoring data.

        Combines:
        1. Rule-based detection (Flag 'D', constant values)
        2. IsolationForest statistical detection
        3. Spike detection

        Args:
            data: List of monitoring data points with 'value', 'ts'/'timestamp', 'flag'

        Returns:
            List of AnomalyResult for each data point
        """
        if not data:
            return []

        results: list[AnomalyResult] = []

        # Rule-based detection: constant values
        constant_indices = self._detect_constant_values(data)

        # Spike detection
        spike_indices = self._detect_spikes(data)

        # Prepare features for IsolationForest
        features = self._prepare_features(data)

        # Train IsolationForest if we have enough data
        if_predictions = None
        if_scores = None
        if len(features) >= 10:
            self.model = IsolationForest(
                contamination=self.contamination,
                n_estimators=self.n_estimators,
                random_state=42,
                n_jobs=-1,
            )
            self.model.fit(features)
            if_predictions = self.model.predict(features)  # 1 = normal, -1 = anomaly
            if_scores = self.model.score_samples(features)  # More negative = more anomalous

        # Process each data point
        for i, point in enumerate(data):
            ts = point.get("ts") or point.get("timestamp")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))

            value = point["value"]
            flag = point.get("flag", "N")

            # Determine anomaly type and score
            is_anomaly = False
            anomaly_type = AnomalyType.NORMAL
            anomaly_score = 0.0
            reason = None

            # Priority 1: Device fault flag
            if flag and flag.upper() == "D":
                is_anomaly = True
                anomaly_type = AnomalyType.DEVICE_FAULT
                anomaly_score = -1.0
                reason = "设备标记为故障状态 (Flag=D)"

            # Priority 2: Constant value detection
            elif i in constant_indices:
                is_anomaly = True
                anomaly_type = AnomalyType.CONSTANT_VALUE
                anomaly_score = -0.8
                reason = f"数值连续 {self.constant_threshold_minutes} 分钟以上未变化"

            # Priority 3: Spike detection
            elif i in spike_indices:
                is_anomaly = True
                anomaly_type = AnomalyType.SPIKE
                anomaly_score = -0.9
                reason = f"数值突变超过 {self.spike_threshold_multiplier} 倍标准差"

            # Priority 4: IsolationForest detection
            elif if_predictions is not None and i < len(if_predictions):
                if if_predictions[i] == -1:
                    is_anomaly = True
                    anomaly_type = AnomalyType.VALUE_ANOMALY
                    anomaly_score = float(if_scores[i]) if if_scores is not None else -0.5
                    reason = "孤立森林算法检测到统计异常值"
                else:
                    anomaly_score = float(if_scores[i]) if if_scores is not None else 0.0

            results.append(AnomalyResult(
                timestamp=ts,
                value=value,
                is_anomaly=is_anomaly,
                anomaly_type=anomaly_type,
                anomaly_score=anomaly_score,
                flag=flag,
                reason=reason,
            ))

        logger.info(
            "Anomaly detection completed",
            total_points=len(data),
            anomalies_found=sum(1 for r in results if r.is_anomaly),
        )

        return results


# Global detector instance
_detector: IsolationForestDetector | None = None


def get_detector() -> IsolationForestDetector:
    """Get or create global detector instance."""
    global _detector
    if _detector is None:
        _detector = IsolationForestDetector()
    return _detector


async def _get_device_by_mn(mn: str) -> Device | None:
    """Get device by MN from PostgreSQL.

    Args:
        mn: Device MN identifier

    Returns:
        Device or None if not found
    """
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Device).where(Device.mn == mn)
            )
            return result.scalar_one_or_none()
    except Exception as e:
        logger.warning("Failed to lookup device", mn=mn, error=str(e))
        return None


async def _create_alarms_for_anomalies(
    device_id: str,
    pollutant_code: str,
    anomalies: list[AnomalyResult],
) -> int:
    """Create alarms for detected anomalies.

    Only creates alarms for the most recent anomaly of each type
    to avoid alarm flooding.

    Args:
        device_id: Device MN identifier
        pollutant_code: Pollutant code
        anomalies: List of detected anomalies

    Returns:
        Number of alarms created
    """
    # Get device from database
    device = await _get_device_by_mn(device_id)
    if device is None:
        logger.warning(
            "Cannot create alarms: device not found",
            device_id=device_id,
        )
        return 0

    # Create alarm service
    alarm_service = AlarmService()

    # Group anomalies by type and get the most recent one for each type
    latest_by_type: dict[AnomalyType, AnomalyResult] = {}
    for anomaly in anomalies:
        if anomaly.anomaly_type not in latest_by_type:
            latest_by_type[anomaly.anomaly_type] = anomaly
        elif anomaly.timestamp and latest_by_type[anomaly.anomaly_type].timestamp:
            if anomaly.timestamp > latest_by_type[anomaly.anomaly_type].timestamp:
                latest_by_type[anomaly.anomaly_type] = anomaly

    # Create alarms for each unique anomaly type
    alarms_created = 0
    for anomaly_type, anomaly in latest_by_type.items():
        # Skip normal entries (shouldn't happen but be safe)
        if anomaly_type == AnomalyType.NORMAL:
            continue

        try:
            alarm = await alarm_service.create_ai_anomaly_alarm(
                device_id=device.id,
                device_mn=device.mn,
                pollutant_code=pollutant_code,
                value=anomaly.value,
                anomaly_type=anomaly_type.value,
                anomaly_score=anomaly.anomaly_score,
                reason=anomaly.reason,
            )
            if alarm:
                alarms_created += 1
                logger.info(
                    "AI anomaly alarm created",
                    alarm_id=str(alarm.id),
                    device_mn=device.mn,
                    anomaly_type=anomaly_type.value,
                )
        except Exception as e:
            logger.error(
                "Failed to create AI anomaly alarm",
                device_mn=device.mn,
                anomaly_type=anomaly_type.value,
                error=str(e),
            )

    return alarms_created


async def detect_anomalies(
    device_id: str,
    pollutant_code: str = "w01018",
    hours: int = 24,
    create_alarms: bool = False,
    db_session: AsyncSession | None = None,
) -> dict[str, Any]:
    """High-level function to detect anomalies for a device.

    Fetches data from MySQL and runs anomaly detection.
    Optionally creates alarms for detected anomalies.

    Args:
        device_id: Device identifier (MN number)
        pollutant_code: Pollutant code (default: w01018 for COD)
        hours: Hours of historical data to analyze
        create_alarms: If True, create alarms for detected anomalies
        db_session: Optional database session (creates one if not provided)

    Returns:
        Dictionary containing:
        - device_id: Device identifier
        - pollutant_code: Pollutant analyzed
        - time_range: Start and end time of analysis
        - total_points: Total data points analyzed
        - anomalies: List of detected anomalies with details
        - summary: Summary statistics
        - alarms_created: Number of alarms created (if create_alarms=True)
    """
    # Use local time with timezone buffer
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
            limit=5000,  # Max points for 24h at 1-min intervals
        )
    else:
        async with AsyncSessionLocal() as session:
            service = MonitoringService(session)
            data = await service.query_monitoring_data(
                device_id=device_id,
                pollutant_code=pollutant_code,
                start_time=start_time,
                end_time=end_time,
                limit=5000,  # Max points for 24h at 1-min intervals
            )

    if not data:
        return {
            "device_id": device_id,
            "pollutant_code": pollutant_code,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
            },
            "total_points": 0,
            "anomalies": [],
            "summary": {
                "total_anomalies": 0,
                "by_type": {},
                "anomaly_rate": 0.0,
            },
            "message": "无数据可分析",
        }

    # Sort by timestamp ascending for analysis
    data.sort(key=lambda x: x.get("ts") or x.get("timestamp") or datetime.min)

    # Run detection
    detector = get_detector()
    results = detector.detect_anomalies(data)

    # Filter only anomalies
    anomalies = [r for r in results if r.is_anomaly]

    # Count by type
    type_counts: dict[str, int] = {}
    for anomaly in anomalies:
        type_name = anomaly.anomaly_type.value
        type_counts[type_name] = type_counts.get(type_name, 0) + 1

    # Create alarms if requested
    alarms_created = 0
    if create_alarms and anomalies:
        alarms_created = await _create_alarms_for_anomalies(
            device_id=device_id,
            pollutant_code=pollutant_code,
            anomalies=anomalies,
        )

    return {
        "device_id": device_id,
        "pollutant_code": pollutant_code,
        "time_range": {
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
        },
        "total_points": len(data),
        "anomalies": [a.to_dict() for a in anomalies],
        "summary": {
            "total_anomalies": len(anomalies),
            "by_type": type_counts,
            "anomaly_rate": round(len(anomalies) / len(data) * 100, 2) if data else 0,
        },
        "alarms_created": alarms_created,
    }
