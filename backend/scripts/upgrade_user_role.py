#!/usr/bin/env python3
"""升级现有 viewer 用户为 operator 角色"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
import structlog

from app.db.postgres import AsyncSessionLocal
from app.models.user import User, UserRole

logger = structlog.get_logger()


async def upgrade_users():
    """升级所有 viewer 用户为 operator"""
    logger.info("开始升级用户角色...")

    async with AsyncSessionLocal() as session:
        try:
            # 查找所有 viewer 用户（非超级管理员）
            result = await session.execute(
                select(User).where(
                    User.role == UserRole.VIEWER.value,
                    User.is_superadmin == False
                )
            )
            viewer_users = result.scalars().all()

            if not viewer_users:
                logger.info("没有需要升级的用户")
                return

            logger.info(f"找到 {len(viewer_users)} 个 viewer 用户")

            # 升级为 operator
            upgraded_count = 0
            for user in viewer_users:
                old_role = user.role
                user.role = UserRole.OPERATOR.value
                upgraded_count += 1
                logger.info(
                    f"升级用户: {user.username} ({user.email})",
                    old_role=old_role,
                    new_role=user.role
                )

            # 提交更改
            await session.commit()

            logger.info("=" * 60)
            logger.info(f"成功升级 {upgraded_count} 个用户为 operator 角色")
            logger.info("=" * 60)

        except Exception as e:
            await session.rollback()
            logger.error("升级失败", error=str(e), exc_info=True)
            raise


async def main():
    """主函数"""
    try:
        await upgrade_users()
        logger.info("升级完成！现有用户现在可以创建和管理设备了。")
    except Exception as e:
        logger.error("升级失败", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
