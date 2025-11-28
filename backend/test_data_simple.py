"""Simple test for data API endpoints using httpx (already installed)."""

import httpx
import asyncio
from datetime import datetime, timedelta


async def test_apis():
    """Test the data API endpoints."""
    base_url = "http://localhost:8000/api/v1"

    async with httpx.AsyncClient() as client:
        # 1. Login
        print("1. Testing login...")
        login_data = {"username": "admin", "password": "admin123"}
        resp = await client.post(f"{base_url}/auth/login", data=login_data)

        if resp.status_code == 200:
            token = resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            print("✅ Login successful")
        else:
            print(f"❌ Login failed: {resp.text}")
            return

        # 2. Test history endpoint (main one used by frontend)
        print("\n2. Testing /data/history/MN00000001...")
        try:
            resp = await client.get(
                f"{base_url}/data/history/MN00000001",
                headers=headers,
                params={"limit": 10}
            )

            if resp.status_code == 200:
                data = resp.json()
                print(f"✅ History endpoint works: {len(data)} records")
                if data:
                    print(f"   Sample: ts={data[0]['ts']}, value={data[0]['value']}")
            else:
                print(f"❌ History failed: {resp.text}")
        except Exception as e:
            print(f"❌ History error: {e}")

        # 3. Test latest endpoint
        print("\n3. Testing /data/latest...")
        try:
            resp = await client.get(
                f"{base_url}/data/latest",
                headers=headers,
                params={"limit": 5}
            )

            if resp.status_code == 200:
                data = resp.json()
                print(f"✅ Latest endpoint works: {len(data)} records")
            else:
                print(f"❌ Latest failed: {resp.text}")
        except Exception as e:
            print(f"❌ Latest error: {e}")

        # 4. Test realtime endpoint
        print("\n4. Testing /data/realtime/MN00000001...")
        try:
            resp = await client.get(
                f"{base_url}/data/realtime/MN00000001",
                headers=headers
            )

            if resp.status_code == 200:
                data = resp.json()
                print(f"✅ Realtime endpoint works: {len(data)} records")
            else:
                print(f"❌ Realtime failed: {resp.text}")
        except Exception as e:
            print(f"❌ Realtime error: {e}")

        print("\n" + "="*50)
        print("API Test Complete!")
        print("="*50)


if __name__ == "__main__":
    asyncio.run(test_apis())