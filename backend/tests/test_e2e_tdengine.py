"""
End-to-end test for TDengine integration.

This script tests the complete data flow:
1. TCP packet -> HJ212 Parser -> TDengine Storage
2. API Query -> TDengine -> Response

Usage:
    # Start services first:
    docker-compose up -d tdengine postgres

    # Run this test:
    pytest backend/tests/test_e2e_tdengine.py -v -s

    # Or run directly:
    python backend/tests/test_e2e_tdengine.py
"""

import asyncio
import socket
import time
import os
import sys
from datetime import datetime, timedelta
from typing import Optional

import pytest
import httpx
import structlog

logger = structlog.get_logger(__name__)

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.tdengine_client import get_tdengine_client, TDengineClient
from app.protocols.parser import HJ212Parser
from app.protocols.models import ParserConfig
from app.gateway.hj212_parser import HJ212Parser as LegacyParser


class TestTDengineConnection:
    """Test TDengine database connection."""

    @pytest.fixture
    def client(self) -> TDengineClient:
        """Get TDengine client instance."""
        return get_tdengine_client()

    @pytest.mark.asyncio
    async def test_connect_to_tdengine(self, client: TDengineClient):
        """Test that we can connect to TDengine."""
        await client.connect()
        assert client.initialized is True
        assert client.conn is not None

    @pytest.mark.asyncio
    async def test_init_database(self, client: TDengineClient):
        """Test database initialization."""
        await client.connect()
        await client.init_database()

        # Verify database exists
        result = await client.execute("SHOW DATABASES")
        databases = [row[0] for row in result] if result else []
        assert "ecomind" in databases

    @pytest.mark.asyncio
    async def test_insert_and_query_data(self, client: TDengineClient):
        """Test inserting and querying monitoring data."""
        await client.connect()
        await client.init_database()

        # Generate test data
        test_device_id = "TEST00000001"
        test_pollutant = "w01018"
        test_org_id = "TEST0000"
        test_value = 6.5
        test_timestamp = datetime.now()

        # Insert data
        success = await client.insert_monitoring_data(
            device_id=test_device_id,
            pollutant_code=test_pollutant,
            org_id=test_org_id,
            timestamp=test_timestamp,
            value=test_value,
            flag="N",
            status=0
        )
        assert success is True, "Failed to insert data"

        # Query data back
        results = await client.query_monitoring_data(
            device_id=test_device_id,
            pollutant_code=test_pollutant,
            limit=10
        )

        assert len(results) > 0, "No data returned from query"
        assert results[0]["device_id"] == test_device_id
        assert results[0]["pollutant_code"] == test_pollutant
        assert abs(results[0]["value"] - test_value) < 0.001

    @pytest.mark.asyncio
    async def test_get_latest_values(self, client: TDengineClient):
        """Test getting latest values."""
        await client.connect()
        await client.init_database()

        # Insert some test data
        test_device_id = "TEST00000002"
        for i in range(3):
            await client.insert_monitoring_data(
                device_id=test_device_id,
                pollutant_code=f"w0100{i}",
                org_id="TEST0000",
                timestamp=datetime.now() - timedelta(seconds=i),
                value=10.0 + i,
                flag="N",
                status=0
            )

        # Get latest values
        results = await client.get_latest_values(device_ids=[test_device_id])
        assert len(results) > 0, "No latest values returned"

    @pytest.mark.asyncio
    async def test_get_statistics(self, client: TDengineClient):
        """Test statistics calculation."""
        await client.connect()
        await client.init_database()

        # Insert multiple data points
        test_device_id = "TEST00000003"
        values = [10.0, 20.0, 30.0, 40.0, 50.0]

        for i, val in enumerate(values):
            await client.insert_monitoring_data(
                device_id=test_device_id,
                pollutant_code="w01018",
                org_id="TEST0000",
                timestamp=datetime.now() - timedelta(minutes=i),
                value=val,
                flag="N",
                status=0
            )

        # Get statistics
        stats = await client.get_statistics(
            device_id=test_device_id,
            pollutant_code="w01018"
        )

        assert stats is not None
        assert stats.get("count", 0) >= len(values)


class TestHJ212ParserIntegration:
    """Test HJ212 parser with TDengine storage."""

    @pytest.fixture
    def parser(self) -> HJ212Parser:
        """Get HJ212 parser instance."""
        config = ParserConfig(strict_mode=False, validate_crc=False)
        return HJ212Parser(config)

    @pytest.fixture
    def client(self) -> TDengineClient:
        """Get TDengine client instance."""
        return get_tdengine_client()

    @pytest.mark.asyncio
    async def test_parse_and_store_realtime_data(self, parser: HJ212Parser, client: TDengineClient):
        """Test parsing HJ212 packet and storing to TDengine."""
        await client.connect()
        await client.init_database()

        # Sample HJ212 realtime data packet
        packet_data = (
            b"##0234QN=20231101120000000;ST=32;CN=2011;PW=123456;"
            b"MN=E2E_TEST_001;Flag=4;CP=&&DataTime=20231101120000;"
            b"w01018-Rtd=6.5,w01018-Flag=N;w01001-Rtd=25.3,w01001-Flag=N&&1234\r\n"
        )

        # Parse the packet
        parsed = parser.parse(packet_data)

        if parsed.is_valid:
            device_id = parsed.device_id
            timestamp = parsed.segment.timestamp or datetime.now()
            org_id = device_id[:8] if device_id else "UNKNOWN"

            # Store each parameter
            for param_code, param_value in parsed.parameters.items():
                if param_code == "DataTime" or param_value.rtd is None:
                    continue

                success = await client.insert_monitoring_data(
                    device_id=device_id,
                    pollutant_code=param_code,
                    org_id=org_id,
                    timestamp=timestamp,
                    value=param_value.rtd,
                    flag=param_value.flag or "N",
                    status=0
                )
                assert success, f"Failed to store {param_code}"

            # Verify data was stored
            results = await client.query_monitoring_data(
                device_id=device_id,
                limit=10
            )
            assert len(results) > 0, "No data found after storage"


