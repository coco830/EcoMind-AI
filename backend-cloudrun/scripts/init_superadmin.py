#!/usr/bin/env python3
"""Initialize superadmin account.

This script creates the initial superadmin account for the EcoMind-AI platform.
Run this once after deployment to set up the platform administrator.

Usage:
    python scripts/init_superadmin.py

The superadmin account has fixed credentials:
    Username: huanbao
    Email: yueenhb@163.com
    Password: huanbao@123
"""

import asyncio
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.db.postgres import AsyncSessionLocal, init_db
from app.models.user import User
from app.models.organization import Organization
from app.core.security import get_password_hash


# Fixed superadmin credentials
SUPERADMIN_USERNAME = "huanbao"
SUPERADMIN_EMAIL = "yueenhb@163.com"
SUPERADMIN_PASSWORD = "huanbao@123"


async def create_superadmin():
    """Create superadmin account with fixed credentials."""
    print("\n=== EcoMind-AI 超级管理员初始化 ===\n")

    # Initialize database
    await init_db()

    async with AsyncSessionLocal() as db:
        # Check if superadmin already exists
        result = await db.execute(
            select(User).where(User.username == SUPERADMIN_USERNAME)
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            if existing_user.is_superadmin:
                print(f"超级管理员账号 '{SUPERADMIN_USERNAME}' 已存在")
                # Ensure password is correct
                existing_user.hashed_password = get_password_hash(SUPERADMIN_PASSWORD)
                existing_user.email = SUPERADMIN_EMAIL
                existing_user.is_superadmin = True
                existing_user.is_active = True
                await db.commit()
                print("账户信息已更新")
                print(f"\n✅ 超级管理员账户就绪!")
                print(f"   用户名: {SUPERADMIN_USERNAME}")
                print(f"   邮箱: {SUPERADMIN_EMAIL}")
                print(f"   密码: {SUPERADMIN_PASSWORD}")
                return True
            else:
                # Upgrade existing user to superadmin
                print(f"用户 '{SUPERADMIN_USERNAME}' 已存在，升级为超级管理员...")
                existing_user.hashed_password = get_password_hash(SUPERADMIN_PASSWORD)
                existing_user.email = SUPERADMIN_EMAIL
                existing_user.is_superadmin = True
                existing_user.is_active = True
                existing_user.role = "admin"
                await db.commit()
                print(f"\n✅ 已升级为超级管理员!")
                print(f"   用户名: {SUPERADMIN_USERNAME}")
                print(f"   邮箱: {SUPERADMIN_EMAIL}")
                print(f"   密码: {SUPERADMIN_PASSWORD}")
                return True

        # Check if email exists
        result = await db.execute(
            select(User).where(User.email == SUPERADMIN_EMAIL)
        )
        existing_email_user = result.scalar_one_or_none()
        if existing_email_user:
            # Update existing user with this email to be superadmin
            print(f"邮箱 '{SUPERADMIN_EMAIL}' 已被使用，更新该账户为超级管理员...")
            existing_email_user.username = SUPERADMIN_USERNAME
            existing_email_user.hashed_password = get_password_hash(SUPERADMIN_PASSWORD)
            existing_email_user.is_superadmin = True
            existing_email_user.is_active = True
            existing_email_user.role = "admin"
            await db.commit()
            print(f"\n✅ 已更新为超级管理员!")
            print(f"   用户名: {SUPERADMIN_USERNAME}")
            print(f"   邮箱: {SUPERADMIN_EMAIL}")
            print(f"   密码: {SUPERADMIN_PASSWORD}")
            return True

        # Create platform organization for superadmin
        result = await db.execute(
            select(Organization).where(Organization.code == "PLATFORM_ADMIN")
        )
        platform_org = result.scalar_one_or_none()

        if not platform_org:
            platform_org = Organization(
                name="平台管理",
                code="PLATFORM_ADMIN",
                address="",
                contact_name="Platform Admin",
                contact_phone="",
            )
            db.add(platform_org)
            await db.flush()
            await db.refresh(platform_org)

        # Create superadmin user
        superadmin = User(
            username=SUPERADMIN_USERNAME,
            email=SUPERADMIN_EMAIL,
            hashed_password=get_password_hash(SUPERADMIN_PASSWORD),
            full_name="超级管理员",
            role="admin",
            is_active=True,
            is_superadmin=True,
            org_id=platform_org.id,
        )
        db.add(superadmin)
        await db.commit()

        print(f"\n✅ 超级管理员创建成功!")
        print(f"   用户名: {SUPERADMIN_USERNAME}")
        print(f"   邮箱: {SUPERADMIN_EMAIL}")
        print(f"   密码: {SUPERADMIN_PASSWORD}")
        print(f"\n请使用以上账户信息登录管理平台。")
        return True


if __name__ == "__main__":
    success = asyncio.run(create_superadmin())
    sys.exit(0 if success else 1)
