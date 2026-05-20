#!/usr/bin/env python3
"""Verify database bootstrap and migration guardrails."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]


def _base_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in list(env):
        upper = key.upper()
        if (
            upper in {"DATABASE_URL", "ENVIRONMENT", "APP_ENV", "JWT_SECRET", "SM4_KEY"}
            or upper.startswith("DEFAULT_")
            or upper.startswith("SUPERADMIN_")
            or upper.startswith("MYSQL_")
            or upper.startswith("POSTGRES_")
        ):
            env.pop(key, None)
    env["PYTHONPATH"] = str(BACKEND)
    return env


def _run_case(name: str, code: str, env: dict[str, str]) -> None:
    print(f"\n== db verification: {name} ==")
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        cwd=BACKEND,
        env=env,
        text=True,
        capture_output=True,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise SystemExit(f"FAILED: db verification '{name}' exited {result.returncode}")
    print("PASS")


def _sqlite_url(path: Path) -> str:
    return "sqlite+aiosqlite:///" + path.as_posix()


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="ecomind-db-verify-") as tmp:
        tmpdir = Path(tmp)

        prod_db = tmpdir / "prod-empty.db"
        env = _base_env()
        env.update(
            {
                "ENVIRONMENT": "production",
                "DATABASE_URL": _sqlite_url(prod_db),
                "JWT_SECRET": "x" * 48,
                "SM4_KEY": "0123456789abcdef0123456789abcdea",
            }
        )
        _run_case(
            "production schema check does not create tables",
            f"""
            import asyncio
            import sqlite3

            import app.models  # noqa: F401
            from app.db.postgres import check_schema, close_db

            async def run():
                try:
                    await check_schema()
                except RuntimeError as exc:
                    assert "Missing tables" in str(exc), str(exc)
                else:
                    raise AssertionError("production schema check passed on an empty database")
                finally:
                    await close_db()

            asyncio.run(run())

            conn = sqlite3.connect(r"{prod_db}")
            tables = {{row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}}
            conn.close()
            assert tables == set(), tables
            """,
            env,
        )

        dev_db = tmpdir / "dev-empty.db"
        env = _base_env()
        env.update(
            {
                "ENVIRONMENT": "development",
                "DATABASE_URL": _sqlite_url(dev_db),
            }
        )
        _run_case(
            "development empty database init is idempotent",
            f"""
            import asyncio
            import sqlite3

            import app.models  # noqa: F401
            from app.db.postgres import init_db, close_db

            async def run():
                await init_db()
                await init_db()
                await close_db()

            asyncio.run(run())

            conn = sqlite3.connect(r"{dev_db}")
            tables = {{row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}}
            default_org_count = conn.execute(
                "SELECT COUNT(*) FROM organizations WHERE code = 'DEFAULT'"
            ).fetchone()[0]
            conn.close()

            assert "users" in tables, tables
            assert "organizations" in tables, tables
            assert default_org_count == 1, default_org_count
            """,
            env,
        )

        env = _base_env()
        env.update(
            {
                "ENVIRONMENT": "production",
                "JWT_SECRET": "x" * 48,
                "SM4_KEY": "0123456789abcdef0123456789abcdea",
            }
        )
        _run_case(
            "production default users require explicit passwords",
            """
            from app.services.default_users import (
                DefaultUserPasswordError,
                get_default_user_specs,
            )

            try:
                get_default_user_specs()
            except DefaultUserPasswordError:
                pass
            else:
                raise AssertionError("default user specs accepted implicit production passwords")
            """,
            env,
        )

        env = _base_env()
        env.update({"ENVIRONMENT": "production"})
        _run_case(
            "init_users production passwords are explicit",
            """
            import sys
            sys.path.insert(0, "scripts")

            from init_users import PasswordConfigurationError, get_user_specs

            try:
                get_user_specs()
            except PasswordConfigurationError:
                pass
            else:
                raise AssertionError("init_users accepted implicit production passwords")
            """,
            env,
        )

        env = _base_env()
        env.update(
            {
                "ENVIRONMENT": "production",
                "DATABASE_URL": _sqlite_url(tmpdir / "superadmin.db"),
                "JWT_SECRET": "x" * 48,
                "SM4_KEY": "0123456789abcdef0123456789abcdea",
            }
        )
        _run_case(
            "init_superadmin production password is explicit",
            """
            import sys
            sys.path.insert(0, "scripts")

            from init_superadmin import PasswordConfigurationError, get_superadmin_password

            try:
                get_superadmin_password()
            except PasswordConfigurationError:
                pass
            else:
                raise AssertionError("init_superadmin accepted an implicit production password")
            """,
            env,
        )


if __name__ == "__main__":
    main()
