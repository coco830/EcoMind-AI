"""
TDengine Schema Definition for Environmental Monitoring Data

This module defines the table structures for storing HJ212 protocol data
in TDengine time-series database.
"""

from typing import List, Dict, Any


class TDengineSchema:
    """TDengine database schema definitions"""

    # Database configuration
    DATABASE_NAME = "ecomind"
    KEEP_DAYS = 365  # Keep data for 1 year
    REPLICA = 1
    BLOCKS = 6

    # Super table for meters data
    METERS_SUPER_TABLE = "meters_data"

    @staticmethod
    def get_create_database_sql() -> str:
        """Get SQL for creating database"""
        return f"""
        CREATE DATABASE IF NOT EXISTS {TDengineSchema.DATABASE_NAME}
        KEEP {TDengineSchema.KEEP_DAYS}
        REPLICA {TDengineSchema.REPLICA}
        BLOCKS {TDengineSchema.BLOCKS}
        """

    @staticmethod
    def get_create_super_table_sql() -> str:
        """Get SQL for creating meters data super table"""
        return f"""
        CREATE STABLE IF NOT EXISTS {TDengineSchema.DATABASE_NAME}.{TDengineSchema.METERS_SUPER_TABLE} (
            ts TIMESTAMP,

            -- Water quality parameters (w series)
            w01001 FLOAT,    -- pH
            w01018 FLOAT,    -- COD
            w21003 FLOAT,    -- Ammonia nitrogen
            w21011 FLOAT,    -- Total phosphorus
            w21001 FLOAT,    -- Total nitrogen
            w01009 FLOAT,    -- Dissolved oxygen
            w01010 FLOAT,    -- Water temperature
            w01014 FLOAT,    -- Conductivity
            w01003 FLOAT,    -- Turbidity
            w19011 FLOAT,    -- Total residual chlorine

            -- Air quality parameters (a series)
            a01011 FLOAT,    -- Smoke flow rate
            a01012 FLOAT,    -- Smoke temperature
            a01013 FLOAT,    -- Smoke pressure
            a01014 FLOAT,    -- Smoke humidity
            a34013 FLOAT,    -- Particulate matter
            a21026 FLOAT,    -- SO2
            a21002 FLOAT,    -- NOx
            a21003 FLOAT,    -- CO
            a05001 FLOAT,    -- PM2.5
            a05002 FLOAT,    -- PM10

            -- Power parameters (d series) - 2025 version
            d10001 FLOAT,    -- Total active power
            d10002 FLOAT,    -- Total reactive power
            d10003 FLOAT,    -- Total apparent power
            d10004 FLOAT,    -- A-phase voltage
            d10005 FLOAT,    -- B-phase voltage
            d10006 FLOAT,    -- C-phase voltage
            d10007 FLOAT,    -- A-phase current
            d10008 FLOAT,    -- B-phase current
            d10009 FLOAT,    -- C-phase current
            d10010 FLOAT,    -- Power factor

            -- Production parameters (p series) - 2025 version
            p10001 FLOAT,    -- Fan current
            p10002 FLOAT,    -- Fan frequency
            p10003 FLOAT,    -- Fan speed
            p10004 FLOAT,    -- Dust collector pressure
            p10005 FLOAT,    -- Desulfurization tower level

            -- System info
            data_flag NCHAR(16),   -- Data flag (N/A/M/F/C/D/S/T/O)
            command_code NCHAR(8), -- Command code (2011/2051/2061)
            system_code NCHAR(8)   -- System code (31/32/22/44)
        ) TAGS (
            mn NCHAR(24),          -- Device ID (MN field)
            station_name NCHAR(64), -- Station name
            station_type NCHAR(16), -- Station type
            longitude FLOAT,        -- Longitude
            latitude FLOAT,         -- Latitude
            region NCHAR(32),       -- Region
            protocol_version INT    -- Protocol version (1=2017, 2=2025)
        )
        """

    @staticmethod
    def get_create_device_table_sql(mn: str, station_name: str = None,
                                    station_type: str = "pollution_source",
                                    longitude: float = 0.0, latitude: float = 0.0,
                                    region: str = None, protocol_version: int = 1) -> str:
        """
        Get SQL for creating a device-specific table

        Args:
            mn: Device ID (24 characters)
            station_name: Station name
            station_type: Type of monitoring station
            longitude: GPS longitude
            latitude: GPS latitude
            region: Region name
            protocol_version: Protocol version (1=2017, 2=2025)

        Returns:
            SQL statement for creating table
        """
        # Sanitize table name (replace special chars with underscore)
        table_name = f"device_{mn}".replace("-", "_").replace(" ", "_")

        # Handle None values
        station_name = station_name or mn
        region = region or "unknown"

        return f"""
        CREATE TABLE IF NOT EXISTS {TDengineSchema.DATABASE_NAME}.{table_name}
        USING {TDengineSchema.DATABASE_NAME}.{TDengineSchema.METERS_SUPER_TABLE}
        TAGS (
            '{mn}',
            '{station_name}',
            '{station_type}',
            {longitude},
            {latitude},
            '{region}',
            {protocol_version}
        )
        """

    @staticmethod
    def get_insert_sql(mn: str, timestamp: str, data: Dict[str, Any]) -> str:
        """
        Get SQL for inserting monitoring data

        Args:
            mn: Device ID
            timestamp: Timestamp in format 'YYYY-MM-DD HH:MM:SS.mmm'
            data: Dictionary of parameter values

        Returns:
            SQL insert statement
        """
        # Sanitize table name
        table_name = f"device_{mn}".replace("-", "_").replace(" ", "_")

        # Build column list and values
        columns = ["ts"]
        values = [f"'{timestamp}'"]

        # Add parameter values
        for key, value in data.items():
            if key.startswith(('w', 'a', 'd', 'p', 'i')):
                # Monitoring parameters
                columns.append(key.lower())
                if value is None:
                    values.append("NULL")
                else:
                    values.append(str(float(value)))
            elif key in ['data_flag', 'command_code', 'system_code']:
                # String fields
                columns.append(key)
                values.append(f"'{value}'")

        columns_str = ", ".join(columns)
        values_str = ", ".join(values)

        return f"""
        INSERT INTO {TDengineSchema.DATABASE_NAME}.{table_name}
        ({columns_str})
        VALUES ({values_str})
        """

    @staticmethod
    def get_query_latest_sql(mn: str, limit: int = 100) -> str:
        """Get SQL for querying latest data from a device"""
        table_name = f"device_{mn}".replace("-", "_").replace(" ", "_")
        return f"""
        SELECT * FROM {TDengineSchema.DATABASE_NAME}.{table_name}
        ORDER BY ts DESC
        LIMIT {limit}
        """

    @staticmethod
    def get_query_range_sql(mn: str, start_time: str, end_time: str) -> str:
        """Get SQL for querying data in time range"""
        table_name = f"device_{mn}".replace("-", "_").replace(" ", "_")
        return f"""
        SELECT * FROM {TDengineSchema.DATABASE_NAME}.{table_name}
        WHERE ts >= '{start_time}' AND ts <= '{end_time}'
        ORDER BY ts DESC
        """