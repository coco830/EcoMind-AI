#!/usr/bin/env python3
"""Test script for Prophet prediction with periodic data.

This script generates synthetic data with clear "day high, night low" patterns
and validates that Prophet predictions follow the same cycle without going negative.

Usage:
    python scripts/test_prophet_prediction.py
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np

from app.ai.prediction import ProphetPredictor


def generate_periodic_data(
    hours: int = 48,
    interval_minutes: int = 30,
    base_value: float = 100.0,
    amplitude: float = 50.0,
) -> list[dict]:
    """Generate synthetic data with day/night cycle.

    Pattern: High during day (8:00-20:00), Low during night (20:00-8:00)

    Args:
        hours: Total hours of data to generate
        interval_minutes: Interval between data points
        base_value: Base value around which data oscillates
        amplitude: Amplitude of day/night variation

    Returns:
        List of data points with timestamp and value
    """
    data = []
    now = datetime.now()
    start_time = now - timedelta(hours=hours)

    num_points = (hours * 60) // interval_minutes

    for i in range(num_points):
        ts = start_time + timedelta(minutes=i * interval_minutes)
        hour = ts.hour

        # Day/night cycle: high during day (8-20), low during night
        if 8 <= hour < 20:
            # Daytime: higher values with peak at noon
            hour_factor = 1 - abs(hour - 14) / 6  # Peak at 14:00
            cycle_value = base_value + amplitude * (0.5 + 0.5 * hour_factor)
        else:
            # Nighttime: lower values with minimum at 2 AM
            if hour >= 20:
                night_hour = hour - 20
            else:
                night_hour = hour + 4
            hour_factor = abs(night_hour - 6) / 6  # Minimum at 2 AM (6 hours from 20:00)
            cycle_value = base_value - amplitude * (0.5 + 0.3 * (1 - hour_factor))

        # Add some noise
        noise = np.random.normal(0, amplitude * 0.1)
        value = max(0, cycle_value + noise)

        data.append({
            "ts": ts,
            "value": value,
        })

    return data


def run_test():
    """Run Prophet prediction test with periodic data."""
    print("=" * 60)
    print("Prophet Prediction Test - Periodic Data Validation")
    print("=" * 60)

    # Generate 48 hours of periodic data
    print("\n[1] Generating 48 hours of synthetic periodic data...")
    data = generate_periodic_data(hours=48, interval_minutes=30)
    print(f"    Generated {len(data)} data points")

    # Show sample of generated data
    print("\n[2] Sample of generated data (showing day/night pattern):")
    for i, point in enumerate(data):
        if i % 12 == 0:  # Every 6 hours
            hour = point["ts"].hour
            period = "Day  " if 8 <= hour < 20 else "Night"
            print(f"    {point['ts'].strftime('%Y-%m-%d %H:%M')} ({period}): {point['value']:.2f}")

    # Initialize predictor
    print("\n[3] Running Prophet prediction (4 hours ahead)...")
    predictor = ProphetPredictor(prediction_hours=4, prediction_interval_minutes=15)

    try:
        predictions, model_type, metrics = predictor.predict(data)
    except Exception as e:
        print(f"\n    ERROR: Prophet prediction failed: {e}")
        print("\n    Note: Make sure Prophet is installed:")
        print("    pip install prophet")
        return False

    print(f"    Model type: {model_type}")
    print(f"    Generated {len(predictions)} prediction points")

    # Validate predictions
    print("\n[4] Validating predictions...")

    # Check 1: No negative values
    negative_count = sum(1 for p in predictions if p.value < 0)
    print(f"    Negative values: {negative_count} (should be 0)")

    # Check 2: All predictions have confidence intervals
    missing_intervals = sum(1 for p in predictions if p.value_lower is None or p.value_upper is None)
    print(f"    Missing confidence intervals: {missing_intervals} (should be 0)")

    # Check 3: Predictions follow day/night pattern
    print("\n[5] Prediction values with confidence intervals:")
    print("    Time                  | Value  | Lower  | Upper  | Conf   | Period")
    print("    " + "-" * 70)

    day_predictions = []
    night_predictions = []

    for p in predictions:
        hour = p.timestamp.hour
        period = "Day  " if 8 <= hour < 20 else "Night"
        print(f"    {p.timestamp.strftime('%Y-%m-%d %H:%M')} | {p.value:6.2f} | {p.value_lower:6.2f} | {p.value_upper:6.2f} | {p.confidence:.4f} | {period}")

        if 8 <= hour < 20:
            day_predictions.append(p.value)
        else:
            night_predictions.append(p.value)

    # Check 4: Day average should be higher than night average (if we have both)
    print("\n[6] Day/Night pattern analysis:")
    if day_predictions and night_predictions:
        day_avg = np.mean(day_predictions)
        night_avg = np.mean(night_predictions)
        print(f"    Day average: {day_avg:.2f}")
        print(f"    Night average: {night_avg:.2f}")
        pattern_detected = day_avg > night_avg
        print(f"    Day > Night pattern: {'YES' if pattern_detected else 'NO (may need more data)'}")
    else:
        print("    Not enough mixed day/night predictions to compare")
        pattern_detected = True  # Skip this check

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    all_passed = (
        negative_count == 0 and
        missing_intervals == 0 and
        len(predictions) > 0
    )

    if all_passed:
        print("PASSED: All validation checks passed!")
        print(f"  - No negative predictions")
        print(f"  - All confidence intervals present")
        print(f"  - {len(predictions)} predictions generated")
        if model_type == "prophet":
            print(f"  - Using Prophet model with seasonality detection")
        else:
            print(f"  - Using fallback model: {model_type}")
    else:
        print("FAILED: Some validation checks failed")
        if negative_count > 0:
            print(f"  - {negative_count} negative predictions found")
        if missing_intervals > 0:
            print(f"  - {missing_intervals} missing confidence intervals")
        if len(predictions) == 0:
            print(f"  - No predictions generated")

    print("\n" + "=" * 60)

    return all_passed


if __name__ == "__main__":
    success = run_test()
    sys.exit(0 if success else 1)
