#!/usr/bin/env python3
"""验证多租户修复后的功能"""

import requests
import time

BASE_URL = "http://localhost:8000"

print("=" * 70)
print("多租户数据隔离验证测试")
print("=" * 70)
print()

# 测试账号
test_users = [
    {"username": "userA", "password": "123456"},  # 假设密码
    {"username": "yangkaidi", "password": "123456"},  # 假设密码
]

# 尝试登录两个用户并检查他们的设备列表
for user_info in test_users:
    print(f"\n{'=' * 70}")
    print(f"测试用户: {user_info['username']}")
    print('=' * 70)

    # 1. 登录
    print(f"1. 登录用户 {user_info['username']}...")
    login_response = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        data={
            "username": user_info['username'],
            "password": user_info['password']
        }
    )

    if login_response.status_code != 200:
        print(f"   ✗ 登录失败: {login_response.status_code}")
        print(f"   提示: 如果密码错误，请在浏览器登录后查看实际密码")
        continue

    token = login_response.json()["access_token"]
    user_data = login_response.json()["user"]
    print(f"   ✓ 登录成功")
    print(f"   用户ID: {user_data['id']}")
    print(f"   组织ID: {user_data['org_id']}")
    print(f"   角色: {user_data['role']}")

    # 2. 获取设备列表
    print(f"\n2. 查询 {user_info['username']} 的设备列表...")
    headers = {"Authorization": f"Bearer {token}"}
    devices_response = requests.get(
        f"{BASE_URL}/api/v1/devices",
        headers=headers
    )

    if devices_response.status_code == 200:
        devices = devices_response.json()
        print(f"   ✓ 设备数量: {len(devices)}")

        if devices:
            print(f"\n   设备列表:")
            for i, device in enumerate(devices, 1):
                print(f"   {i}. {device['name']} (MN: {device['mn']}, 组织: {device['org_id']})")
        else:
            print(f"   (当前无设备)")
    else:
        print(f"   ✗ 获取设备列表失败: {devices_response.status_code}")

    # 3. 尝试创建一个测试设备
    print(f"\n3. 为 {user_info['username']} 创建测试设备...")
    timestamp = int(time.time())
    device_data = {
        "mn": f"TEST_{user_info['username'].upper()}_{timestamp}",
        "name": f"{user_info['username']}的测试设备",
        "device_type": "water",
        "org_id": user_data['org_id'],  # 使用用户的组织ID
        "address": "测试地址"
    }

    create_response = requests.post(
        f"{BASE_URL}/api/v1/devices",
        headers=headers,
        json=device_data
    )

    if create_response.status_code == 201:
        device = create_response.json()
        print(f"   ✓ 设备创建成功")
        print(f"   设备名称: {device['name']}")
        print(f"   设备MN: {device['mn']}")
        print(f"   所属组织: {device['org_id']}")
    elif create_response.status_code == 400:
        error_detail = create_response.json().get('detail', 'Unknown error')
        if 'already exists' in error_detail:
            print(f"   ⚠ 设备MN已存在（可能之前创建过）")
        else:
            print(f"   ✗ 创建失败: {error_detail}")
    else:
        print(f"   ✗ 创建失败: {create_response.status_code}")
        print(f"   错误: {create_response.text}")

print("\n" + "=" * 70)
print("验证结果总结")
print("=" * 70)
print()
print("✅ 如果两个用户看到的设备列表不同 → 数据隔离成功")
print("❌ 如果两个用户看到相同的设备列表 → 数据隔离失败")
print()
print("注意:")
print("  1. 如果登录失败，请确认用户密码正确")
print("  2. 如果看不到设备，这是正常的（旧设备还在原组织）")
print("  3. 创建的新设备应该只对当前用户可见")
print("=" * 70)