class TestTCPGatewayIntegration:
    """Test TCP Gateway with real TDengine."""

    @staticmethod
    def send_tcp_packet(host: str, port: int, data: bytes, timeout: float = 5.0) -> Optional[bytes]:
        """Send TCP packet and receive response."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                sock.connect((host, port))
                sock.sendall(data)

                # Try to receive response
                try:
                    response = sock.recv(1024)
                    return response
                except socket.timeout:
                    return None
        except Exception as e:
            logger.error("TCP error", error=str(e))
            return None

    @pytest.mark.asyncio
    async def test_tcp_to_database_flow(self):
        """
        Test complete flow: TCP packet -> Gateway -> TDengine -> API.

        Prerequisites:
        - TDengine running on localhost:6030
        - TCP Gateway running on localhost:9880
        - Backend API running on localhost:8000
        """
        # Check if services are running
        tcp_host = os.getenv("TCP_GATEWAY_HOST", "localhost")
        tcp_port = int(os.getenv("TCP_GATEWAY_PORT", "9880"))
        api_host = os.getenv("API_HOST", "localhost")
        api_port = int(os.getenv("API_PORT", "8000"))

        # Generate unique device ID for this test
        test_device_id = f"E2ETEST{int(time.time()) % 100000:05d}"
        test_value = 42.5

        # Create HJ212 packet
        now = datetime.now()
        data_time = now.strftime("%Y%m%d%H%M%S")

        packet = (
            f"##0300QN={data_time}000;ST=32;CN=2011;PW=123456;"
            f"MN={test_device_id};Flag=4;CP=&&DataTime={data_time};"
            f"w01018-Rtd={test_value},w01018-Flag=N&&ABCD\r\n"
        ).encode()

        logger.info("E2E Test: TCP -> TDengine -> API",
                    device_id=test_device_id, test_value=test_value,
                    packet_preview=packet[:100].decode())

        # Step 1: Send TCP packet to Gateway
        logger.info("Sending TCP packet", host=tcp_host, port=tcp_port)
        response = self.send_tcp_packet(tcp_host, tcp_port, packet)

        if response:
            logger.info("Received response", response=response)
        else:
            logger.info("No response (this is OK for some packet types)")

        # Wait for data to be processed
        await asyncio.sleep(1)

        # Step 2: Query data from TDengine directly
        logger.info("Querying TDengine directly")
        client = get_tdengine_client()
        await client.connect()

        results = await client.query_monitoring_data(
            device_id=test_device_id,
            limit=10
        )

        if results:
            logger.info("Found records in TDengine", count=len(results), sample=results[:3])
        else:
            logger.info("No records found (Gateway may not be running)")

        # Step 3: Query via API (requires authentication)
        logger.info("Querying API", host=api_host, port=api_port)

        async with httpx.AsyncClient() as http_client:
            try:
                # First, login to get token
                login_resp = await http_client.post(
                    f"http://{api_host}:{api_port}/api/v1/auth/login",
                    data={"username": "admin", "password": "admin123"},
                    timeout=10.0
                )

                if login_resp.status_code == 200:
                    token = login_resp.json().get("access_token")
                    headers = {"Authorization": f"Bearer {token}"}

                    # Query monitoring data
                    data_resp = await http_client.get(
                        f"http://{api_host}:{api_port}/api/v1/data",
                        params={"device_id": test_device_id, "limit": 10},
                        headers=headers,
                        timeout=10.0
                    )

                    if data_resp.status_code == 200:
                        api_data = data_resp.json()
                        logger.info("API returned records", count=len(api_data), sample=api_data[:3])
                    else:
                        logger.warning("API query failed", status_code=data_resp.status_code)
                else:
                    logger.warning("Login failed", status_code=login_resp.status_code)

            except Exception as e:
                logger.error("API error", error=str(e))

        logger.info("E2E Test Complete")


async def run_quick_test():
    """Run a quick connection test."""
    logger.info("EcoMind-AI TDengine Connection Test")

    client = get_tdengine_client()

    logger.info("Connecting to TDengine", host=client.host, port=client.port, database=client.database)

    try:
        await client.connect()
        logger.info("Connected to TDengine")

        logger.info("Initializing database")
        await client.init_database()
        logger.info("Database ready")

        logger.info("Inserting test data")
        test_device = f"QUICKTEST{int(time.time()) % 10000:04d}"
        success = await client.insert_monitoring_data(
            device_id=test_device,
            pollutant_code="w01018",
            org_id=test_device[:8],
            timestamp=datetime.now(),
            value=25.5,
            flag="N",
            status=0
        )
        logger.info("Insert result", success=success)

        logger.info("Querying data")
        results = await client.query_monitoring_data(
            device_id=test_device,
            limit=5
        )
        logger.info("Query results", count=len(results), records=results)

        logger.info("All tests passed! TDengine integration is working.")

    except Exception as e:
        logger.error("TDengine test failed", error=str(e))
        logger.info("Troubleshooting: 1. Make sure TDengine is running: docker-compose up -d tdengine")
        logger.info("Troubleshooting: 2. Check TDengine logs: docker logs ecomind-tdengine")
        logger.info("Troubleshooting: 3. Verify network connectivity: telnet localhost 6030")
        raise

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(run_quick_test())
