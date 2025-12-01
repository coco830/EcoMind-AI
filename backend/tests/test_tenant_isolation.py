"""Tests for multi-tenant isolation.

SECURITY: These tests verify that users from one organization cannot access
resources belonging to another organization.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from app.core.security import get_password_hash, create_access_token
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.models.device import Device, DeviceStatus, DeviceType


@pytest.fixture
async def org_a(test_db: AsyncSession) -> Organization:
    """Create Organization A for testing."""
    org = Organization(
        name="Organization A",
        code="ORG_A",
        address="123 Test Street",
    )
    test_db.add(org)
    await test_db.commit()
    await test_db.refresh(org)
    return org


@pytest.fixture
async def org_b(test_db: AsyncSession) -> Organization:
    """Create Organization B for testing."""
    org = Organization(
        name="Organization B",
        code="ORG_B",
        address="456 Test Avenue",
    )
    test_db.add(org)
    await test_db.commit()
    await test_db.refresh(org)
    return org


@pytest.fixture
async def user_a(test_db: AsyncSession, org_a: Organization) -> User:
    """Create a user in Organization A."""
    user = User(
        username="user_a",
        email="user_a@example.com",
        hashed_password=get_password_hash("password123"),
        full_name="User A",
        role=UserRole.ADMIN.value,
        is_active=True,
        org_id=org_a.id,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest.fixture
async def user_b(test_db: AsyncSession, org_b: Organization) -> User:
    """Create a user in Organization B."""
    user = User(
        username="user_b",
        email="user_b@example.com",
        hashed_password=get_password_hash("password123"),
        full_name="User B",
        role=UserRole.ADMIN.value,
        is_active=True,
        org_id=org_b.id,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest.fixture
async def superadmin(test_db: AsyncSession) -> User:
    """Create a superadmin user (no org_id)."""
    user = User(
        username="superadmin",
        email="superadmin@example.com",
        hashed_password=get_password_hash("password123"),
        full_name="Super Admin",
        role=UserRole.ADMIN.value,
        is_active=True,
        is_superadmin=True,
        org_id=None,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest.fixture
async def device_a(test_db: AsyncSession, org_a: Organization) -> Device:
    """Create a device in Organization A."""
    device = Device(
        mn="DEVICE_A_001",
        name="Device A",
        device_type=DeviceType.WATER.value,
        status=DeviceStatus.ONLINE.value,
        org_id=org_a.id,
    )
    test_db.add(device)
    await test_db.commit()
    await test_db.refresh(device)
    return device


@pytest.fixture
async def device_b(test_db: AsyncSession, org_b: Organization) -> Device:
    """Create a device in Organization B."""
    device = Device(
        mn="DEVICE_B_001",
        name="Device B",
        device_type=DeviceType.WATER.value,
        status=DeviceStatus.ONLINE.value,
        org_id=org_b.id,
    )
    test_db.add(device)
    await test_db.commit()
    await test_db.refresh(device)
    return device


def get_auth_headers(user: User) -> dict[str, str]:
    """Generate authentication headers for a user."""
    token = create_access_token(data={"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# Device Tenant Isolation Tests
# =============================================================================

@pytest.mark.asyncio
async def test_user_can_list_own_org_devices(
    client: AsyncClient,
    user_a: User,
    device_a: Device,
    device_b: Device,
) -> None:
    """Test that users can only list devices in their own organization."""
    headers = get_auth_headers(user_a)
    response = await client.get("/api/v1/devices", headers=headers)

    assert response.status_code == 200
    devices = response.json()

    # User A should only see Device A
    device_ids = [d["id"] for d in devices]
    assert str(device_a.id) in device_ids
    assert str(device_b.id) not in device_ids


@pytest.mark.asyncio
async def test_user_cannot_access_other_org_device_by_id(
    client: AsyncClient,
    user_a: User,
    device_b: Device,
) -> None:
    """Test that User A cannot access Device B (belonging to Org B) by ID.

    SECURITY: This test verifies tenant isolation is enforced.
    Acceptable: 403 Forbidden (access denied) or 404 Not Found (hides existence)
    """
    headers = get_auth_headers(user_a)
    response = await client.get(f"/api/v1/devices/{device_b.id}", headers=headers)

    # Either 403 (access denied) or 404 (not found) is acceptable
    # 403 = isolation works, 404 = isolation works + hides device existence
    assert response.status_code in (403, 404), f"Expected 403 or 404, got {response.status_code}"


@pytest.mark.asyncio
async def test_user_cannot_use_org_id_param_to_bypass_isolation(
    client: AsyncClient,
    user_a: User,
    org_b: Organization,
    device_b: Device,
) -> None:
    """Test that passing org_id parameter does NOT allow cross-tenant access.

    SECURITY: This test verifies that the org_id parameter is ignored for
    non-superadmin users.
    """
    headers = get_auth_headers(user_a)
    # Try to use org_id parameter to access Org B's devices
    response = await client.get(
        f"/api/v1/devices?org_id={org_b.id}",
        headers=headers,
    )

    assert response.status_code == 200
    devices = response.json()

    # Should NOT see Device B even when passing org_id parameter
    device_ids = [d["id"] for d in devices]
    assert str(device_b.id) not in device_ids


@pytest.mark.asyncio
async def test_superadmin_can_access_all_devices(
    client: AsyncClient,
    superadmin: User,
    device_a: Device,
    device_b: Device,
) -> None:
    """Test that superadmin can access devices from all organizations."""
    headers = get_auth_headers(superadmin)
    response = await client.get("/api/v1/devices", headers=headers)

    assert response.status_code == 200
    devices = response.json()

    # Superadmin should see all devices
    device_ids = [d["id"] for d in devices]
    assert str(device_a.id) in device_ids
    assert str(device_b.id) in device_ids


@pytest.mark.asyncio
async def test_superadmin_can_filter_by_org_id(
    client: AsyncClient,
    superadmin: User,
    org_a: Organization,
    device_a: Device,
    device_b: Device,
) -> None:
    """Test that superadmin can filter devices by org_id."""
    headers = get_auth_headers(superadmin)
    response = await client.get(
        f"/api/v1/devices?org_id={org_a.id}",
        headers=headers,
    )

    assert response.status_code == 200
    devices = response.json()

    # Superadmin should see only Org A's devices when filtered
    device_ids = [d["id"] for d in devices]
    assert str(device_a.id) in device_ids
    assert str(device_b.id) not in device_ids


@pytest.mark.asyncio
async def test_user_cannot_create_device_for_other_org(
    client: AsyncClient,
    user_a: User,
    org_b: Organization,
) -> None:
    """Test that users cannot create devices for other organizations.

    SECURITY: Verifies tenant isolation in device creation.
    """
    headers = get_auth_headers(user_a)
    response = await client.post(
        "/api/v1/devices",
        headers=headers,
        json={
            "mn": "HACKED_DEVICE",
            "name": "Hacked Device",
            "device_type": "water",
            "org_id": str(org_b.id),  # Try to create in Org B
        },
    )

    # Should be forbidden
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_user_cannot_update_other_org_device(
    client: AsyncClient,
    user_a: User,
    org_a: Organization,
    device_b: Device,
) -> None:
    """Test that users cannot update devices from other organizations.

    SECURITY: Verifies tenant isolation in device updates.
    """
    headers = get_auth_headers(user_a)
    response = await client.put(
        f"/api/v1/devices/{device_b.id}",
        headers=headers,
        json={
            "mn": "HACKED_MN",
            "name": "Hacked Name",
            "device_type": "water",
            "org_id": str(org_a.id),  # Try to move to own org
        },
    )

    # Either 403 (access denied) or 404 (not found) is acceptable
    assert response.status_code in (403, 404), f"Expected 403 or 404, got {response.status_code}"


@pytest.mark.asyncio
async def test_user_cannot_delete_other_org_device(
    client: AsyncClient,
    user_a: User,
    device_b: Device,
) -> None:
    """Test that users cannot delete devices from other organizations.

    SECURITY: Verifies tenant isolation in device deletion.
    """
    headers = get_auth_headers(user_a)
    response = await client.delete(
        f"/api/v1/devices/{device_b.id}",
        headers=headers,
    )

    # Either 403 (access denied) or 404 (not found) is acceptable
    assert response.status_code in (403, 404), f"Expected 403 or 404, got {response.status_code}"


# =============================================================================
# Device Stats Tenant Isolation Tests
# =============================================================================

@pytest.mark.asyncio
async def test_user_sees_only_own_org_device_stats(
    client: AsyncClient,
    user_a: User,
    device_a: Device,
    device_b: Device,
) -> None:
    """Test that device stats only include user's organization devices."""
    headers = get_auth_headers(user_a)
    response = await client.get("/api/v1/devices/stats/summary", headers=headers)

    assert response.status_code == 200
    stats = response.json()

    # Should only count Device A (1 device)
    assert stats["total"] == 1
