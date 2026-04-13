#!/usr/bin/env python3
"""Pick one real mnCode with recent monitoring data for integration testing.

Usage:
  python scripts/pick_test_mn_code.py
  python scripts/pick_test_mn_code.py --days 14 --org-id <org_id>
  python scripts/pick_test_mn_code.py --enterprise-name 某某水务 --json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from urllib.parse import quote_plus

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def _build_db_url_from_env() -> str | None:
    explicit = os.getenv("DATABASE_URL")
    if explicit:
        return explicit

    mysql_password = os.getenv("MYSQL_PASSWORD") or os.getenv("mysql_password")
    if mysql_password:
        mysql_user = (
            os.getenv("MYSQL_USER")
            or os.getenv("MYSQL_USERNAME")
            or os.getenv("mysql_user")
            or os.getenv("mysql_username")
            or "root"
        )
        mysql_host = os.getenv("MYSQL_HOST") or os.getenv("mysql_host") or "localhost"
        mysql_port = os.getenv("MYSQL_PORT") or os.getenv("mysql_port") or "3306"
        mysql_db = (
            os.getenv("MYSQL_DB")
            or os.getenv("MYSQL_DATABASE")
            or os.getenv("mysql_db")
            or "ecomind"
        )
        return "mysql+aiomysql://{}:{}@{}:{}/{}?charset=utf8mb4".format(
            mysql_user,
            quote_plus(mysql_password),
            mysql_host,
            mysql_port,
            mysql_db,
        )

    postgres_password = os.getenv("POSTGRES_PASSWORD") or os.getenv("postgres_password")
    if postgres_password:
        pg_user = os.getenv("POSTGRES_USER") or os.getenv("postgres_user") or "ecomind"
        pg_host = os.getenv("POSTGRES_HOST") or os.getenv("postgres_host") or "localhost"
        pg_port = os.getenv("POSTGRES_PORT") or os.getenv("postgres_port") or "5432"
        pg_db = os.getenv("POSTGRES_DB") or os.getenv("postgres_db") or "ecomind"
        return "postgresql+asyncpg://{}:{}@{}:{}/{}".format(
            pg_user,
            quote_plus(postgres_password),
            pg_host,
            pg_port,
            pg_db,
        )

    return None


def _normalize_async_url(db_url: str) -> str:
    url = db_url.strip()
    if url.startswith("sqlite:///") and "+aiosqlite" not in url:
        return url.replace("sqlite:///", "sqlite+aiosqlite:///")
    if url.startswith("mysql+pymysql://"):
        return url.replace("mysql+pymysql://", "mysql+aiomysql://")
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://")
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
    return url


async def _pick_one(session: AsyncSession, *, days: int, org_id: str | None, enterprise_name: str | None) -> dict | None:
    where_clauses = [
        "d.mn IS NOT NULL",
        "d.mn <> ''",
    ]
    params: dict[str, object] = {
        "window_start": datetime.utcnow() - timedelta(days=days),
    }

    if org_id:
        where_clauses.append("d.org_id = :org_id")
        params["org_id"] = org_id
    if enterprise_name:
        where_clauses.append("o.name LIKE :enterprise_name")
        params["enterprise_name"] = f"%{enterprise_name}%"

    sql = f"""
        SELECT
            d.org_id AS org_id,
            o.name AS enterprise_name,
            d.name AS device_name,
            d.mn AS mn_code,
            d.status AS device_status,
            d.last_heartbeat AS last_heartbeat,
            COUNT(md.id) AS recent_points,
            MAX(md.ts) AS latest_data_time
        FROM devices d
        JOIN organizations o
            ON o.id = d.org_id
        LEFT JOIN monitoring_data md
            ON md.device_id = d.mn
           AND md.org_id = d.org_id
           AND md.ts >= :window_start
        WHERE {" AND ".join(where_clauses)}
        GROUP BY
            d.org_id,
            o.name,
            d.name,
            d.mn,
            d.status,
            d.last_heartbeat
        HAVING COUNT(md.id) > 0
        ORDER BY recent_points DESC, latest_data_time DESC
        LIMIT 1
    """

    result = await session.execute(text(sql), params)
    row = result.mappings().first()
    if row is None:
        return None

    latest_data_time = row["latest_data_time"]
    last_heartbeat = row["last_heartbeat"]

    return {
        "orgId": row["org_id"],
        "enterprise": row["enterprise_name"],
        "deviceName": row["device_name"],
        "mnCode": row["mn_code"],
        "deviceStatus": row["device_status"],
        "recentPoints": int(row["recent_points"] or 0),
        "latestDataTime": latest_data_time.isoformat(sep=" ", timespec="seconds") if latest_data_time else "",
        "lastHeartbeat": last_heartbeat.isoformat(sep=" ", timespec="seconds") if last_heartbeat else "",
        "windowDays": days,
    }


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Pick one real mnCode with recent monitoring data.")
    parser.add_argument("--db-url", help="Optional explicit database URL")
    parser.add_argument("--days", type=int, default=7, help="Look back this many days for monitoring data, default 7")
    parser.add_argument("--org-id", help="Optional org_id filter")
    parser.add_argument("--enterprise-name", help="Optional enterprise name fuzzy filter")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    args = parser.parse_args()

    raw_db_url = args.db_url or _build_db_url_from_env()
    if not raw_db_url:
        print(
            "未检测到数据库配置。请设置 DATABASE_URL 或 MYSQL_PASSWORD/MYSQL_HOST/MYSQL_DATABASE 等环境变量。",
            file=sys.stderr,
        )
        return 2

    db_url = _normalize_async_url(raw_db_url)
    engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_factory() as session:
            result = await _pick_one(
                session,
                days=max(args.days, 1),
                org_id=args.org_id,
                enterprise_name=args.enterprise_name,
            )
    finally:
        await engine.dispose()

    if result is None:
        print(
            "在最近 {} 天内没有找到可用于联调的 mnCode。请放宽 --days 或检查 monitoring_data 是否已有现网数据。".format(
                max(args.days, 1)
            ),
            file=sys.stderr,
        )
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print("联调用 mnCode 已选出：")
    print(f"enterprise: {result['enterprise']}")
    print(f"orgId: {result['orgId']}")
    print(f"deviceName: {result['deviceName']}")
    print(f"mnCode: {result['mnCode']}")
    print(f"deviceStatus: {result['deviceStatus']}")
    print(f"recentPoints({result['windowDays']}d): {result['recentPoints']}")
    print(f"latestDataTime: {result['latestDataTime']}")
    print(f"lastHeartbeat: {result['lastHeartbeat']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
