#!/usr/bin/env python3
"""Initialize default user accounts with RBAC roles.

CloudBase 云托管的「在线终端」里，Python 版本/环境有时与运行容器不一致（例如 3.9）。
本项目代码包含 `X | None`（Python 3.10+）类型注解写法，若直接导入 `app.*` 可能触发
Pydantic 解析注解时报错，从而导致初始化脚本无法运行。

为避免环境差异，本脚本不再依赖 `app.*` 导入路径，改为：
- 从环境变量构造数据库连接（MySQL/SQLite/PostgreSQL）
- 使用 SQLAlchemy 执行少量 SQL（只操作 organizations/users 两张表）
- 使用 passlib(bcrypt) 生成密码 hash

Usage:
  python scripts/init_users.py
  python scripts/init_users.py --db-url "mysql+aiomysql://..."
  python scripts/init_users.py --create-tables

Default accounts:
  1) superadmin: 超级管理员（环保管家）
  2) wenyuan:    文档编辑（技术文案）
  3) huanbao:    只读用户（销售/演示）
"""

import argparse
import asyncio
import os
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import quote_plus
from uuid import uuid4

from passlib.context import CryptContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


USERS = [
    {
        "username": "superadmin",
        "email": "yueenrs@yueentech.cn",
        "password": "yueenhb123..",
        "full_name": "超级管理员",
        "role": "superadmin",
        "is_superadmin": True,
    },
    {
        "username": "wenyuan",
        "email": "yueenxs@yueentech.cn",
        "password": "huanbao-1983",
        "full_name": "技术文员",
        "role": "doc_editor",
        "is_superadmin": False,
    },
    {
        "username": "huanbao",
        "email": "yueenhb@163.com",
        "password": "huanbao@123",
        "full_name": "销售演示",
        "role": "viewer",
        "is_superadmin": False,
    },
]


def _now_utc_naive() -> datetime:
    # 避免 MySQL/SQLite 时区字段差异，直接使用 naive UTC 时间戳
    return datetime.utcnow()


def _build_db_url_from_env() -> Optional[str]:
    """Best-effort database URL detection for CloudBase environments."""
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
        encoded_password = quote_plus(mysql_password)
        return "mysql+aiomysql://{}:{}@{}:{}/{}?charset=utf8mb4".format(
            mysql_user,
            encoded_password,
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
        encoded_password = quote_plus(postgres_password)
        return "postgresql+asyncpg://{}:{}@{}:{}/{}".format(
            pg_user,
            encoded_password,
            pg_host,
            pg_port,
            pg_db,
        )

    return None


def _normalize_async_url(db_url: str) -> str:
    """Convert common sync SQLAlchemy URLs to async equivalents when possible."""
    url = db_url.strip()
    if url.startswith("sqlite:///") and "+aiosqlite" not in url:
        return url.replace("sqlite:///", "sqlite+aiosqlite:///")
    if url.startswith("mysql+pymysql://"):
        return url.replace("mysql+pymysql://", "mysql+aiomysql://")
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://")
    return url


async def _maybe_create_tables(session: AsyncSession, dialect: str) -> None:
    """Optionally create minimal tables required by this script."""
    if dialect == "mysql":
        await session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS organizations (
                    id VARCHAR(36) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    code VARCHAR(64) NOT NULL UNIQUE,
                    address VARCHAR(512) NULL,
                    contact_name VARCHAR(64) NULL,
                    contact_phone VARCHAR(20) NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'active',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )
        )
        await session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id VARCHAR(36) PRIMARY KEY,
                    username VARCHAR(64) NOT NULL UNIQUE,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    hashed_password VARCHAR(255) NOT NULL,
                    full_name VARCHAR(128) NULL,
                    role VARCHAR(32) DEFAULT 'viewer',
                    is_active TINYINT(1) NOT NULL DEFAULT 1,
                    is_superadmin TINYINT(1) NOT NULL DEFAULT 0,
                    org_id VARCHAR(36) NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_users_org_id (org_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )
        )
        return

    if dialect == "sqlite":
        await session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS organizations (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    code TEXT NOT NULL UNIQUE,
                    address TEXT NULL,
                    contact_name TEXT NULL,
                    contact_phone TEXT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
        )
        await session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL UNIQUE,
                    hashed_password TEXT NOT NULL,
                    full_name TEXT NULL,
                    role TEXT DEFAULT 'viewer',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    is_superadmin INTEGER NOT NULL DEFAULT 0,
                    org_id TEXT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
        )


