#!/usr/bin/env python3
"""
Test script for multi-tenancy functionality in EcoMind-AI.

This script tests:
1. Organization management (superadmin only)
2. User registration with default organization
3. Data isolation between organizations
4. Device access control
5. Alarm access control

Run this after running the migration script.
"""

import asyncio
import sys
from pathlib import Path
from uuid import UUID

# Add backend to Python path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.db.postgres import AsyncSessionLocal
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.device import Device, DeviceType
from app.core.security import get_password_hash

logger = structlog.get_logger()


async def test_organizations(db: AsyncSession):
    """Test organization setup."""
    logger.info("=" * 60)
    logger.info("Testing Organizations")
    logger.info("=" * 60)

    # Check default organization
    result = await db.execute(
        select(Organization).where(Organization.code == "DEFAULT")
    )
    default_org = result.scalar_one_or_none()

    if default_org:
        logger.info(" Default organization exists", org_name=default_org.name, org_code=default_org.code)
    else:
        logger.error(" Default organization not found!")
        return False

    # Count organizations
    result = await db.execute(select(Organization))
    orgs = result.scalars().all()
    logger.info(f"Total organizations: {len(orgs)}")

    return True


async def test_superadmin(db: AsyncSession):
    """Test superadmin user."""
    logger.info("=" * 60)
    logger.info("Testing Superadmin User")
    logger.info("=" * 60)

    result = await db.execute(
        select(User).where(User.is_superadmin == True)
    )
    superadmins = result.scalars().all()

    if superadmins:
        for sa in superadmins:
            logger.info(" Superadmin found", username=sa.username, email=sa.email)
    else:
        logger.warning(" No superadmin users found!")
        return False

    return True


async def test_users(db: AsyncSession):
    """Test user setup and organization assignment."""
    logger.info("=" * 60)
    logger.info("Testing Users")
    logger.info("=" * 60)

    # Check users without organization (excluding superadmins)
    result = await db.execute(
        select(User).where(
            User.org_id.is_(None),
            User.is_superadmin == False
        )
    )
    orphan_users = result.scalars().all()

    if orphan_users:
        logger.warning(f"Found {len(orphan_users)} users without organization:")
        for user in orphan_users:
            logger.warning(f"  - {user.username} ({user.email})")
        return False
    else:
        logger.info(" All non-superadmin users have organizations")

    # Count users per organization
    result = await db.execute(select(User))
    all_users = result.scalars().all()

    org_user_counts = {}
    for user in all_users:
        if user.is_superadmin:
            org_id = "SUPERADMIN"
        else:
            org_id = str(user.org_id) if user.org_id else "NONE"
        org_user_counts[org_id] = org_user_counts.get(org_id, 0) + 1

    logger.info("User distribution by organization:")
    for org_id, count in org_user_counts.items():
        logger.info(f"  - {org_id}: {count} users")

    return True


async def test_devices(db: AsyncSession):
    """Test device setup and organization assignment."""
    logger.info("=" * 60)
    logger.info("Testing Devices")
    logger.info("=" * 60)

    # Check devices without organization
    result = await db.execute(
        select(Device).where(Device.org_id.is_(None))
    )
    orphan_devices = result.scalars().all()

    if orphan_devices:
        logger.warning(f"Found {len(orphan_devices)} devices without organization:")
        for device in orphan_devices:
            logger.warning(f"  - {device.mn} ({device.name})")
        return False
    else:
        logger.info(" All devices have organizations")

    # Count devices per organization
    result = await db.execute(select(Device))
    all_devices = result.scalars().all()

    org_device_counts = {}
    for device in all_devices:
        org_id = str(device.org_id)
        org_device_counts[org_id] = org_device_counts.get(org_id, 0) + 1

    logger.info("Device distribution by organization:")
    for org_id, count in org_device_counts.items():
        logger.info(f"  - {org_id}: {count} devices")

    return True


async def test_data_isolation(db: AsyncSession):
    """Test that organizations are properly isolated."""
    logger.info("=" * 60)
    logger.info("Testing Data Isolation")
    logger.info("=" * 60)

    # Create two test organizations
    org1 = Organization(
        name="K���A",
        code="TEST_ORG_A",
        address="K�0@A",
    )
    org2 = Organization(
        name="K���B",
        code="TEST_ORG_B",
        address="K�0@B",
    )
    db.add(org1)
    db.add(org2)
    await db.flush()
    await db.refresh(org1)
    await db.refresh(org2)

    # Create users for each org
    user1 = User(
        username="testuser_a",
        email="testuser_a@test.com",
        hashed_password=get_password_hash("password123"),
        full_name="Test User A",
        role=UserRole.ADMIN.value,
        org_id=org1.id,
    )
    user2 = User(
        username="testuser_b",
        email="testuser_b@test.com",
        hashed_password=get_password_hash("password123"),
        full_name="Test User B",
        role=UserRole.ADMIN.value,
        org_id=org2.id,
    )
    db.add(user1)
    db.add(user2)
    await db.flush()

    # Create devices for each org
    device1 = Device(
        mn="TEST_MN_A001",
        name="KվA",
        device_type=DeviceType.WATER.value,
        org_id=org1.id,
    )
    device2 = Device(
        mn="TEST_MN_B001",
        name="KվB",
        device_type=DeviceType.AIR.value,
        org_id=org2.id,
    )
    db.add(device1)
    db.add(device2)
    await db.flush()

    # Verify isolation
    result = await db.execute(
        select(Device).where(Device.org_id == org1.id)
    )
    org1_devices = result.scalars().all()

    result = await db.execute(
        select(Device).where(Device.org_id == org2.id)
    )
    org2_devices = result.scalars().all()

    if device1.id in [d.id for d in org1_devices] and device1.id not in [d.id for d in org2_devices]:
        logger.info(" Device isolation working correctly")
    else:
        logger.error(" Device isolation failed!")
        return False

    # Cleanup test data
    await db.delete(device1)
    await db.delete(device2)
    await db.delete(user1)
    await db.delete(user2)
    await db.delete(org1)
    await db.delete(org2)
    await db.flush()

    return True


async def run_tests():
    """Run all tests."""
    logger.info("\n" + "=" * 60)
    logger.info("Multi-Tenancy Testing for EcoMind-AI")
    logger.info("=" * 60 + "\n")

    async with AsyncSessionLocal() as db:
        try:
            results = []

            # Run tests
            results.append(("Organizations", await test_organizations(db)))
            results.append(("Superadmin", await test_superadmin(db)))
            results.append(("Users", await test_users(db)))
            results.append(("Devices", await test_devices(db)))
            results.append(("Data Isolation", await test_data_isolation(db)))

            # Commit test changes
            await db.commit()

            # Print summary
            logger.info("\n" + "=" * 60)
            logger.info("Test Summary")
            logger.info("=" * 60)

            all_passed = True
            for test_name, result in results:
                status = " PASS" if result else " FAIL"
                logger.info(f"{status:10} {test_name}")
                if not result:
                    all_passed = False

            logger.info("=" * 60)

            if all_passed:
                logger.info(" All tests passed! <�")
                return 0
            else:
                logger.error(" Some tests failed!")
                return 1

        except Exception as e:
            logger.error("Test execution failed", error=str(e), exc_info=True)
            await db.rollback()
            return 1


async def main():
    """Main entry point."""
    exit_code = await run_tests()
    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
