#!/usr/bin/env python3
"""检查用户和设备的组织分配"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
import structlog

from app.db.postgres import AsyncSessionLocal
from app.models.user import User
from app.models.device import Device

logger = structlog.get_logger()


async def check_data():
    """检查用户和设备的组织分配"""

    async with AsyncSessionLocal() as session:
        # 查询 userA 和 yangkaidi
        result = await session.execute(
            select(User).where(User.username.in_(['userA', 'yangkaidi']))
        )
        users = result.scalars().all()

        print("=" * 60)
        print("用户信息:")
        print("=" * 60)
        for user in users:
            print(f"用户名: {user.username}")
            print(f"  邮箱: {user.email}")
            print(f"  角色: {user.role}")
            print(f"  组织ID: {user.org_id}")
            print(f"  是否superadmin: {user.is_superadmin}")
            print()

        # 查询所有设备
        result = await session.execute(select(Device))
        devices = result.scalars().all()

        print("=" * 60)
        print("设备信息:")
        print("=" * 60)
        for device in devices:
            print(f"设备名称: {device.name}")
            print(f"  MN号: {device.mn}")
            print(f"  组织ID: {device.org_id}")
            print()

        # 检查是否所有用户都在同一个组织
        user_orgs = set([u.org_id for u in users if u.org_id])
        if len(user_orgs) == 1:
            print("⚠️  问题发现：所有用户都在同一个组织中！")
            print(f"   组织ID: {list(user_orgs)[0]}")
        else:
            print("✓ 用户分属不同组织")

        print()


if __name__ == "__main__":
    asyncio.run(check_data())