async def _get_or_create_platform_org(session: AsyncSession) -> str:
    result = await session.execute(
        text("SELECT id FROM organizations WHERE code = :code LIMIT 1"),
        {"code": "PLATFORM_ADMIN"},
    )
    row = result.mappings().first()
    if row and row.get("id"):
        return str(row["id"])

    org_id = str(uuid4())
    now = _now_utc_naive()
    await session.execute(
        text(
            """
            INSERT INTO organizations (id, name, code, address, contact_name, contact_phone, status, created_at, updated_at)
            VALUES (:id, :name, :code, :address, :contact_name, :contact_phone, :status, :created_at, :updated_at)
            """
        ),
        {
            "id": org_id,
            "name": "平台管理",
            "code": "PLATFORM_ADMIN",
            "address": "",
            "contact_name": "Platform Admin",
            "contact_phone": "",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    return org_id


async def _migrate_old_accounts(session: AsyncSession) -> None:
    now = _now_utc_naive()
    await session.execute(
        text(
            """
            UPDATE users
            SET is_superadmin = 0, role = 'viewer', updated_at = :now
            WHERE username IN ('huanbao') AND is_superadmin = 1
            """
        ),
        {"now": now},
    )


def _hash_password(password: str) -> str:
    return PWD_CONTEXT.hash(password)


async def _upsert_user(
    session: AsyncSession, user: Dict[str, Any], platform_org_id: str
) -> None:
    username = str(user["username"])
    email = str(user["email"])
    now = _now_utc_naive()

    # 1) match by username
    result = await session.execute(
        text("SELECT id FROM users WHERE username = :username LIMIT 1"),
        {"username": username},
    )
    row = result.mappings().first()
    if row and row.get("id"):
        await session.execute(
            text(
                """
                UPDATE users
                SET email = :email,
                    hashed_password = :hashed_password,
                    full_name = :full_name,
                    role = :role,
                    is_superadmin = :is_superadmin,
                    is_active = 1,
                    org_id = COALESCE(org_id, :org_id),
                    updated_at = :updated_at
                WHERE username = :username
                """
            ),
            {
                "username": username,
                "email": email,
                "hashed_password": _hash_password(str(user["password"])),
                "full_name": str(user.get("full_name") or ""),
                "role": str(user["role"]),
                "is_superadmin": 1 if user.get("is_superadmin") else 0,
                "org_id": platform_org_id,
                "updated_at": now,
            },
        )
        print("  更新用户 '{}'...".format(username))
        return

    # 2) match by email
    result = await session.execute(
        text("SELECT id FROM users WHERE email = :email LIMIT 1"),
        {"email": email},
    )
    row = result.mappings().first()
    if row and row.get("id"):
        await session.execute(
            text(
                """
                UPDATE users
                SET username = :username,
                    hashed_password = :hashed_password,
                    full_name = :full_name,
                    role = :role,
                    is_superadmin = :is_superadmin,
                    is_active = 1,
                    org_id = COALESCE(org_id, :org_id),
                    updated_at = :updated_at
                WHERE email = :email
                """
            ),
            {
                "email": email,
                "username": username,
                "hashed_password": _hash_password(str(user["password"])),
                "full_name": str(user.get("full_name") or ""),
                "role": str(user["role"]),
                "is_superadmin": 1 if user.get("is_superadmin") else 0,
                "org_id": platform_org_id,
                "updated_at": now,
            },
        )
        print("  更新邮箱为 '{}' 的用户...".format(email))
        return

    # 3) create
    user_id = str(uuid4())
    await session.execute(
        text(
            """
            INSERT INTO users (id, username, email, hashed_password, full_name, role, is_active, is_superadmin, org_id, created_at, updated_at)
            VALUES (:id, :username, :email, :hashed_password, :full_name, :role, :is_active, :is_superadmin, :org_id, :created_at, :updated_at)
            """
        ),
        {
            "id": user_id,
            "username": username,
            "email": email,
            "hashed_password": _hash_password(str(user["password"])),
            "full_name": str(user.get("full_name") or ""),
            "role": str(user["role"]),
            "is_active": 1,
            "is_superadmin": 1 if user.get("is_superadmin") else 0,
            "org_id": platform_org_id,
            "created_at": now,
            "updated_at": now,
        },
    )
    print("  创建用户 '{}'...".format(username))


async def _run(db_url: str, create_tables: bool) -> None:
    engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    try:
        async with session_factory() as session:
            dialect = session.bind.dialect.name  # type: ignore[attr-defined]

            if create_tables:
                print("检查并创建必要表（organizations/users）...")
                await _maybe_create_tables(session, dialect)
                await session.commit()

            print("\n=== EcoMind-AI 用户账号初始化 ===\n")

            platform_org_id = await _get_or_create_platform_org(session)

            print("迁移旧账号...")
            await _migrate_old_accounts(session)

            print("\n创建/更新用户账号...")
            for u in USERS:
                await _upsert_user(session, u, platform_org_id)

            await session.commit()

        print("\n" + "=" * 50)
        print("用户账号初始化完成！")
        print("=" * 50)
        print("\n账号列表：\n")
        role_desc = {
            "superadmin": "超级管理员 (全部权限)",
            "doc_editor": "文档编辑 (文档读写 + 其他只读)",
            "viewer": "只读用户 (所有只读，用于演示)",
        }
        for u in USERS:
            print(
                "  - {} ({})".format(u["full_name"], role_desc.get(u["role"], u["role"]))
            )
            print("    用户名: {}".format(u["username"]))
            print("    邮  箱: {}".format(u["email"]))
            print("    密  码: {}".format(u["password"]))

    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize default EcoMind-AI users")
    parser.add_argument(
        "--db-url",
        dest="db_url",
        default=None,
        help="Override database URL (e.g. mysql+aiomysql://...)",
    )
    parser.add_argument(
        "--create-tables",
        action="store_true",
        help="Create minimal required tables if missing (organizations/users)",
    )
    args = parser.parse_args()

    db_url = args.db_url or _build_db_url_from_env()
    if not db_url:
        raise SystemExit(
            "未检测到数据库配置。请设置 DATABASE_URL 或 MYSQL_PASSWORD/MYSQL_HOST/MYSQL_DB 等环境变量。"
        )

    asyncio.run(
        _run(_normalize_async_url(db_url), create_tables=bool(args.create_tables))
    )


if __name__ == "__main__":
    main()
