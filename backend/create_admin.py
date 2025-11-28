#!/usr/bin/env python3
"""Create admin user via API."""

import requests
import json
import uuid

# Base URL
BASE_URL = "http://localhost:8000/api/v1"

def create_admin():
    """Create admin user via registration API."""

    # First try to create organization ID
    org_id = str(uuid.uuid4())

    # Create admin user
    admin_data = {
        "username": "admin",
        "email": "admin@ecomind.com",
        "password": "admin123",
        "full_name": "系统管理员",
        "role": "admin",
        "org_id": None  # We'll use None for now
    }

    try:
        # Register admin user
        print("Creating admin user...")
        response = requests.post(
            f"{BASE_URL}/auth/register",
            json=admin_data,
            headers={"Content-Type": "application/json"}
        )

        if response.status_code == 201:
            print("✅ Admin user created successfully!")
            print("   Username: admin")
            print("   Password: admin123")
        elif response.status_code == 400:
            error = response.json()
            if "already registered" in error.get("detail", ""):
                print("ℹ️ Admin user already exists")

                # Try to login
                print("\nTrying to login with admin credentials...")
                login_data = "username=admin&password=admin123"
                login_response = requests.post(
                    f"{BASE_URL}/auth/login",
                    data=login_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )

                if login_response.status_code == 200:
                    result = login_response.json()
                    print("✅ Login successful!")
                    print(f"   Token: {result['access_token'][:50]}...")
                else:
                    print(f"❌ Login failed: {login_response.json()}")
            else:
                print(f"❌ Registration failed: {error}")
        else:
            print(f"❌ Failed to create admin user: {response.text}")

    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n确保后端服务正在运行 (http://localhost:8000)")


if __name__ == "__main__":
    create_admin()