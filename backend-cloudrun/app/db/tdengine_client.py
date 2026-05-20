"""TDengine database client with REST API support and SQL injection protection.

支持宽表模式：所有污染物指标作为列存储，每条记录包含一个时间点的全部监测数据。
符合 HJ 212-2017/2025 标准。
"""

import os
import re
from typing import Any, Dict, List, Optional
from datetime import datetime
import asyncio
import structlog
import httpx

from app.core.config import get_settings
from app.core.pollutant_library import POLLUTANT_MAP, get_pollutant_info

logger = structlog.get_logger()
settings = get_settings()

# Check if mock mode is enabled (for development without TDengine)
MOCK_MODE = os.getenv("TDENGINE_MOCK", "false").lower() in ("true", "1", "yes")


class TDengineClient:
    """
    Singleton TDengine client using REST API with SQL injection protection.

    Uses TDengine's REST API (port 6041) which doesn't require native client library.
    """

    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize TDengine client (only once due to singleton)."""
        if not hasattr(self, '_init_done'):
            self.initialized = False
            self.mock_mode = MOCK_MODE
            self.host = settings.tdengine_host
            self.port = settings.tdengine_port
            self.rest_port = 6041  # REST API port
            self.user = settings.tdengine_user
            self.password = settings.tdengine_password
            self.database = settings.tdengine_database
            self._mock_data: List[Dict[str, Any]] = []  # In-memory storage for mock mode
            self._http_client: Optional[httpx.AsyncClient] = None
            self._init_done = True

            if self.mock_mode:
                logger.warning("TDengine running in MOCK mode - data stored in memory only")
            else:
                logger.info("TDengine REST client initialized",
                           host=self.host, rest_port=self.rest_port, database=self.database)

    @property
    def rest_url(self) -> str:
        """Get TDengine REST API URL."""
        return f"http://{self.host}:{self.rest_port}/rest/sql"

    @property
    def rest_url_with_db(self) -> str:
        """Get TDengine REST API URL with database."""
        return f"http://{self.host}:{self.rest_port}/rest/sql/{self.database}"

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                auth=(self.user, self.password),
                timeout=30.0
            )
        return self._http_client

    async def connect(self, retry_count: int = 3, retry_delay: float = 2.0):
        """
        Establish connection to TDengine REST API with retry mechanism.
        """
        # Mock mode: skip connection
        if self.mock_mode:
            self.initialized = True
            logger.info("TDengine mock mode - connection skipped")
            return

        if self.initialized:
            return

        async with self._lock:
            if self.initialized:
                return

            last_error = None
            for attempt in range(retry_count):
                try:
                    logger.info(f"Connecting to TDengine REST API (attempt {attempt + 1}/{retry_count})",
                               host=self.host, port=self.rest_port)

                    client = await self._get_http_client()
                    # Test connection with simple query
                    response = await client.post(
                        self.rest_url,
                        data="SELECT SERVER_VERSION()"
                    )

                    if response.status_code == 200:
                        result = response.json()
                        # Support both TDengine 2.x (status) and 3.x (code) response format
                        if result.get("status") == "succ" or result.get("code") == 0:
                            version = result.get("data", [[]])[0][0] if result.get("data") else "unknown"
                            self.initialized = True
                            logger.info("TDengine REST connection established",
                                       host=self.host, port=self.rest_port, version=version)
                            return
                        else:
                            error_msg = result.get("desc") or result.get("status", "Unknown error")
                            raise ConnectionError(f"TDengine error: {error_msg}")
                    else:
                        raise ConnectionError(f"HTTP error: {response.status_code}")

                except Exception as e:
                    last_error = e
                    logger.warning(f"TDengine connection attempt {attempt + 1} failed",
                                  error=str(e))
                    if attempt < retry_count - 1:
                        await asyncio.sleep(retry_delay)

            logger.error("Failed to connect to TDengine after all retries",
                        error=str(last_error))
            raise ConnectionError(f"Cannot connect to TDengine: {last_error}")

    async def close(self):
        """Close TDengine connection."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
            self.initialized = False
            logger.info("TDengine connection closed")

    @staticmethod
    def sanitize_identifier(identifier: str) -> str:
        """
        Sanitize database/table/column identifiers to prevent SQL injection.

        Only allows alphanumeric characters and underscores.
        """
        if not re.match(r'^[a-zA-Z0-9_]+$', identifier):
            raise ValueError(f"Invalid identifier: {identifier}")
        return identifier

    @staticmethod
    def escape_string(value: str) -> str:
        """
        Escape string values for SQL queries.

        Escapes single quotes and backslashes.
        """
        if value is None:
            return "NULL"
        # Escape backslashes first, then single quotes
        value = value.replace("\\", "\\\\")
        value = value.replace("'", "\\'")
        return f"'{value}'"

    @staticmethod
    def format_value(value: Any) -> str:
        """
        Format a value for safe SQL insertion.

        Handles different data types appropriately.
        """
        if value is None:
            return "NULL"
        elif isinstance(value, str):
            return TDengineClient.escape_string(value)
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        elif isinstance(value, datetime):
            return f"'{value.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}'"
        else:
            raise ValueError(f"Unsupported value type: {type(value)}")

    async def execute(self, sql: str, params: Optional[Dict[str, Any]] = None, use_db: bool = True) -> Any:
        """
        Execute a SQL query via REST API with parameter substitution.

        Args:
            sql: SQL query template with :param_name placeholders
            params: Dictionary of parameter values
            use_db: Whether to use the database endpoint

        Returns:
            Query results as a list or affected rows count
        """
        if not self.initialized:
            await self.connect()

        # Mock mode: log and return empty
        if self.mock_mode:
            logger.debug("Mock execute", sql=sql[:100])
            return []

        # Process parameters
        if params:
            for key, value in params.items():
                placeholder = f":{key}"

                # Check if it's an identifier (table/column name) or a value
                identifier_pattern = rf"(FROM|INTO|TABLE|UPDATE|DELETE FROM)\s+{re.escape(placeholder)}"
                if re.search(identifier_pattern, sql, re.IGNORECASE):
                    safe_value = self.sanitize_identifier(str(value))
                    sql = sql.replace(placeholder, safe_value)
                else:
                    safe_value = self.format_value(value)
                    sql = sql.replace(placeholder, safe_value)

        logger.debug("Executing TDengine query", sql=sql[:200])

        try:
            client = await self._get_http_client()
            url = self.rest_url_with_db if use_db else self.rest_url

            response = await client.post(url, data=sql)

            if response.status_code != 200:
                raise Exception(f"HTTP error: {response.status_code}")

            result = response.json()

            # Support both TDengine 2.x (status) and 3.x (code) response format
            if result.get("status") != "succ" and result.get("code") != 0:
                error_msg = result.get("desc") or result.get("status", "Unknown error")
                raise Exception(f"TDengine error: {error_msg}")

            # For SELECT queries, return data
            if sql.strip().upper().startswith("SELECT"):
                return result.get("data", [])
            else:
                # For non-SELECT, return affected rows
                return result.get("rows", 0)

        except Exception as e:
            logger.error("TDengine query execution failed", sql=sql[:200], error=str(e))
            raise

    async def init_database(self):
        """Initialize TDengine database and tables with wide table schema.

        宽表模式：每个污染物指标作为独立列存储
        - 每个污染物有 _val (数值) 和 _flag (标记) 两列
        - 支持动态添加新污染物列
        """
        if not self.initialized:
            await self.connect()

        # Mock mode: skip database init
        if self.mock_mode:
            logger.info("Mock mode - database initialization skipped")
            return

        try:
            # Create database if not exists
            db_name = self.sanitize_identifier(self.database)
            await self.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}", use_db=False)

            # 生成所有污染物列定义
            pollutant_columns = self._generate_pollutant_columns()

            # Create super table for wide-table monitoring data
            create_sql = f"""
                CREATE STABLE IF NOT EXISTS meters_data (
                    ts TIMESTAMP,
                    data_type NCHAR(16),
                    {pollutant_columns}
                ) TAGS (
                    device_id NCHAR(64),
                    org_id NCHAR(64)
                )
            """
            await self.execute(create_sql)

            # 保留旧的窄表以便兼容（如果需要可以删除）
            await self.execute("""
                CREATE STABLE IF NOT EXISTS monitoring_data (
                    ts TIMESTAMP,
                    value DOUBLE,
                    flag NCHAR(8),
                    status INT
                ) TAGS (
                    device_id NCHAR(64),
                    pollutant_code NCHAR(32),
                    org_id NCHAR(64)
                )
            """)

            logger.info("TDengine database initialized successfully",
                       pollutant_count=len(POLLUTANT_MAP))

        except Exception as e:
            logger.error("Failed to initialize TDengine database", error=str(e))
            raise

    def _generate_pollutant_columns(self) -> str:
        """生成所有污染物的列定义 SQL"""
        columns = []
        for code in POLLUTANT_MAP.keys():
            # 每个污染物有 value 和 flag 两列
            columns.append(f"{code}_val DOUBLE")
            columns.append(f"{code}_flag NCHAR(8)")
        return ",\n                    ".join(columns)

    async def alter_table_add_columns(self, new_pollutant_codes: List[str]) -> bool:
        """
        动态添加新污染物列到超级表

        Args:
            new_pollutant_codes: 新的污染物编码列表

        Returns:
            是否成功添加
        """
        if self.mock_mode:
            logger.info("Mock mode - alter table skipped", codes=new_pollutant_codes)
            return True

        try:
            for code in new_pollutant_codes:
                safe_code = self.sanitize_identifier(code.lower())
                # 添加 value 列
                await self.execute(
                    f"ALTER STABLE meters_data ADD COLUMN {safe_code}_val DOUBLE"
                )
                # 添加 flag 列
                await self.execute(
                    f"ALTER STABLE meters_data ADD COLUMN {safe_code}_flag NCHAR(8)"
                )
                logger.info("Added new pollutant columns", code=code)
            return True
        except Exception as e:
            # 如果列已存在会报错，可以忽略
            if "duplicated column" in str(e).lower() or "column already exists" in str(e).lower():
                logger.debug("Column already exists", codes=new_pollutant_codes)
                return True
            logger.error("Failed to alter table", error=str(e))
            return False

    async def insert_monitoring_data(
        self,
        device_id: str,
        pollutant_code: str,
        org_id: str,
        timestamp: datetime,
        value: float,
        flag: str = "N",
        status: int = 0
    ) -> bool:
        """
        Insert monitoring data with SQL injection protection.

        All parameters are properly sanitized before insertion.
        """
        # Mock mode: store in memory
        if self.mock_mode:
            data = {
                "ts": timestamp,
                "device_id": device_id,
                "pollutant_code": pollutant_code,
                "org_id": org_id,
                "value": value,
                "flag": flag,
                "status": status
            }
            self._mock_data.append(data)
            logger.debug("Mock insert", device_id=device_id, value=value)
            return True

        # Create safe table name
        table_name = f"d_{self.sanitize_identifier(device_id)}_{self.sanitize_identifier(pollutant_code)}"

        sql = """
            INSERT INTO :table_name USING monitoring_data
            TAGS (:device_id, :pollutant_code, :org_id)
            VALUES (:ts, :value, :flag, :status)
        """

        params = {
            "table_name": table_name,
            "device_id": device_id,
            "pollutant_code": pollutant_code,
            "org_id": org_id,
            "ts": timestamp,
            "value": value,
            "flag": flag,
            "status": status
        }

        try:
            result = await self.execute(sql, params)
            success = result is not None and (isinstance(result, int) and result >= 0 or result == [])
            if success:
                logger.debug("Inserted monitoring data",
                            device_id=device_id, pollutant_code=pollutant_code, value=value)
            return success
        except Exception as e:
            logger.error("Failed to insert monitoring data",
                        device_id=device_id, pollutant_code=pollutant_code, error=str(e))
            return False

    async def insert_wide_monitoring_data(
        self,
        device_id: str,
        org_id: str,
        timestamp: datetime,
        pollutants: Dict[str, Dict[str, Any]],
        data_type: str = "realtime"
    ) -> bool:
        """
        宽表模式批量插入监测数据

        一次写入同一时间点的所有污染物数据，效率更高。

        Args:
            device_id: 设备唯一标识 (MN)
            org_id: 组织ID
            timestamp: 数据时间戳
            pollutants: 污染物数据字典，格式如:
                {
                    "w01018": {"Rtd": 45.6, "Flag": "N"},
                    "w21003": {"Rtd": 2.3, "Flag": "N"}
                }
            data_type: 数据类型 (realtime/minute/hour)

        Returns:
            是否成功插入
        """
        # Mock mode: store in memory (for wide table)
        if self.mock_mode:
            data = {
                "ts": timestamp,
                "device_id": device_id,
                "org_id": org_id,
                "data_type": data_type,
                "pollutants": pollutants
            }
            self._mock_data.append(data)
            logger.debug("Mock wide insert", device_id=device_id,
                        pollutant_count=len(pollutants))
            return True

        try:
            # 构建动态列名和值
            columns = ["ts", "data_type"]
            values = [self.format_value(timestamp), self.escape_string(data_type)]

            # 处理未知的污染物编码
            unknown_codes = []

            for pol_code, pol_data in pollutants.items():
                code = pol_code.lower()

                # 检查是否为已知污染物
                if code not in POLLUTANT_MAP and code.startswith("w"):
                    unknown_codes.append(code)

                # 获取值 (优先 Rtd, 其次 Avg)
                value = pol_data.get("Rtd") or pol_data.get("Avg")
                flag = pol_data.get("Flag", "N")

                if value is not None:
                    try:
                        safe_code = self.sanitize_identifier(code)
                        columns.append(f"{safe_code}_val")
                        values.append(str(float(value)))
                        columns.append(f"{safe_code}_flag")
                        values.append(self.escape_string(str(flag)))
                    except (ValueError, TypeError) as e:
                        logger.warning("Invalid pollutant value",
                                      code=code, value=value, error=str(e))

            # 如果有未知污染物，尝试动态添加列
            if unknown_codes:
                logger.info("Detected unknown pollutant codes, attempting to add columns",
                           codes=unknown_codes)
                await self.alter_table_add_columns(unknown_codes)

            # 构建 INSERT 语句
            table_name = f"m_{self.sanitize_identifier(device_id)}"

            sql = f"""
                INSERT INTO {table_name} USING meters_data
                TAGS ({self.escape_string(device_id)}, {self.escape_string(org_id)})
                ({', '.join(columns)})
                VALUES ({', '.join(values)})
            """

            result = await self.execute(sql)
            success = result is not None and (isinstance(result, int) and result >= 0 or result == [])

            if success:
                logger.debug("Inserted wide monitoring data",
                            device_id=device_id, pollutant_count=len(pollutants))
            return success

        except Exception as e:
            logger.error("Failed to insert wide monitoring data",
                        device_id=device_id, error=str(e))
            return False

    async def query_wide_monitoring_data(
        self,
        device_id: str,
        pollutant_codes: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        宽表查询监测数据

        Args:
            device_id: 设备ID
            pollutant_codes: 要查询的污染物编码列表，为空则查询所有
            start_time: 开始时间
            end_time: 结束时间
            limit: 最大返回记录数

        Returns:
            监测数据列表
        """
        if self.mock_mode:
            results = [r for r in self._mock_data if r.get("device_id") == device_id]
            if start_time:
                results = [r for r in results if r.get("ts", datetime.min) >= start_time]
            if end_time:
                results = [r for r in results if r.get("ts", datetime.max) <= end_time]
            results.sort(key=lambda x: x.get("ts", datetime.min), reverse=True)
            return results[:limit]

        # 构建查询列
        if pollutant_codes:
            select_cols = ["ts", "data_type"]
            for code in pollutant_codes:
                safe_code = self.sanitize_identifier(code.lower())
                select_cols.append(f"{safe_code}_val")
                select_cols.append(f"{safe_code}_flag")
            columns_str = ", ".join(select_cols)
        else:
            columns_str = "*"

        # 构建 WHERE
        conditions = [f"device_id = {self.escape_string(device_id)}"]
        if start_time:
            conditions.append(f"ts >= {self.format_value(start_time)}")
        if end_time:
            conditions.append(f"ts <= {self.format_value(end_time)}")

        where_clause = " AND ".join(conditions)

        if not isinstance(limit, int) or limit < 1 or limit > 10000:
            limit = 1000

        sql = f"""
            SELECT {columns_str}
            FROM meters_data
            WHERE {where_clause}
            ORDER BY ts DESC
            LIMIT {limit}
        """

        try:
            result = await self.execute(sql)
            # 转换为字典列表（需要根据实际返回的列名处理）
            return result if result else []
        except Exception as e:
            logger.error("Failed to query wide monitoring data",
                        device_id=device_id, error=str(e))
            return []

    async def query_monitoring_data(
        self,
        device_id: Optional[str] = None,
        pollutant_code: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Query monitoring data with SQL injection protection.

        All parameters are properly sanitized before querying.
        """
        # Mock mode: filter from memory
        if self.mock_mode:
            results = self._mock_data.copy()

            if device_id:
                results = [r for r in results if r["device_id"] == device_id]
            if pollutant_code:
                results = [r for r in results if r["pollutant_code"] == pollutant_code]
            if start_time:
                results = [r for r in results if r["ts"] >= start_time]
            if end_time:
                results = [r for r in results if r["ts"] <= end_time]

            # Sort by timestamp descending and limit
            results.sort(key=lambda x: x["ts"], reverse=True)
            return results[:limit]

        # Build WHERE conditions safely
        conditions = []
        params = {}

        if device_id:
            conditions.append("device_id = :device_id")
            params["device_id"] = device_id

        if pollutant_code:
            conditions.append("pollutant_code = :pollutant_code")
            params["pollutant_code"] = pollutant_code

        if start_time:
            conditions.append("ts >= :start_time")
            params["start_time"] = start_time

        if end_time:
            conditions.append("ts <= :end_time")
            params["end_time"] = end_time

        # Build the query (TDengine 2.x doesn't support "1=1")
        where_clause = " AND ".join(conditions) if conditions else ""

        # Validate and sanitize limit
        if not isinstance(limit, int) or limit < 1 or limit > 10000:
            limit = 1000

        # Build query with optional WHERE clause
        if where_clause:
            sql = f"""
                SELECT ts, device_id, pollutant_code, value, flag, status
                FROM monitoring_data
                WHERE {where_clause}
                ORDER BY ts DESC
                LIMIT {limit}
            """
        else:
            sql = f"""
                SELECT ts, device_id, pollutant_code, value, flag, status
                FROM monitoring_data
                ORDER BY ts DESC
                LIMIT {limit}
            """

        try:
            result = await self.execute(sql, params)

            # Convert to list of dicts
            if result:
                keys = ['ts', 'device_id', 'pollutant_code', 'value', 'flag', 'status']
                return [dict(zip(keys, row)) for row in result]
            return []

        except Exception as e:
            logger.error("Failed to query monitoring data", error=str(e))
            return []

    async def get_latest_values(
        self,
        device_ids: Optional[List[str]] = None,
        pollutant_code: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get latest monitoring values with SQL injection protection.
        """
        # Mock mode: get latest from memory
        if self.mock_mode:
            results = self._mock_data.copy()
            if device_ids:
                results = [r for r in results if r["device_id"] in device_ids]
            if pollutant_code:
                results = [r for r in results if r["pollutant_code"] == pollutant_code]

            # Group by device_id and pollutant_code, get latest
            latest = {}
            for r in results:
                key = (r["device_id"], r["pollutant_code"])
                if key not in latest or r["ts"] > latest[key]["ts"]:
                    latest[key] = r

            return list(latest.values())[:limit]

        # Validate and sanitize limit
        if not isinstance(limit, int) or limit < 1 or limit > 1000:
            limit = 50

        where_clauses = []
        if device_ids:
            safe_ids = [self.escape_string(did) for did in device_ids]
            where_clauses.append(f"device_id IN ({','.join(safe_ids)})")
        if pollutant_code:
            where_clauses.append(f"pollutant_code = {self.escape_string(pollutant_code)}")

        device_filter = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        sql = f"""
            SELECT LAST_ROW(ts, value, flag, status), device_id, pollutant_code
            FROM monitoring_data
            {device_filter}
            GROUP BY device_id, pollutant_code
            LIMIT {limit}
        """

        try:
            result = await self.execute(sql)

            if result:
                keys = ['ts', 'value', 'flag', 'status', 'device_id', 'pollutant_code']
                return [dict(zip(keys, row)) for row in result]
            return []

        except Exception as e:
            logger.error("Failed to get latest values", error=str(e))
            return []

    async def get_statistics(
        self,
        device_id: str,
        pollutant_code: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get statistics for monitoring data with SQL injection protection.
        """
        # Mock mode: calculate from memory
        if self.mock_mode:
            results = [r for r in self._mock_data if r["device_id"] == device_id]
            if pollutant_code:
                results = [r for r in results if r["pollutant_code"] == pollutant_code]
            if start_time:
                results = [r for r in results if r["ts"] >= start_time]
            if end_time:
                results = [r for r in results if r["ts"] <= end_time]

            if not results:
                return {}

            values = [r["value"] for r in results]
            return {
                "device_id": device_id,
                "pollutant_code": pollutant_code or "all",
                "min_value": min(values),
                "max_value": max(values),
                "avg_value": sum(values) / len(values),
                "count": len(values),
                "std_dev": None,
                "start_time": start_time.isoformat() if start_time else None,
                "end_time": end_time.isoformat() if end_time else None
            }

        # Build WHERE conditions safely using parameters
        conditions = ["device_id = :device_id"]
        params = {"device_id": device_id}

        if pollutant_code:
            conditions.append("pollutant_code = :pollutant_code")
            params["pollutant_code"] = pollutant_code

        if start_time:
            conditions.append("ts >= :start_time")
            params["start_time"] = start_time

        if end_time:
            conditions.append("ts <= :end_time")
            params["end_time"] = end_time

        where_clause = " AND ".join(conditions)

        sql = f"""
            SELECT
                MIN(value) as min_value,
                MAX(value) as max_value,
                AVG(value) as avg_value,
                COUNT(*) as count,
                STDDEV(value) as std_dev
            FROM monitoring_data
            WHERE {where_clause}
        """

        try:
            result = await self.execute(sql, params)

            if result and len(result) > 0:
                row = result[0]
                return {
                    "device_id": device_id,
                    "pollutant_code": pollutant_code or "all",
                    "min_value": row[0],
                    "max_value": row[1],
                    "avg_value": row[2],
                    "count": row[3],
                    "std_dev": row[4],
                    "start_time": start_time.isoformat() if start_time else None,
                    "end_time": end_time.isoformat() if end_time else None
                }
            return {}

        except Exception as e:
            logger.error("Failed to get statistics", device_id=device_id, error=str(e))
            return {}


# Singleton instance getter
_tdengine_client = None

def get_tdengine_client() -> TDengineClient:
    """Get the singleton TDengine client instance."""
    global _tdengine_client
    if _tdengine_client is None:
        _tdengine_client = TDengineClient()
    return _tdengine_client
