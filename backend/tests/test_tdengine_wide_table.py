"""Tests for TDengine wide table functionality."""

import pytest
from datetime import datetime
from app.db.tdengine_client import TDengineClient, get_tdengine_client


@pytest.fixture
def tdengine_client():
    """Get mock TDengine client."""
    import os
    os.environ["TDENGINE_MOCK"] = "true"
    # Reset singleton
    global _tdengine_client
    from app.db import tdengine_client as tc_module
    tc_module._tdengine_client = None
    client = get_tdengine_client()
    return client


class TestTDengineWideTable:
    """Test cases for TDengine wide table operations."""

    @pytest.mark.asyncio
    async def test_insert_wide_monitoring_data(self, tdengine_client):
        """Should insert wide table data successfully."""
        client = tdengine_client

        pollutants = {
            "w01018": {"Rtd": 45.6, "Flag": "N"},
            "w21003": {"Rtd": 2.3, "Flag": "N"},
            "w01001": {"Rtd": 7.2, "Flag": "N"},
        }

        result = await client.insert_wide_monitoring_data(
            device_id="TESTDEV001",
            org_id="org001",
            timestamp=datetime.now(),
            pollutants=pollutants,
            data_type="realtime",
        )

        assert result is True
        assert len(client._mock_data) > 0

    @pytest.mark.asyncio
    async def test_insert_multiple_pollutants(self, tdengine_client):
        """Should handle many pollutants in one insert."""
        client = tdengine_client

        # Simulate many pollutants
        pollutants = {
            "w01018": {"Rtd": 45.6, "Flag": "N"},
            "w21003": {"Rtd": 2.3, "Flag": "N"},
            "w01001": {"Rtd": 7.2, "Flag": "N"},
            "w01010": {"Rtd": 25.5, "Flag": "N"},
            "w01009": {"Rtd": 8.1, "Flag": "N"},
            "w21001": {"Rtd": 15.0, "Flag": "N"},
            "w21011": {"Rtd": 0.5, "Flag": "N"},
            "w20120": {"Rtd": 0.0012, "Flag": "N"},
            "w20115": {"Rtd": 0.00005, "Flag": "N"},
            "w20111": {"Rtd": 0.00001, "Flag": "N"},
        }

        result = await client.insert_wide_monitoring_data(
            device_id="TESTDEV002",
            org_id="org001",
            timestamp=datetime.now(),
            pollutants=pollutants,
            data_type="realtime",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_insert_with_avg_values(self, tdengine_client):
        """Should handle Avg values for minute/hour data."""
        client = tdengine_client

        pollutants = {
            "w01018": {"Avg": 46.0, "Flag": "N"},
            "w21003": {"Avg": 2.5, "Flag": "N"},
        }

        result = await client.insert_wide_monitoring_data(
            device_id="TESTDEV003",
            org_id="org001",
            timestamp=datetime.now(),
            pollutants=pollutants,
            data_type="minute",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_query_wide_monitoring_data(self, tdengine_client):
        """Should query wide table data."""
        client = tdengine_client

        # Insert test data first
        await client.insert_wide_monitoring_data(
            device_id="TESTDEV004",
            org_id="org001",
            timestamp=datetime.now(),
            pollutants={"w01018": {"Rtd": 45.6, "Flag": "N"}},
            data_type="realtime",
        )

        # Query
        results = await client.query_wide_monitoring_data(
            device_id="TESTDEV004",
            limit=10,
        )

        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_data_types(self, tdengine_client):
        """Should correctly store data_type field."""
        client = tdengine_client

        # Test realtime
        await client.insert_wide_monitoring_data(
            device_id="TESTDEV005",
            org_id="org001",
            timestamp=datetime.now(),
            pollutants={"w01018": {"Rtd": 45.6}},
            data_type="realtime",
        )

        # Test minute
        await client.insert_wide_monitoring_data(
            device_id="TESTDEV005",
            org_id="org001",
            timestamp=datetime.now(),
            pollutants={"w01018": {"Avg": 46.0}},
            data_type="minute",
        )

        # Test hour
        await client.insert_wide_monitoring_data(
            device_id="TESTDEV005",
            org_id="org001",
            timestamp=datetime.now(),
            pollutants={"w01018": {"Avg": 47.0}},
            data_type="hour",
        )

        # Check mock data has all types
        data_types = {d.get("data_type") for d in client._mock_data
                     if d.get("device_id") == "TESTDEV005"}
        assert "realtime" in data_types
        assert "minute" in data_types
        assert "hour" in data_types


class TestSQLGeneration:
    """Test SQL generation for wide table."""

    def test_generate_pollutant_columns(self):
        """Should generate correct column definitions."""
        client = TDengineClient()
        columns = client._generate_pollutant_columns()

        # Should have many columns
        assert "w01018_val DOUBLE" in columns
        assert "w01018_flag NCHAR(8)" in columns
        assert "w21003_val DOUBLE" in columns
        assert "w20111_val DOUBLE" in columns

    def test_sanitize_identifier(self):
        """Should sanitize identifiers correctly."""
        client = TDengineClient()

        assert client.sanitize_identifier("w01018") == "w01018"
        assert client.sanitize_identifier("DEVICE001") == "DEVICE001"

        with pytest.raises(ValueError):
            client.sanitize_identifier("bad;identifier")

        with pytest.raises(ValueError):
            client.sanitize_identifier("bad--identifier")

    def test_escape_string(self):
        """Should escape strings correctly."""
        client = TDengineClient()

        assert client.escape_string("normal") == "'normal'"
        assert client.escape_string("with'quote") == "'with\\'quote'"
        assert client.escape_string(None) == "NULL"

    def test_format_value(self):
        """Should format values correctly."""
        client = TDengineClient()

        assert client.format_value(123) == "123"
        assert client.format_value(45.67) == "45.67"
        assert client.format_value("text") == "'text'"
        assert client.format_value(None) == "NULL"
        # Boolean handling - TDengine accepts various formats
        assert client.format_value(True) in ("TRUE", "True", "true", "1")
