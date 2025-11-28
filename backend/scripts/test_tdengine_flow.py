#!/usr/bin/env python3
"""
TDengine Integration Test Script

This script tests the complete data flow:
1. Connect to TDengine
2. Initialize database and tables
3. Send a simulated HJ212 TCP packet
4. Verify data is stored in TDengine
5. Query data via API

Usage:
    # First start services:
    docker-compose up -d tdengine postgres backend

    # Then run this script:
    cd backend
    python scripts/test_tdengine_flow.py

Environment variables:
    TDENGINE_HOST: TDengine host (default: localhost)
    TDENGINE_PORT: TDengine port (default: 6030)
    TCP_GATEWAY_HOST: TCP Gateway host (default: localhost)
    TCP_GATEWAY_PORT: TCP Gateway port (default: 9880)
    API_HOST: Backend API host (default: localhost)
    API_PORT: Backend API port (default: 8000)
"""

import asyncio
import socket
import sys
import os
import time
from datetime import datetime
from typing import Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import after path is set
os.environ.setdefault("TDENGINE_HOST", "localhost")
os.environ.setdefault("TDENGINE_PORT", "6030")

from app.db.tdengine_client import get_tdengine_client


def print_header(text: str):
    """Print section header."""
    print("\n" + "=" * 60)
    print(f" {text}")
    print("=" * 60)


def print_step(step: int, text: str):
    """Print step information."""
    print(f"\n[Step {step}] {text}")


def print_result(success: bool, message: str):
    """Print result with status."""
    status = "✓" if success else "✗"
    print(f"  {status} {message}")


