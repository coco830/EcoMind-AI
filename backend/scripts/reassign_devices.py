#!/usr/bin/env python3
"""手动将设备重新分配给用户组织"""

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


async def reassign_devices():
    """显示设备列表并让用户选择重新分配"""

    async with AsyncSessionLocal() as session:
        try:
            # 获取所有用户
            result = await session.execute(
                select(User).where(User.is_superadmin == False).order_by(User.username)
            )
            users = result.scalars().all()

            # 获取所有设备
            result = await session.execute(select(Device).order_by(Device.name))
            devices = result.scalars().all()

            logger.info("=" * 60)
            logger.info("设备重新分配工具")
            logger.info("=" * 60)
            logger.info("")

            # 显示用户列表
            logger.info("可用用户:")
            for i, user in enumerate(users, 1):
                logger.info(
                    f"{i}. {user.username} (组织: {user.org_id})"
                )
            logger.info("")

            # 显示设备列表
            logger.info("现有设备:")
            for i, device in enumerate(devices, 1):
                logger.info(
                    f"{i}. {device.name} (MN: {device.mn}, 当前组织: {device.org_id})"
                )
            logger.info("")

            # 交互式分配
            logger.info("请输入设备编号和用户编号进行分配")
            logger.info("格式: 设备编号 用户编号")
            logger.info("例如: 1 1 (将设备1分配给用户1)")
            logger.info("输入 'done' 完成分配")
            logger.info("")

            while True:
                try:
                    user_input = input("请输入: ").strip()

                    if user_input.lower() == 'done':
                        break

                    parts = user_input.split()
                    if len(parts) != 2:
                        logger.warning("格式错误，请输入: 设备编号 用户编号")
                        continue

                    device_idx = int(parts[0]) - 1
                    user_idx = int(parts[1]) - 1

                    if device_idx < 0 or device_idx >= len(devices):
                        logger.warning("设备编号无效")
                        continue

                    if user_idx < 0 or user_idx >= len(users):
                        logger.warning("用户编号无效")
                        continue

                    device = devices[device_idx]
                    user = users[user_idx]

                    old_org = device.org_id
                    device.org_id = user.org_id

                    logger.info(
                        f"已将设备 '{device.name}' 分配给 '{user.username}' 的组织",
                        old_org=str(old_org),
                        new_org=str(user.org_id)
                    )

                except ValueError:
                    logger.warning("请输入有效的数字")
                except KeyboardInterrupt:
                    logger.info("\n取消分配")
                    return

            # 提交更改
            await session.commit()
            logger.info("")
            logger.info("=" * 60)
            logger.info("设备分配完成！")
            logger.info("=" * 60)

        except Exception as e:
            await session.rollback()
            logger.error("分配失败", error=str(e), exc_info=True)
            raise


async def quick_assign_by_name():
    """快速分配：根据设备创建者推测所有权"""

    async with AsyncSessionLocal() as session:
        try:
            logger.info("=" * 60)
            logger.info("快速设备分配（基于推测）")
            logger.info("=" * 60)
            logger.info("")

            # 获取用户
            result = await session.execute(select(User))
            users = {user.username: user for user in result.scalars().all()}

            # 获取设备
            result = await session.execute(select(Device))
            devices = result.scalars().all()

            logger.info("建议分配方案:")
            logger.info("  - userA 的设备 → userA 的组织")
            logger.info("  - yangkaidi 的设备 → yangkaidi 的组织")
            logger.info("  - 其他设备 → 保留在原组织或分配给默认用户")
            logger.info("")

            # 这里你需要根据实际情况手动指定哪些设备属于哪个用户
            # 因为数据库中没有记录设备的创建者
            device_owner_map = {
                # "设备MN": "用户名"
                # 示例:
                # "123": "userA",
                # "321": "yangkaidi",
            }

            assigned_count = 0
            for device in devices:
                if device.mn in device_owner_map:
                    owner_username = device_owner_map[device.mn]
                    if owner_username in users:
                        user = users[owner_username]
                        old_org = device.org_id
                        device.org_id = user.org_id
                        assigned_count += 1
                        logger.info(
                            f"分配设备: {device.name} → {owner_username}",
                            mn=device.mn,
                            old_org=str(old_org),
                            new_org=str(user.org_id)
                        )

            if assigned_count > 0:
                await session.commit()
                logger.info("")
                logger.info(f"成功分配 {assigned_count} 个设备")
            else:
                logger.warning("没有设备需要分配")
                logger.warning("请编辑此脚本的 device_owner_map 字典来指定设备所有权")

        except Exception as e:
            await session.rollback()
            logger.error("分配失败", error=str(e), exc_info=True)
            raise


async def main():
    """主函数"""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "quick":
        await quick_assign_by_name()
    else:
        await reassign_devices()


if __name__ == "__main__":
    asyncio.run(main())
