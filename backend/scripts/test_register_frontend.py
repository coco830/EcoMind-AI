#!/usr/bin/env python3
"""测试前端注册功能"""

import requests
import time

BASE_URL = "http://localhost:8000"

print("=" * 60)
print("测试用户注册功能（自动分配到默认组织）")
print("=" * 60)
print()

# 测试注册
timestamp = int(time.time())
register_data = {
    "username": f"frontend_test_{timestamp}",
    "email": f"frontend{timestamp}@example.com",
    "password": "password123",
    "full_name": "前端测试用户"
}

print(f"正在注册用户: {register_data['username']}")
print()

try:
    response = requests.post(f"{BASE_URL}/api/v1/auth/register", json=register_data)

    if response.status_code == 201:
        user = response.json()
        print("✓ 注册成功！")
        print(f"  用户名: {user['username']}")
        print(f"  邮箱: {user['email']}")
        print(f"  姓名: {user['full_name']}")
        print(f"  角色: {user['role']}")
        print(f"  组织ID: {user['org_id']}")
        print()

        # 测试登录
        print("测试登录新注册的用户...")
        login_response = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            data={"username": register_data["username"], "password": register_data["password"]}
        )

        if login_response.status_code == 200:
            print("✓ 登录成功！")
            token = login_response.json()["access_token"]
            print(f"  Token: {token[:30]}...")

            # 验证用户信息
            me_response = requests.get(
                f"{BASE_URL}/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )

            if me_response.status_code == 200:
                me = me_response.json()
                print("✓ 用户信息验证成功！")
                print(f"  用户: {me['username']} ({me['email']})")
                print(f"  角色: {me['role']}")
                print(f"  组织: {me['org_id']}")
        else:
            print(f"✗ 登录失败: {login_response.text}")
    else:
        print(f"✗ 注册失败: {response.text}")

except Exception as e:
    print(f"✗ 测试失败: {e}")

print()
print("=" * 60)
print("前端可以访问以下页面进行注册:")
print("  登录页面: http://localhost:3000/login")
print("  注册页面: http://localhost:3000/register")
print("=" * 60)