def send_tcp_packet(host: str, port: int, data: bytes, timeout: float = 5.0) -> Optional[bytes]:
    """Send TCP packet and optionally receive response."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.sendall(data)

            try:
                response = sock.recv(1024)
                return response
            except socket.timeout:
                return b""  # No response is OK
    except ConnectionRefusedError:
        return None
    except Exception as e:
        print(f"  TCP Error: {e}")
        return None


def create_hj212_packet(device_id: str, pollutant_code: str, value: float) -> bytes:
    """Create a valid HJ212 protocol packet."""
    now = datetime.now()
    data_time = now.strftime("%Y%m%d%H%M%S")
    qn = data_time + "000"

    # Build CP (data content)
    cp = f"DataTime={data_time};{pollutant_code}-Rtd={value},{pollutant_code}-Flag=N"

    # Build data segment
    data_segment = (
        f"QN={qn};ST=32;CN=2011;PW=123456;"
        f"MN={device_id};Flag=4;CP=&&{cp}&&"
    )

    # Calculate CRC (simple implementation)
    crc = sum(data_segment.encode()) & 0xFFFF
    crc_hex = f"{crc:04X}"

    # Build complete packet
    data_len = len(data_segment)
    packet = f"##{data_len:04d}{data_segment}{crc_hex}\r\n"

    return packet.encode()


async def test_tdengine_connection():
    """Test TDengine connection."""
    print_step(1, "Testing TDengine Connection")

    client = get_tdengine_client()
    print(f"  Host: {client.host}")
    print(f"  Port: {client.port}")
    print(f"  Database: {client.database}")

    try:
        await client.connect()
        print_result(True, "Connected to TDengine successfully")
        return True
    except Exception as e:
        print_result(False, f"Failed to connect: {e}")
        return False


async def test_database_init():
    """Test database initialization."""
    print_step(2, "Initializing Database")

    client = get_tdengine_client()

    try:
        await client.init_database()
        print_result(True, "Database initialized successfully")

        # Verify super table exists
        result = await client.execute("SHOW STABLES")
        tables = [row[0] for row in result] if result else []
        if "monitoring_data" in tables:
            print_result(True, "Super table 'monitoring_data' exists")
        else:
            print_result(False, "Super table not found")

        return True
    except Exception as e:
        print_result(False, f"Failed to initialize: {e}")
        return False


async def test_direct_insert():
    """Test direct data insertion."""
    print_step(3, "Testing Direct Data Insertion")

    client = get_tdengine_client()
    test_device = f"DIRECTTEST{int(time.time()) % 10000:04d}"
    test_value = 25.5

    print(f"  Device ID: {test_device}")
    print(f"  Value: {test_value}")

    try:
        success = await client.insert_monitoring_data(
            device_id=test_device,
            pollutant_code="w01018",
            org_id=test_device[:8],
            timestamp=datetime.now(),
            value=test_value,
            flag="N",
            status=0
        )

        if success:
            print_result(True, "Data inserted successfully")

            # Query back to verify
            results = await client.query_monitoring_data(
                device_id=test_device,
                limit=1
            )

            if results and len(results) > 0:
                print_result(True, f"Data verified: {results[0]}")
                return True
            else:
                print_result(False, "Data not found after insert")
                return False
        else:
            print_result(False, "Insert returned False")
            return False

    except Exception as e:
        print_result(False, f"Insert failed: {e}")
        return False


def test_tcp_gateway():
    """Test TCP Gateway connection."""
    print_step(4, "Testing TCP Gateway")

    tcp_host = os.getenv("TCP_GATEWAY_HOST", "localhost")
    tcp_port = int(os.getenv("TCP_GATEWAY_PORT", "9880"))

    print(f"  Gateway: {tcp_host}:{tcp_port}")

    # Create test packet
    test_device = f"TCPTEST{int(time.time()) % 10000:04d}"
    test_value = 42.0
    packet = create_hj212_packet(test_device, "w01018", test_value)

    print(f"  Device ID: {test_device}")
    print(f"  Packet size: {len(packet)} bytes")

    response = send_tcp_packet(tcp_host, tcp_port, packet)

    if response is None:
        print_result(False, f"Cannot connect to TCP Gateway at {tcp_host}:{tcp_port}")
        print("  Hint: Make sure the backend service is running with TCP Gateway enabled")
        return False, test_device
    else:
        if response:
            print_result(True, f"Received ACK: {response[:50]}")
        else:
            print_result(True, "Packet sent (no ACK expected for this packet type)")
        return True, test_device


async def test_data_query(device_id: str):
    """Test data query after TCP insert."""
    print_step(5, "Verifying Data Storage")

    # Wait for data to be processed
    await asyncio.sleep(1)

    client = get_tdengine_client()

    try:
        results = await client.query_monitoring_data(
            device_id=device_id,
            limit=5
        )

        if results and len(results) > 0:
            print_result(True, f"Found {len(results)} records for {device_id}")
            for r in results:
                print(f"    - ts: {r['ts']}, value: {r['value']}, flag: {r['flag']}")
            return True
        else:
            print_result(False, f"No records found for {device_id}")
            return False

    except Exception as e:
        print_result(False, f"Query failed: {e}")
        return False


async def test_statistics():
    """Test statistics calculation."""
    print_step(6, "Testing Statistics Calculation")

    client = get_tdengine_client()

    # Insert multiple data points
    test_device = f"STATSTEST{int(time.time()) % 10000:04d}"
    values = [10.0, 20.0, 30.0, 40.0, 50.0]

    print(f"  Device ID: {test_device}")
    print(f"  Values: {values}")

    for i, val in enumerate(values):
        await client.insert_monitoring_data(
            device_id=test_device,
            pollutant_code="w01018",
            org_id=test_device[:8],
            timestamp=datetime.now(),
            value=val,
            flag="N",
            status=0
        )
        await asyncio.sleep(0.1)  # Small delay between inserts

    # Get statistics
    stats = await client.get_statistics(
        device_id=test_device,
        pollutant_code="w01018"
    )

    if stats and stats.get("count", 0) >= len(values):
        print_result(True, f"Statistics calculated: count={stats['count']}")
        print(f"    - min: {stats.get('min_value')}")
        print(f"    - max: {stats.get('max_value')}")
        print(f"    - avg: {stats.get('avg_value')}")
        return True
    else:
        print_result(False, "Statistics incomplete or missing")
        return False


async def main():
    """Run all tests."""
    print_header("EcoMind-AI TDengine Integration Test")

    results = {}

    # Test 1: TDengine Connection
    results["connection"] = await test_tdengine_connection()
    if not results["connection"]:
        print("\n❌ Cannot proceed without TDengine connection")
        print("\nTroubleshooting:")
        print("1. Start TDengine: docker-compose up -d tdengine")
        print("2. Check status: docker ps | grep tdengine")
        print("3. Check logs: docker logs ecomind-tdengine")
        return 1

    # Test 2: Database Init
    results["init"] = await test_database_init()

    # Test 3: Direct Insert
    results["direct_insert"] = await test_direct_insert()

    # Test 4: TCP Gateway
    tcp_success, tcp_device = test_tcp_gateway()
    results["tcp_gateway"] = tcp_success

    # Test 5: Verify TCP Data (only if gateway is running)
    if tcp_success:
        results["tcp_verify"] = await test_data_query(tcp_device)
    else:
        results["tcp_verify"] = None

    # Test 6: Statistics
    results["statistics"] = await test_statistics()

    # Print Summary
    print_header("Test Summary")

    passed = 0
    failed = 0
    skipped = 0

    for name, result in results.items():
        if result is True:
            status = "✓ PASSED"
            passed += 1
        elif result is False:
            status = "✗ FAILED"
            failed += 1
        else:
            status = "○ SKIPPED"
            skipped += 1
        print(f"  {name:20s} {status}")

    print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")

    # Cleanup
    client = get_tdengine_client()
    await client.close()

    if failed > 0:
        return 1
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
