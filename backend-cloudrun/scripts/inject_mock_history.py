#!/usr/bin/env python3
"""Generate mock historical data with daily periodicity for NeuralProphet testing.

This script injects 7 days of minute-level monitoring data into TDengine
with clear daily patterns, subtle trends, and realistic noise.

Data Pattern:
- Daytime (8:00-20:00): Sinusoidal wave between 50-85 mg/L (peak at 14:00)
- Nighttime (20:00-8:00): Lower values between 15-35 mg/L
- Subtle upward/downward trend over the 7-day period
- Random noise (-5, +5) for realism

Usage:
    python scripts/inject_mock_history.py --device BEIJING001 --days 7
    python scripts/inject_mock_history.py --device BEIJING001 --pollutant w01018 --days 7 --trend up
"""

import argparse
import asyncio
import math
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

DEFAULT_POLLUTANTS = ["w01018", "w21003", "w01001", "w00000"]

def generate_periodic_value(
    timestamp: datetime,
    pollutant_code: str,
    day_index: int,
    total_days: int,
    trend: str = "up",
) -> float:
    """Generate a value with daily periodicity, trend, and noise.

    Pattern:
    - Daytime (8:00-20:00): Sinusoidal pattern, peaks around 14:00
    - Nighttime (20:00-8:00): Lower baseline values
    - Subtle trend (up/down/none) over the period
    - Random noise for realism

    Args:
        timestamp: The timestamp for this data point
        pollutant_code: The pollutant code (affects value ranges)
        day_index: Current day index (0 to total_days-1)
        total_days: Total number of days
        trend: "up", "down", or "none"

    Returns:
        A realistic sensor value with daily periodicity and trend
    """
    hour = timestamp.hour
    minute = timestamp.minute

    # Convert to decimal hour (0-24)
    decimal_hour = hour + minute / 60.0

    # Define pollutant-specific ranges
    if pollutant_code == "w01018":  # COD
        day_min, day_max = 50.0, 85.0
        night_min, night_max = 15.0, 35.0
        noise_range = 5.0
    elif pollutant_code == "w21003":  # 氨氮
        day_min, day_max = 2.5, 5.0
        night_min, night_max = 0.5, 2.0
        noise_range = 0.4
    elif pollutant_code == "w01001":  # pH
        day_min, day_max = 7.0, 8.5
        night_min, night_max = 6.5, 8.0
        noise_range = 0.15
    elif pollutant_code == "w00000":  # Flow
        day_min, day_max = 60.0, 100.0
        night_min, night_max = 5.0, 30.0
        noise_range = 8.0
    else:  # Default
        day_min, day_max = 40.0, 80.0
        night_min, night_max = 10.0, 30.0
        noise_range = 4.0

    # Calculate trend adjustment (subtle: ±10% over the period)
    if trend == "up":
        trend_factor = 1.0 + (day_index / total_days) * 0.1
    elif trend == "down":
        trend_factor = 1.0 - (day_index / total_days) * 0.1
    else:
        trend_factor = 1.0

    # Determine if daytime (8:00-20:00) or nighttime
    if 8 <= hour < 20:
        # Daytime: Sinusoidal pattern
        # Map 8:00-20:00 to 0-π for a half sine wave
        # Peak at 14:00 (middle of daytime)
        phase = (decimal_hour - 8) / 12.0 * math.pi

        # Sinusoidal oscillation
        amplitude = (day_max - day_min) / 2.0
        midpoint = (day_max + day_min) / 2.0
        base_value = midpoint + amplitude * math.sin(phase)

    else:
        # Nighttime: Lower values with slight variation
        if hour >= 20:
            # Evening transition (20:00-24:00)
            phase = (decimal_hour - 20) / 4.0 * math.pi / 2
            base_value = night_max - (night_max - night_min) * math.sin(phase)
        else:
            # Early morning (0:00-8:00)
            phase = decimal_hour / 8.0 * math.pi / 2
            base_value = night_min + (night_max - night_min) * math.sin(phase)

    # Apply trend
    base_value *= trend_factor

    # Add random noise (uniform distribution for more realistic spikes)
    noise = random.uniform(-noise_range, noise_range)
    value = base_value + noise

    # Ensure non-negative
    value = max(0.1, value)

    return round(value, 2)


