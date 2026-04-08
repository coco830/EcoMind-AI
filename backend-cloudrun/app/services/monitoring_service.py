"""MySQL-based monitoring data service.

提供监测数据的存储、查询和聚合功能。
替代 TDengine Mock 模式，使用 MySQL 持久化数据。
"""

from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional
import structlog

from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.mysql import insert as mysql_insert

from app.models.monitoring_mysql import (
    MonitoringDataMySQL,
    MonitoringDailyStats,
    MonitoringHourlyStats,
)
from app.core.pollutant_library import (
    get_pollutant_info,
    get_pollutant_code_candidates,
    normalize_pollutant_code,
)

logger = structlog.get_logger()


class MonitoringService:
    """监测数据服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def insert_monitoring_data(
        self,
        device_id: str,
        org_id: str,
        pollutant_code: str,
        ts: datetime,
        value: float,
        flag: str = "N",
        status: int = 0,
        data_type: str = "realtime",
        device_name: Optional[str] = None,
        pollutant_name: Optional[str] = None,
    ) -> bool:
        """插入单条监测数据"""
        try:
            normalized_code = normalize_pollutant_code(pollutant_code)

            # 获取污染物名称
            if not pollutant_name:
                pol_info = get_pollutant_info(normalized_code)
                pollutant_name = pol_info.get("name") if pol_info else None

            data = MonitoringDataMySQL(
                ts=ts,
                device_id=device_id,
                device_name=device_name,
                org_id=org_id,
                pollutant_code=normalized_code,
                pollutant_name=pollutant_name,
                value=value,
                flag=flag,
                status=status,
                data_type=data_type,
            )
            self.db.add(data)
            await self.db.commit()

            logger.debug(
                "Inserted monitoring data",
                device_id=device_id,
                pollutant_code=normalized_code,
                value=value,
            )
            return True

        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to insert monitoring data", error=str(e))
            return False

    async def insert_batch_monitoring_data(
        self,
        data_list: List[Dict[str, Any]]
    ) -> int:
        """批量插入监测数据

        Args:
            data_list: 数据列表，每个元素包含:
                - device_id, org_id, pollutant_code, ts, value
                - 可选: flag, status, data_type, device_name, pollutant_name

        Returns:
            成功插入的记录数
        """
        try:
            records = []
            for item in data_list:
                normalized_code = normalize_pollutant_code(item["pollutant_code"])

                # 获取污染物名称
                pollutant_name = item.get("pollutant_name")
                if not pollutant_name:
                    pol_info = get_pollutant_info(normalized_code)
                    pollutant_name = pol_info.get("name") if pol_info else None

                records.append(MonitoringDataMySQL(
                    ts=item["ts"],
                    device_id=item["device_id"],
                    device_name=item.get("device_name"),
                    org_id=item["org_id"],
                    pollutant_code=normalized_code,
                    pollutant_name=pollutant_name,
                    value=item["value"],
                    flag=item.get("flag", "N"),
                    status=item.get("status", 0),
                    data_type=item.get("data_type", "realtime"),
                ))

            self.db.add_all(records)
            await self.db.commit()

            logger.info("Batch inserted monitoring data", count=len(records))
            return len(records)

        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to batch insert monitoring data", error=str(e))
            return 0

    async def query_monitoring_data(
        self,
        device_id: Optional[str] = None,
        org_id: Optional[str] = None,
        pollutant_code: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        data_type: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """查询监测数据"""
        try:
            query = select(MonitoringDataMySQL)

            # 构建条件
            conditions = []
            if device_id:
                conditions.append(MonitoringDataMySQL.device_id == device_id)
            if org_id:
                conditions.append(MonitoringDataMySQL.org_id == org_id)
            if pollutant_code:
                candidate_codes = get_pollutant_code_candidates(pollutant_code)
                if candidate_codes:
                    conditions.append(MonitoringDataMySQL.pollutant_code.in_(candidate_codes))
            if start_time:
                conditions.append(MonitoringDataMySQL.ts >= start_time)
            if end_time:
                conditions.append(MonitoringDataMySQL.ts <= end_time)
            if data_type:
                conditions.append(MonitoringDataMySQL.data_type == data_type)

            if conditions:
                query = query.where(and_(*conditions))

            query = query.order_by(MonitoringDataMySQL.ts.desc()).limit(limit).offset(offset)

            result = await self.db.execute(query)
            records = result.scalars().all()

            normalized_records: List[Dict[str, Any]] = []
            for record in records:
                normalized_code = normalize_pollutant_code(record.pollutant_code)
                pol_info = get_pollutant_info(normalized_code)
                normalized_records.append(
                    {
                        "id": record.id,
                        "ts": record.ts,
                        "device_id": record.device_id,
                        "device_name": record.device_name,
                        "org_id": record.org_id,
                        "pollutant_code": normalized_code,
                        "pollutant_name": record.pollutant_name or (pol_info.get("name") if pol_info else None),
                        "value": record.value,
                        "flag": record.flag,
                        "status": record.status,
                        "data_type": record.data_type,
                    }
                )

            return normalized_records

        except Exception as e:
            logger.error("Failed to query monitoring data", error=str(e))
            return []

    async def get_latest_values(
        self,
        device_ids: Optional[List[str]] = None,
        org_id: Optional[str] = None,
        pollutant_code: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """获取最新监测值

        返回每个设备每个污染物的最新值
        """
        try:
            # 使用子查询获取每个设备每个污染物的最新时间
            subquery = (
                select(
                    MonitoringDataMySQL.device_id,
                    MonitoringDataMySQL.pollutant_code,
                    func.max(MonitoringDataMySQL.ts).label("max_ts")
                )
                .group_by(
                    MonitoringDataMySQL.device_id,
                    MonitoringDataMySQL.pollutant_code
                )
            )

            conditions = []
            if device_ids:
                conditions.append(MonitoringDataMySQL.device_id.in_(device_ids))
            if org_id:
                conditions.append(MonitoringDataMySQL.org_id == org_id)
            if pollutant_code:
                candidate_codes = get_pollutant_code_candidates(pollutant_code)
                if candidate_codes:
                    conditions.append(MonitoringDataMySQL.pollutant_code.in_(candidate_codes))

            if conditions:
                subquery = subquery.where(and_(*conditions))

            subquery = subquery.subquery()

            # 主查询
            query = (
                select(MonitoringDataMySQL)
                .join(
                    subquery,
                    and_(
                        MonitoringDataMySQL.device_id == subquery.c.device_id,
                        MonitoringDataMySQL.pollutant_code == subquery.c.pollutant_code,
                        MonitoringDataMySQL.ts == subquery.c.max_ts,
                    )
                )
            )

            result = await self.db.execute(query)
            records = result.scalars().all()

            latest_by_device_pollutant: Dict[tuple[str, str], Dict[str, Any]] = {}
            for record in records:
                normalized_code = normalize_pollutant_code(record.pollutant_code)
                key = (record.device_id, normalized_code)
                existing = latest_by_device_pollutant.get(key)

                if existing is not None and existing["ts"] >= record.ts:
                    continue

                pol_info = get_pollutant_info(normalized_code)
                latest_by_device_pollutant[key] = {
                    "ts": record.ts,
                    "device_id": record.device_id,
                    "device_name": record.device_name,
                    "pollutant_code": normalized_code,
                    "pollutant_name": record.pollutant_name or (pol_info.get("name") if pol_info else None),
                    "value": record.value,
                    "flag": record.flag,
                }

            return list(latest_by_device_pollutant.values())

        except Exception as e:
            logger.error("Failed to get latest values", error=str(e))
            return []

    async def get_statistics(
        self,
        device_id: str,
        pollutant_code: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """获取统计数据"""
        try:
            normalized_pollutant_code = normalize_pollutant_code(pollutant_code) if pollutant_code else None

            query = select(
                func.min(MonitoringDataMySQL.value).label("min_value"),
                func.max(MonitoringDataMySQL.value).label("max_value"),
                func.avg(MonitoringDataMySQL.value).label("avg_value"),
                func.count(MonitoringDataMySQL.id).label("count"),
            ).where(MonitoringDataMySQL.device_id == device_id)

            if pollutant_code:
                candidate_codes = get_pollutant_code_candidates(pollutant_code)
                if candidate_codes:
                    query = query.where(MonitoringDataMySQL.pollutant_code.in_(candidate_codes))
            if start_time:
                query = query.where(MonitoringDataMySQL.ts >= start_time)
            if end_time:
                query = query.where(MonitoringDataMySQL.ts <= end_time)

            result = await self.db.execute(query)
            row = result.one_or_none()

            if row:
                return {
                    "device_id": device_id,
                    "pollutant_code": normalized_pollutant_code or "all",
                    "min_value": float(row.min_value) if row.min_value else None,
                    "max_value": float(row.max_value) if row.max_value else None,
                    "avg_value": float(row.avg_value) if row.avg_value else None,
                    "count": row.count,
                    "start_time": start_time.isoformat() if start_time else None,
                    "end_time": end_time.isoformat() if end_time else None,
                }
            return {}

        except Exception as e:
            logger.error("Failed to get statistics", error=str(e))
            return {}

    async def aggregate_daily_stats(
        self,
        target_date: date,
        device_id: Optional[str] = None,
    ) -> int:
        """聚合生成每日统计数据

        将指定日期的原始数据聚合为每日统计记录。

        Args:
            target_date: 目标日期
            device_id: 可选，指定设备ID

        Returns:
            生成的统计记录数
        """
        try:
            start_time = datetime.combine(target_date, datetime.min.time())
            end_time = datetime.combine(target_date, datetime.max.time())

            # 聚合查询
            query = select(
                MonitoringDataMySQL.device_id,
                MonitoringDataMySQL.device_name,
                MonitoringDataMySQL.org_id,
                MonitoringDataMySQL.pollutant_code,
                MonitoringDataMySQL.pollutant_name,
                func.min(MonitoringDataMySQL.value).label("min_value"),
                func.max(MonitoringDataMySQL.value).label("max_value"),
                func.avg(MonitoringDataMySQL.value).label("avg_value"),
                func.sum(MonitoringDataMySQL.value).label("sum_value"),
                func.count(MonitoringDataMySQL.id).label("data_count"),
                func.sum(
                    func.IF(MonitoringDataMySQL.flag == "N", 1, 0)
                ).label("valid_count"),
            ).where(
                and_(
                    MonitoringDataMySQL.ts >= start_time,
                    MonitoringDataMySQL.ts <= end_time,
                )
            ).group_by(
                MonitoringDataMySQL.device_id,
                MonitoringDataMySQL.device_name,
                MonitoringDataMySQL.org_id,
                MonitoringDataMySQL.pollutant_code,
                MonitoringDataMySQL.pollutant_name,
            )

            if device_id:
                query = query.where(MonitoringDataMySQL.device_id == device_id)

            result = await self.db.execute(query)
            rows = result.all()

            count = 0
            for row in rows:
                # 计算超标次数和超标率
                pol_info = get_pollutant_info(row.pollutant_code)
                limit_value = pol_info.get("limit") if pol_info else None
                exceed_count = 0
                exceed_rate = 0.0

                if limit_value and row.data_count > 0:
                    # 需要单独查询超标记录数
                    exceed_query = select(func.count(MonitoringDataMySQL.id)).where(
                        and_(
                            MonitoringDataMySQL.device_id == row.device_id,
                            MonitoringDataMySQL.pollutant_code == row.pollutant_code,
                            MonitoringDataMySQL.ts >= start_time,
                            MonitoringDataMySQL.ts <= end_time,
                            MonitoringDataMySQL.value > limit_value,
                        )
                    )
                    exceed_result = await self.db.execute(exceed_query)
                    exceed_count = exceed_result.scalar() or 0
                    exceed_rate = exceed_count / row.data_count if row.data_count > 0 else 0

                # 使用 INSERT ON DUPLICATE KEY UPDATE
                stmt = mysql_insert(MonitoringDailyStats).values(
                    stat_date=target_date,
                    device_id=row.device_id,
                    device_name=row.device_name,
                    org_id=row.org_id,
                    pollutant_code=row.pollutant_code,
                    pollutant_name=row.pollutant_name,
                    min_value=row.min_value,
                    max_value=row.max_value,
                    avg_value=row.avg_value,
                    sum_value=row.sum_value,
                    data_count=row.data_count,
                    exceed_count=exceed_count,
                    exceed_rate=exceed_rate,
                    valid_count=row.valid_count,
                    invalid_count=row.data_count - row.valid_count,
                ).on_duplicate_key_update(
                    min_value=row.min_value,
                    max_value=row.max_value,
                    avg_value=row.avg_value,
                    sum_value=row.sum_value,
                    data_count=row.data_count,
                    exceed_count=exceed_count,
                    exceed_rate=exceed_rate,
                    valid_count=row.valid_count,
                    invalid_count=row.data_count - row.valid_count,
                )

                await self.db.execute(stmt)
                count += 1

            await self.db.commit()
            logger.info("Aggregated daily stats", date=target_date, count=count)
            return count

        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to aggregate daily stats", error=str(e))
            return 0

    async def get_daily_stats(
        self,
        device_id: Optional[str] = None,
        org_id: Optional[str] = None,
        pollutant_code: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """查询每日统计数据"""
        try:
            query = select(MonitoringDailyStats)

            conditions = []
            if device_id:
                conditions.append(MonitoringDailyStats.device_id == device_id)
            if org_id:
                conditions.append(MonitoringDailyStats.org_id == org_id)
            if pollutant_code:
                conditions.append(MonitoringDailyStats.pollutant_code == pollutant_code)
            if start_date:
                conditions.append(MonitoringDailyStats.stat_date >= start_date)
            if end_date:
                conditions.append(MonitoringDailyStats.stat_date <= end_date)

            if conditions:
                query = query.where(and_(*conditions))

            query = query.order_by(MonitoringDailyStats.stat_date.desc()).limit(limit)

            result = await self.db.execute(query)
            records = result.scalars().all()

            return [
                {
                    "id": r.id,
                    "stat_date": r.stat_date,
                    "device_id": r.device_id,
                    "device_name": r.device_name,
                    "org_id": r.org_id,
                    "pollutant_code": r.pollutant_code,
                    "pollutant_name": r.pollutant_name,
                    "min_value": r.min_value,
                    "max_value": r.max_value,
                    "avg_value": r.avg_value,
                    "data_count": r.data_count,
                    "exceed_count": r.exceed_count,
                    "exceed_rate": r.exceed_rate,
                }
                for r in records
            ]

        except Exception as e:
            logger.error("Failed to get daily stats", error=str(e))
            return []

    async def get_latest_data_date(
        self,
        device_id: str,
        lookback_days: int = 30,
    ) -> Optional[date]:
        """获取设备最近有数据的日期

        当指定日期没有数据时，用于自动查找最近的有效数据日期。

        Args:
            device_id: 设备ID（MN号）
            lookback_days: 向前查找的天数，默认30天

        Returns:
            最近有数据的日期，如果没有数据返回None
        """
        try:
            query = (
                select(func.date(MonitoringDataMySQL.ts).label("data_date"))
                .where(MonitoringDataMySQL.device_id == device_id)
                .group_by(func.date(MonitoringDataMySQL.ts))
                .order_by(func.date(MonitoringDataMySQL.ts).desc())
                .limit(1)
            )

            result = await self.db.execute(query)
            row = result.scalar_one_or_none()

            if row:
                # row 可能是 datetime.date 或字符串，需要处理
                if isinstance(row, date):
                    return row
                elif isinstance(row, str):
                    from datetime import datetime as dt
                    return dt.strptime(row, "%Y-%m-%d").date()

            logger.info("No data found for device", device_id=device_id)
            return None

        except Exception as e:
            logger.error("Failed to get latest data date", device_id=device_id, error=str(e))
            return None

    async def get_heatmap_data(
        self,
        org_id: Optional[str] = None,
        pollutant_code: str = "w01018",
        target_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """获取热力图数据

        返回带有地理位置的监测数据，用于地图热力图展示。

        Args:
            org_id: 组织ID筛选
            pollutant_code: 污染物代码
            target_date: 目标日期，默认今天

        Returns:
            热力图数据点列表
        """
        from app.models.device import Device

        try:
            if not target_date:
                target_date = date.today()

            # 联合查询设备位置和统计数据
            query = (
                select(
                    MonitoringDailyStats,
                    Device.latitude,
                    Device.longitude,
                )
                .join(
                    Device,
                    MonitoringDailyStats.device_id == Device.mn,
                )
                .where(
                    and_(
                        MonitoringDailyStats.stat_date == target_date,
                        MonitoringDailyStats.pollutant_code == pollutant_code,
                        Device.latitude.isnot(None),
                        Device.longitude.isnot(None),
                    )
                )
            )

            if org_id:
                query = query.where(MonitoringDailyStats.org_id == org_id)

            result = await self.db.execute(query)
            rows = result.all()

            return [
                {
                    "lat": float(row.latitude),
                    "lng": float(row.longitude),
                    "value": float(row[0].avg_value) if row[0].avg_value else 0,
                    "device_id": row[0].device_id,
                    "device_name": row[0].device_name,
                    "pollutant_code": row[0].pollutant_code,
                    "pollutant_name": row[0].pollutant_name,
                    "stat_date": row[0].stat_date,
                }
                for row in rows
            ]

        except Exception as e:
            logger.error("Failed to get heatmap data", error=str(e))
            return []
