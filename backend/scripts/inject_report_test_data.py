#!/usr/bin/env python3
"""
Inject realistic test data into TDengine for Report Center testing.

This script creates a month's worth of monitoring data for testing
the Excel and PDF export functionality in the Reports page.

Usage:
    python scripts/inject_report_test_data.py
    python scripts/inject_report_test_data.py --device TESTDEV001 --days 30
"""

import asyncio
import argparse
import random
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.tdengine_client import get_tdengine_client


# Water quality pollutants with realistic value ranges
WATER_POLLUTANTS = {
    "w01001": {"name": "pH值", "min": 6.5, "max": 8.5, "unit": "", "threshold": 9.0},
    "w01018": {"name": "化学需氧量(COD)", "min": 10, "max": 80, "unit": "mg/L", "threshold": 100},
    "w21003": {"name": "氨氮", "min": 0.5, "max": 8, "unit": "mg/L", "threshold": 15},
    "w21011": {"name": "总磷", "min": 0.1, "max": 1.5, "unit": "mg/L", "threshold": 2.0},
    "w21001": {"name": "总氮", "min": 5, "max": 25, "unit": "mg/L", "threshold": 30},
    "w01009": {"name": "溶解氧", "min": 4, "max": 12, "unit": "mg/L", "threshold": None},
    "w01010": {"name": "水温", "min": 15, "max": 28, "unit": "℃", "threshold": None},
}


def generate_value(pollutant_code: str, hour: int) -> tuple[float, str]:
    """
    Generate a realistic value with daily patterns.

    Returns (value, flag) tuple where flag is 'N' for normal or 'A' for alarm.
    """
    config = WATER_POLLUTANTS[pollutant_code]
    base_min = config["min"]
    base_max = config["max"]
    threshold = config["threshold"]

    # Add daily variation pattern (higher during day, lower at night)
    if 8 <= hour <= 18:
        # Daytime: slightly higher values
        factor = 1.1 + random.uniform(0, 0.2)
    else:
        # Nighttime: slightly lower values
        factor = 0.9 + random.uniform(0, 0.1)

    # Generate base value
    value = random.uniform(base_min, base_max) * factor

    # Add some noise
    noise = random.gauss(0, (base_max - base_min) * 0.05)
    value += noise

    # Occasionally generate exceedance values (about 2% of the time)
    if threshold and random.random() < 0.02:
        value = threshold * random.uniform(1.01, 1.3)
        flag = "A"  # Alarm
    else:
        # Clamp to reasonable range
        value = max(base_min * 0.5, min(value, base_max * 1.5))
        flag = "N"  # Normal

    return round(value, 4), flag


async def inject_data(device_id: str, days: int, org_id: str = "default"):
    """Inject test data into TDengine."""
    client = get_tdengine_client()

    print("Connecting to TDengine...")
    await client.connect()

    # Initialize database
    print("Initializing database...")
    await client.init_database()

    # Calculate time range
    end_time = datetime.now().replace(minute=0, second=0, microsecond=0)
    start_time = end_time - timedelta(days=days)

    print(f"\nInjecting data for device: {device_id}")
    print(f"Time range: {start_time} to {end_time}")
    print(f"Pollutants: {list(WATER_POLLUTANTS.keys())}")
    print(f"Total days: {days}")

    total_records = 0
    exceedance_count = 0

    current_time = start_time

    # Generate data every hour (24 points per day)
    while current_time <= end_time:
        for pollutant_code in WATER_POLLUTANTS.keys():
            value, flag = generate_value(pollutant_code, current_time.hour)

            success = await client.insert_monitoring_data(
                device_id=device_id,
                pollutant_code=pollutant_code,
                org_id=org_id,
                timestamp=current_time,
                value=value,
                flag=flag,
                status=0 if flag == "N" else 1
            )

            if success:
                total_records += 1
                if flag == "A":
                    exceedance_count += 1

        # Move to next hour
        current_time += timedelta(hours=1)

        # Print progress every day
        if current_time.hour == 0:
            day_num = (current_time - start_time).days
            print(f"  Day {day_num}/{days} completed...")

    print(f"\n{'='*50}")
    print(f"Data injection completed!")
    print(f"  Total records: {total_records}")
    print(f"  Exceedance records: {exceedance_count}")
    print(f"  Device ID: {device_id}")
    print(f"{'='*50}")

    # Verify by querying
    print("\nVerifying data...")
    data = await client.query_monitoring_data(
        device_id=device_id,
        limit=10
    )

    if data:
        print(f"Latest {len(data)} records:")
        for record in data[:5]:
            print(f"  {record['ts']} | {record['pollutant_code']} | {record['value']} | Flag: {record['flag']}")
    else:
        print("Warning: No data found after injection!")

    await client.close()
    return total_records


async def main():
    parser = argparse.ArgumentParser(
        description="Inject test data for Report Center testing"
    )
    parser.add_argument(
        "--device",
        default="TESTDEV001",
        help="Device MN number (default: TESTDEV001)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days of data to generate (default: 30)"
    )
    parser.add_argument(
        "--org",
        default="default",
        help="Organization ID (default: default)"
    )

    args = parser.parse_args()

    print("="*60)
    print("EcoMind-AI Report Test Data Injection")
    print("="*60)

    try:
        records = await inject_data(args.device, args.days, args.org)
        print(f"\nSuccess! You can now test the Reports page at:")
        print(f"  http://localhost:3000/reports")
        print(f"\nSelect device '{args.device}' to view and export reports.")
        return 0
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
