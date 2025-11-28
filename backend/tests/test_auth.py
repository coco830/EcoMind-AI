"""Tests for authentication endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register(client: AsyncClient) -> None:
    """Test user registration."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "password123",
            "full_name": "New User",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "newuser@example.com"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient) -> None:
    """Test registration with duplicate username."""
    # First registration
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "dupuser",
            "email": "dup1@example.com",
            "password": "password123",
        },
    )

    # Second registration with same username
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "dupuser",
            "email": "dup2@example.com",
            "password": "password123",
        },
    )
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login(client: AsyncClient) -> None:
    """Test user login."""
    # First register a user
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "loginuser",
            "email": "login@example.com",
            "password": "password123",
        },
    )

    # Then login
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "loginuser", "password": "password123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient) -> None:
    """Test login with wrong password."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "wrongpass",
            "email": "wrongpass@example.com",
            "password": "password123",
        },
    )

    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "wrongpass", "password": "wrongpassword"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Test getting current user info."""
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"


@pytest.mark.asyncio
async def test_get_current_user_unauthorized(client: AsyncClient) -> None:
    """Test getting current user without auth."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
