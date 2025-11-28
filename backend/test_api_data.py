"""Test script to verify real data API endpoints."""

import asyncio
import aiohttp
import json
from datetime import datetime, timedelta


async def test_data_apis():
    """Test all data API endpoints with real data."""

    # API base URL
    base_url = "http://localhost:8000/api/v1"

    # Test credentials
    username = "admin"
    password = "admin123"

    async with aiohttp.ClientSession() as session:
        # 1. Login first
        print("1. Testing login...")
        login_data = {
            "username": username,
            "password": password
        }
        async with session.post(f"{base_url}/auth/login", data=login_data) as resp:
            if resp.status == 200:
                auth_data = await resp.json()
                token = auth_data["access_token"]
                headers = {"Authorization": f"Bearer {token}"}
                print("✅ Login successful")
            else:
                print(f"❌ Login failed: {await resp.text()}")
                return

        # 2. Get device list
        print("\n2. Getting device list...")
        async with session.get(f"{base_url}/devices", headers=headers) as resp:
            if resp.status == 200:
                devices = await resp.json()
                if devices:
                    device_id = devices[0]["mn"]
                    print(f"✅ Found {len(devices)} devices. Using device: {device_id}")
                else:
                    print("⚠️ No devices found in database")
                    device_id = "MN00000001"  # Use default for testing
            else:
                print(f"❌ Failed to get devices: {await resp.text()}")
                device_id = "MN00000001"

        # 3. Test /data/history endpoint (main endpoint for frontend)
        print(f"\n3. Testing /data/history/{device_id}...")
        params = {
            "limit": 100,
            "pollutant_code": "w01001"  # pH value
        }
        async with session.get(
            f"{base_url}/data/history/{device_id}",
            headers=headers,
            params=params
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"✅ Retrieved {len(data)} historical records")
                if data:
                    print(f"   Sample data point:")
                    print(f"   - Time: {data[0]['ts']}")
                    print(f"   - Value: {data[0]['value']}")
                    print(f"   - Flag: {data[0]['flag']}")
            else:
                error = await resp.text()
                print(f"❌ Failed to get historical data: {error}")

        # 4. Test /data/realtime endpoint
        print(f"\n4. Testing /data/realtime/{device_id}...")
        async with session.get(
            f"{base_url}/data/realtime/{device_id}",
            headers=headers
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"✅ Retrieved {len(data)} real-time records (last 5 minutes)")
            else:
                error = await resp.text()
                print(f"❌ Failed to get real-time data: {error}")

        # 5. Test /data/latest endpoint
        print("\n5. Testing /data/latest...")
        params = {"device_id": device_id, "limit": 10}
        async with session.get(
            f"{base_url}/data/latest",
            headers=headers,
            params=params
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"✅ Retrieved {len(data)} latest records")
            else:
                error = await resp.text()
                print(f"❌ Failed to get latest data: {error}")

        # 6. Test /data/stats endpoint
        print(f"\n6. Testing /data/stats/{device_id}...")
        params = {
            "pollutant_code": "w01001",
            "start_time": (datetime.now() - timedelta(days=7)).isoformat(),
            "end_time": datetime.now().isoformat()
        }
        async with session.get(
            f"{base_url}/data/stats/{device_id}",
            headers=headers,
            params=params
        ) as resp:
            if resp.status == 200:
                stats = await resp.json()
                print(f"✅ Retrieved statistics:")
                if stats:
                    stat = stats[0]
                    print(f"   - Min: {stat.get('min_value')}")
                    print(f"   - Max: {stat.get('max_value')}")
                    print(f"   - Avg: {stat.get('avg_value')}")
                    print(f"   - Count: {stat.get('count')}")
            else:
                error = await resp.text()
                print(f"❌ Failed to get statistics: {error}")

        # 7. Test /data/export endpoint (JSON)
        print(f"\n7. Testing /data/export (JSON)...")
        params = {
            "device_id": device_id,
            "format": "json",
            "limit": 10
        }
        async with session.get(
            f"{base_url}/data/export",
            headers=headers,
            params=params
        ) as resp:
            if resp.status == 200:
                export_data = await resp.json()
                if export_data["format"] == "json":
                    data_count = len(export_data["data"])
                    print(f"✅ JSON export successful: {data_count} records")
            else:
                error = await resp.text()
                print(f"❌ Failed to export data: {error}")

        # 8. Test /data/export endpoint (CSV)
        print(f"\n8. Testing /data/export (CSV)...")
        params["format"] = "csv"
        async with session.get(
            f"{base_url}/data/export",
            headers=headers,
            params=params
        ) as resp:
            if resp.status == 200:
                export_data = await resp.json()
                if export_data["format"] == "csv":
                    csv_lines = export_data["data"].split('\n')
                    print(f"✅ CSV export successful: {len(csv_lines)-1} lines")
            else:
                error = await resp.text()
                print(f"❌ Failed to export CSV: {error}")

        print("\n" + "="*50)
        print("✅ API Test Complete!")
        print("="*50)


if __name__ == "__main__":
    asyncio.run(test_data_apis())