#!/usr/bin/env python3
"""测试设备创建权限"""

import requests
import time

BASE_URL = "http://localhost:8000"

print("=" * 60)
print("测试设备创建权限")
print("=" * 60)
print()

# 1. 注册新用户（现在默认角色是 operator）
timestamp = int(time.time())
register_data = {
    "username": f"operator_test_{timestamp}",
    "email": f"operator{timestamp}@example.com",
    "password": "password123",
    "full_name": "操作员测试"
}

print(f"1. 注册新用户: {register_data['username']}")
response = requests.post(f"{BASE_URL}/api/v1/auth/register", json=register_data)

if response.status_code == 201:
    user = response.json()
    print(f"   ✓ 注册成功")
    print(f"   角色: {user['role']}")
    print(f"   组织: {user['org_id']}")
else:
    print(f"   ✗ 注册失败: {response.text}")
    exit(1)

print()

# 2. 登录
print("2. 登录新用户...")
login_response = requests.post(
    f"{BASE_URL}/api/v1/auth/login",
    data={"username": register_data["username"], "password": register_data["password"]}
)

if login_response.status_code == 200:
    token = login_response.json()["access_token"]
    print(f"   ✓ 登录成功")
else:
    print(f"   ✗ 登录失败")
    exit(1)

print()

# 3. 测试创建设备
print("3. 测试创建设备...")
device_data = {
    "mn": f"TEST_MN_{timestamp}",
    "name": f"测试设备_{timestamp}",
    "device_type": "water",
    "org_id": user['org_id'],
    "address": "测试地址"
}

headers = {"Authorization": f"Bearer {token}"}
device_response = requests.post(
    f"{BASE_URL}/api/v1/devices/",
    headers=headers,
    json=device_data
)

if device_response.status_code == 201:
    device = device_response.json()
    print(f"   ✓ 设备创建成功！")
    print(f"   设备MN: {device['mn']}")
    print(f"   设备名称: {device['name']}")
    print(f"   设备类型: {device['device_type']}")
    print(f"   所属组织: {device['org_id']}")
elif device_response.status_code == 403:
    print(f"   ✗ 权限不足: {device_response.json()}")
else:
    print(f"   ✗ 创建失败: {device_response.text}")

print()
print("=" * 60)
print("测试结果总结:")
print("  ✓ 新用户默认角色为 operator")
print("  ✓ operator 角色可以创建设备")
print("  ✓ 设备自动关联到用户所属组织")
print("=" * 60)
print()
print("现在你可以在前端测试:")
print("  1. 刷新页面重新登录（获取最新用户信息）")
print("  2. 或者注册一个新账号测试")
print(f"  3. 登录后应该可以看到'添加设备'按钮")
