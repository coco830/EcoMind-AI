#!/usr/bin/env python3
"""
Migration script for multi-tenancy support.

This script uses SQLAlchemy ORM to ensure compatibility with both SQLite and PostgreSQL.

This script:
1. Creates tables using ORM (if not exists)
2. Creates a default organization
3. Migrates existing users and devices to the default organization
4. Sets the first admin user as superadmin

Run this script from the backend directory:
    .venv/bin/python scripts/migrate_to_multitenancy.py
"""

import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
import structlog

from app.db.postgres import AsyncSessionLocal, engine, Base
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.device import Device

logger = structlog.get_logger()


async def run_migration():
    """Run the multi-tenancy migration."""
    logger.info("=" * 60)
    logger.info("Starting Multi-Tenancy Migration (ORM-based)")
    logger.info("=" * 60)

    # Create all tables (if not exists)
    logger.info("\n[Step 1] Creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Tables created/verified.")

    async with AsyncSessionLocal() as session:
        try:
            # Step 2: Create default organization if it doesn't exist
            logger.info("\n[Step 2] Creating default organization...")
            result = await session.execute(
                select(Organization).where(Organization.code == "DEFAULT")
            )
            default_org = result.scalar_one_or_none()

            if default_org is None:
                default_org = Organization(
                    name="默认组织",
                    code="DEFAULT",
                    address="EcoMind-AI 默认组织",
                    contact_name="系统管理员",
                    contact_phone="000-0000-0000",
                )
                session.add(default_org)
                await session.flush()
                await session.refresh(default_org)
                logger.info(f"Default organization created with ID: {default_org.id}")
            else:
                logger.info(f"Default organization already exists with ID: {default_org.id}")

            # Step 3: Migrate users without org_id to default organization (except superadmins)
            logger.info("\n[Step 3] Migrating users to default organization...")
            result = await session.execute(
                select(User).where(User.org_id.is_(None))
            )
            users_to_migrate = result.scalars().all()

            users_migrated = 0
            for user in users_to_migrate:
                if not user.is_superadmin:  # Don't assign org to existing superadmins
                    user.org_id = default_org.id
                    users_migrated += 1
                    logger.info(f"  - Migrated user: {user.username}")

            logger.info(f"Migrated {users_migrated} users to default organization.")

            # Step 4: Migrate devices without org_id to default organization
            logger.info("\n[Step 4] Migrating devices to default organization...")
            result = await session.execute(
                select(Device).where(Device.org_id.is_(None))
            )
            devices_to_migrate = result.scalars().all()

            for device in devices_to_migrate:
                device.org_id = default_org.id
                logger.info(f"  - Migrated device: {device.mn} ({device.name})")

            logger.info(f"Migrated {len(devices_to_migrate)} devices to default organization.")

            # Step 5: Set first admin user as superadmin (if no superadmin exists)
            logger.info("\n[Step 5] Setting superadmin user...")
            result = await session.execute(
                select(User).where(User.is_superadmin == True)
            )
            existing_superadmin = result.scalar_one_or_none()

            if existing_superadmin:
                logger.info(f"Superadmin already exists: {existing_superadmin.username}")
            else:
                # Find first admin user
                result = await session.execute(
                    select(User).where(User.role == UserRole.ADMIN.value).order_by(User.created_at)
                )
                admin_user = result.scalars().first()

                if admin_user:
                    admin_user.is_superadmin = True
                    logger.info(f"Set user '{admin_user.username}' as superadmin.")
                else:
                    logger.warning("No admin user found to set as superadmin.")

            # Commit all changes
            await session.commit()

            logger.info("\n" + "=" * 60)
            logger.info("Migration completed successfully!")
            logger.info("=" * 60)

            # Summary
            logger.info("\nSummary:")
            logger.info(f"  - Default organization: {default_org.name} (ID: {default_org.id})")
            logger.info(f"  - Users migrated: {users_migrated}")
            logger.info(f"  - Devices migrated: {len(devices_to_migrate)}")
            if existing_superadmin:
                logger.info(f"  - Existing superadmin: {existing_superadmin.username}")
            elif admin_user:
                logger.info(f"  - New superadmin: {admin_user.username}")
            logger.info("=" * 60)

        except Exception as e:
            await session.rollback()
            logger.error(f"\n[ERROR] Migration failed: {e}", exc_info=True)
            raise


if __name__ == "__main__":
    asyncio.run(run_migration())