async def inject_historical_data_batch(
    device_id: str,
    pollutant_code: str,
    days: int,
    interval_minutes: int = 1,
    org_id: str = "default",
    trend: str = "up",
) -> int:
    """Inject historical data into TDengine using batch insert.

    Args:
        device_id: Device MN number
        pollutant_code: Pollutant code (e.g., w01018)
        days: Number of days of history to generate
        interval_minutes: Interval between data points (default: 1 minute)
        org_id: Organization ID (default: "default")
        trend: Trend direction ("up", "down", "none")

    Returns:
        Number of data points inserted
    """
    from app.db.tdengine_client import get_tdengine_client

    client = get_tdengine_client()

    # Calculate time range
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)

    # Generate all data points first
    data_points = []
    current_time = start_time
    day_index = 0
    last_day = current_time.day

    print(f"Generating {days} days of data...")

    while current_time <= end_time:
        # Track day changes for trend calculation
        if current_time.day != last_day:
            day_index += 1
            last_day = current_time.day

        value = generate_periodic_value(
            current_time, pollutant_code, day_index, days, trend
        )
        data_points.append({
            "ts": current_time,
            "device_id": device_id,
            "pollutant_code": pollutant_code,
            "org_id": org_id,
            "value": value,
            "flag": "N",
            "status": 0,
        })
        current_time += timedelta(minutes=interval_minutes)

    total = len(data_points)
    print(f"Generated {total} data points")
    print(f"Time range: {start_time} to {end_time}")
    print(f"Trend: {trend}")

    # Show sample values
    print(f"\nSample values (first 5):")
    for dp in data_points[:5]:
        print(f"  {dp['ts'].strftime('%Y-%m-%d %H:%M')} -> {dp['value']}")
    print(f"Sample values (last 5):")
    for dp in data_points[-5:]:
        print(f"  {dp['ts'].strftime('%Y-%m-%d %H:%M')} -> {dp['value']}")

    # Batch insert - check if mock mode
    if client.mock_mode:
        # Direct batch append to mock data for efficiency
        print("\nUsing mock mode batch insert...")
        client._mock_data.extend(data_points)
        print(f"Batch inserted {total} records into mock storage")
        return total
    else:
        # Real TDengine - use batch SQL
        print("\nInserting data in batches...")
        batch_size = 500
        inserted = 0

        for i in range(0, total, batch_size):
            batch = data_points[i:i + batch_size]

            # Build batch INSERT SQL
            values_list = []
            for dp in batch:
                ts_str = dp['ts'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                table_name = f"d_{dp['device_id']}_{dp['pollutant_code']}"
                values_list.append(
                    f"{table_name} USING monitoring_data "
                    f"TAGS ('{dp['device_id']}', '{dp['pollutant_code']}', '{dp['org_id']}') "
                    f"VALUES ('{ts_str}', {dp['value']}, '{dp['flag']}', {dp['status']})"
                )

            sql = "INSERT INTO " + " ".join(values_list)

            try:
                await client.execute(sql)
                inserted += len(batch)
                pct = inserted / total * 100
                print(f"Progress: {inserted}/{total} ({pct:.0f}%)")
            except Exception as e:
                print(f"Batch insert error: {e}")
                # Fallback to individual inserts
                for dp in batch:
                    try:
                        await client.insert_monitoring_data(
                            device_id=dp["device_id"],
                            pollutant_code=dp["pollutant_code"],
                            org_id=dp["org_id"],
                            timestamp=dp["ts"],
                            value=dp["value"],
                            flag=dp["flag"],
                        )
                        inserted += 1
                    except Exception as inner_e:
                        if "Duplicate" not in str(inner_e):
                            print(f"  Insert error: {inner_e}")

        return inserted


def plot_preview(days: int, pollutant_code: str, trend: str):
    """Generate a text-based preview of the data pattern."""
    print("\n" + "=" * 70)
    print(f"Data Pattern Preview ({pollutant_code}, {days}-day period, trend='{trend}')")
    print("=" * 70)

    base_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Show values for day 0, middle day, and last day
    sample_days = [0, days // 2, days - 1]

    for day_idx in sample_days:
        print(f"\n--- Day {day_idx + 1}/{days} ---")
        print(f"Hour  | Value  | Pattern")
        print("-" * 50)

        for hour in [0, 6, 8, 12, 14, 18, 20, 23]:
            ts = base_time.replace(hour=hour)
            value = generate_periodic_value(ts, pollutant_code, day_idx, days, trend)

            # Create visual bar
            if pollutant_code == "w01018":
                bar_length = int(value / 2)  # Scale for COD
            else:
                bar_length = int(value * 2)  # Scale for others
            bar = "#" * min(bar_length, 40)

            period = "Day  " if 8 <= hour < 20 else "Night"
            print(f"{hour:02d}:00 | {value:6.1f} | {period} {bar}")

    print("\n" + "=" * 70)


async def main():
    parser = argparse.ArgumentParser(
        description="Inject mock historical data with daily periodicity for NeuralProphet testing"
    )
    parser.add_argument(
        "--device", "-d",
        type=str,
        default="BEIJING001",
        help="Device ID (MN number), default: BEIJING001"
    )
    parser.add_argument(
        "--pollutant", "-p",
        type=str,
        help="Pollutant code (default: generate COD/氨氮/pH/流量全部数据). Use comma-separated list for custom set."
    )
    parser.add_argument(
        "--days", "-D",
        type=int,
        default=7,
        help="Days of historical data to generate, default: 7"
    )
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=1,
        help="Interval between data points in minutes, default: 1"
    )
    parser.add_argument(
        "--trend", "-t",
        type=str,
        choices=["up", "down", "none"],
        default="up",
        help="Trend direction: up, down, or none. default: up"
    )
    parser.add_argument(
        "--preview", "-P",
        action="store_true",
        help="Show data pattern preview without inserting"
    )

    args = parser.parse_args()

    if args.pollutant:
        pollutant_codes = [code.strip() for code in args.pollutant.split(",") if code.strip()]
    else:
        pollutant_codes = DEFAULT_POLLUTANTS

    if not pollutant_codes:
        raise ValueError("No pollutant codes specified")

    expected_points = len(pollutant_codes) * args.days * 24 * 60 // args.interval

    print("=" * 70)
    print("Mock Historical Data Generator for NeuralProphet Testing")
    print("=" * 70)
    print(f"Device:          {args.device}")
    print(f"Pollutants:      {', '.join(pollutant_codes)}")
    print(f"Days:            {args.days}")
    print(f"Interval:        {args.interval} minute(s)")
    print(f"Trend:           {args.trend}")
    print(f"Expected points: {expected_points:,}")
    print("=" * 70)

    # Show preview
    for pollutant in pollutant_codes:
        plot_preview(args.days, pollutant, args.trend)

    if args.preview:
        print("\nPreview mode - no data inserted")
        return

    # Insert data
    print("\nInserting data for all pollutants...")
    total_inserted = 0
    for pollutant in pollutant_codes:
        print(f"\n--- Injecting {pollutant} ---")
        inserted = await inject_historical_data_batch(
            device_id=args.device,
            pollutant_code=pollutant,
            days=args.days,
            interval_minutes=args.interval,
            trend=args.trend,
        )
        total_inserted += inserted

    print("\n" + "=" * 70)
    print(f"Successfully inserted {total_inserted:,} data points across {len(pollutant_codes)} pollutant(s)!")
    print("=" * 70)
    print("\nYou can now test NeuralProphet prediction with:")
    print(f'  curl "http://localhost:8000/api/v1/ai/predict/{args.device}?pollutant_code={args.pollutant}&hours=168"')


if __name__ == "__main__":
    asyncio.run(main())
