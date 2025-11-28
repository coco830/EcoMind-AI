"""Tests for AI anomaly detection module."""

from datetime import datetime, timedelta

import pytest

from app.ai.anomaly_detection import (
    AnomalyType,
    IsolationForestDetector,
)


class TestIsolationForestDetector:
    """Test suite for IsolationForest-based anomaly detection."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.detector = IsolationForestDetector(
            contamination=0.1,
            n_estimators=50,
            constant_threshold_minutes=60,
            spike_threshold_multiplier=3.0,
        )

    def _create_test_data(
        self,
        values: list[float],
        flags: list[str] | None = None,
    ) -> list[dict]:
        """Create test data with timestamps."""
        now = datetime.utcnow()
        data = []

        if flags is None:
            flags = ["N"] * len(values)

        for i, (value, flag) in enumerate(zip(values, flags)):
            data.append({
                "ts": now - timedelta(minutes=len(values) - i),
                "value": value,
                "flag": flag,
            })

        return data

    def test_detect_spike_anomaly(self) -> None:
        """Test detection of sudden spikes in data."""
        # Normal values with a clear spike
        values = [
            100, 102, 98, 101, 99,  # Normal baseline
            100, 101, 99, 100, 98,  # Continued normal
            500,  # <-- Spike! (should be detected)
            101, 100, 99, 102, 98,  # Back to normal
        ]

        data = self._create_test_data(values)
        results = self.detector.detect_anomalies(data)

        # Find the spike point (index 10, value 500)
        spike_result = results[10]

        assert spike_result.value == 500
        assert spike_result.is_anomaly is True
        assert spike_result.anomaly_type in [
            AnomalyType.SPIKE,
            AnomalyType.VALUE_ANOMALY,
        ]

    def test_detect_device_fault_flag(self) -> None:
        """Test detection of device fault via Flag='D'."""
        values = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109]
        flags = ["N", "N", "N", "N", "D", "N", "N", "N", "N", "N"]  # Flag D at index 4

        data = self._create_test_data(values, flags)
        results = self.detector.detect_anomalies(data)

        # The point with flag='D' should be marked as device fault
        fault_result = results[4]

        assert fault_result.is_anomaly is True
        assert fault_result.anomaly_type == AnomalyType.DEVICE_FAULT
        assert "故障" in (fault_result.reason or "")

    def test_detect_constant_values(self) -> None:
        """Test detection of constant (unchanging) values."""
        # Create data with constant values for > 60 minutes
        # Each point is 1 minute apart, so 70 identical values = 69 minutes
        values = [100.0] * 70 + [101, 102, 103, 104, 105]

        detector = IsolationForestDetector(constant_threshold_minutes=60)
        data = self._create_test_data(values)
        results = detector.detect_anomalies(data)

        # Some of the constant values should be flagged
        constant_anomalies = [
            r for r in results
            if r.anomaly_type == AnomalyType.CONSTANT_VALUE
        ]

        # Should detect the constant sequence
        assert len(constant_anomalies) > 0

    def test_normal_data_no_anomalies(self) -> None:
        """Test that normal, varying data produces few/no anomalies."""
        # Generate normal-looking data with natural variation
        import random

        random.seed(42)
        values = [100 + random.uniform(-5, 5) for _ in range(50)]

        data = self._create_test_data(values)
        results = self.detector.detect_anomalies(data)

        # Count anomalies
        anomalies = [r for r in results if r.is_anomaly]

        # With 10% contamination, we expect roughly 10% or fewer anomalies
        # in normal data (IsolationForest may find some outliers)
        assert len(anomalies) <= len(values) * 0.2

    def test_multiple_anomaly_types(self) -> None:
        """Test detection of multiple anomaly types in same dataset."""
        # Data with: spike, device fault, and normal variation
        values = [
            100, 101, 99, 102, 98,     # Normal
            100, 101, 100, 99, 101,    # Normal
            800,                        # Spike at index 10
            100, 99, 101, 100,         # Normal (indices 11-14)
            102,                        # Device fault at index 15
            100, 99, 101, 100,         # Normal
        ]
        flags = ["N"] * 15 + ["D"] + ["N"] * 4

        data = self._create_test_data(values, flags)
        results = self.detector.detect_anomalies(data)

        # Check spike detection
        spike_point = results[10]
        assert spike_point.value == 800
        assert spike_point.is_anomaly is True

        # Check device fault detection
        fault_point = results[15]
        assert fault_point.is_anomaly is True
        assert fault_point.anomaly_type == AnomalyType.DEVICE_FAULT

    def test_insufficient_data(self) -> None:
        """Test behavior with insufficient data points."""
        values = [100, 101, 102]  # Only 3 points
        data = self._create_test_data(values)

        # Should not crash, but may not detect anomalies
        results = self.detector.detect_anomalies(data)

        assert len(results) == 3

    def test_empty_data(self) -> None:
        """Test behavior with empty data."""
        results = self.detector.detect_anomalies([])
        assert results == []

    def test_anomaly_score_range(self) -> None:
        """Test that anomaly scores are in expected range."""
        values = [100, 101, 99, 500, 102, 98, 101, 100, 99, 103]
        data = self._create_test_data(values)
        results = self.detector.detect_anomalies(data)

        for result in results:
            # Scores should be in reasonable range
            assert -2 <= result.anomaly_score <= 1

    def test_result_to_dict(self) -> None:
        """Test AnomalyResult serialization."""
        values = [100, 101, 500, 102, 103, 104, 105, 106, 107, 108]
        data = self._create_test_data(values)
        results = self.detector.detect_anomalies(data)

        for result in results:
            d = result.to_dict()

            assert "timestamp" in d
            assert "value" in d
            assert "is_anomaly" in d
            assert "anomaly_type" in d
            assert "anomaly_score" in d
            assert isinstance(d["anomaly_score"], float)


@pytest.mark.asyncio
async def test_detect_anomalies_function() -> None:
    """Test high-level detect_anomalies function."""
    from app.ai.anomaly_detection import detect_anomalies

    # This will use mock TDengine client in test environment
    result = await detect_anomalies(
        device_id="TEST_DEVICE_001",
        pollutant_code="w01018",
        hours=24,
    )

    assert "device_id" in result
    assert "pollutant_code" in result
    assert "time_range" in result
    assert "total_points" in result
    assert "anomalies" in result
    assert "summary" in result
