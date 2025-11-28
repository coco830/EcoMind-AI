#!/usr/bin/env python3
"""Initialize database with test data."""

import asyncio
import sys
from pathlib import Path

# Add backend directory to path
sys.path.append(str(Path(__file__).parent))

from uuid import uuid4
from sqlalchemy import select
from app.db.postgres import init_db, get_db, AsyncSessionLocal
from app.models.organization import Organization
from app.models.user import User
from app.core.security import get_password_hash


async def create_test_data():
    """Create test organization and users."""

    # Initialize database tables
    print("Initializing database...")
    await init_db()

    async with AsyncSessionLocal() as session:
        try:
            # Check if default organization exists
            result = await session.execute(
                select(Organization).where(Organization.name == "EcoMind 演示企业")
            )
            org = result.scalar_one_or_none()

            if not org:
                # Create default organization
                print("Creating default organization...")
                org = Organization(
                    id=uuid4(),
                    name="EcoMind 演示企业",
                    code="DEMO001",
                    contact_name="张经理",
                    contact_phone="13800138000",
                    address="上海市浦东新区环保科技园"
                )
                session.add(org)
                await session.flush()
                print(f"Created organization: {org.name}")
            else:
                print(f"Organization already exists: {org.name}")

            # Check if admin user exists
            result = await session.execute(
                select(User).where(User.username == "admin")
            )
            admin_user = result.scalar_one_or_none()

            if not admin_user:
                # Create admin user
                print("Creating admin user...")
                admin_user = User(
                    id=uuid4(),
                    username="admin",
                    email="admin@ecomind.com",
                    hashed_password=get_password_hash("admin123"),
                    full_name="系统管理员",
                    role="admin",
                    is_active=True,
                    org_id=org.id
                )
                session.add(admin_user)
                print("Created admin user: username=admin, password=admin123")
            else:
                print("Admin user already exists")

            # Check if operator user exists
            result = await session.execute(
                select(User).where(User.username == "operator")
            )
            operator_user = result.scalar_one_or_none()

            if not operator_user:
                # Create operator user
                print("Creating operator user...")
                operator_user = User(
                    id=uuid4(),
                    username="operator",
                    email="operator@ecomind.com",
                    hashed_password=get_password_hash("operator123"),
                    full_name="运维人员",
                    role="operator",
                    is_active=True,
                    org_id=org.id
                )
                session.add(operator_user)
                print("Created operator user: username=operator, password=operator123")
            else:
                print("Operator user already exists")

            # Check if viewer user exists
            result = await session.execute(
                select(User).where(User.username == "viewer")
            )
            viewer_user = result.scalar_one_or_none()

            if not viewer_user:
                # Create viewer user
                print("Creating viewer user...")
                viewer_user = User(
                    id=uuid4(),
                    username="viewer",
                    email="viewer@ecomind.com",
                    hashed_password=get_password_hash("viewer123"),
                    full_name="查看用户",
                    role="viewer",
                    is_active=True,
                    org_id=org.id
                )
                session.add(viewer_user)
                print("Created viewer user: username=viewer, password=viewer123")
            else:
                print("Viewer user already exists")

            # Commit all changes
            await session.commit()
            print("\n✅ Test data initialization completed!")
            print("\n可用的测试账号：")
            print("  管理员: admin / admin123")
            print("  运维员: operator / operator123")
            print("  查看者: viewer / viewer123")

        except Exception as e:
            print(f"❌ Error creating test data: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(create_test_data())