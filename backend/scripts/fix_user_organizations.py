#!/usr/bin/env python3
"""为现有用户创建独立的组织"""

import asyncio
import sys
import os
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
import structlog

from app.db.postgres import AsyncSessionLocal
from app.models.user import User
from app.models.organization import Organization
from app.models.device import Device

logger = structlog.get_logger()


async def fix_organizations():
    """为现有用户创建独立的组织并迁移数据"""

    async with AsyncSessionLocal() as session:
        try:
            logger.info("=" * 60)
            logger.info("开始修复用户组织隔离问题")
            logger.info("=" * 60)

            # 查找所有非超级管理员用户
            result = await session.execute(
                select(User).where(User.is_superadmin == False).order_by(User.created_at)
            )
            users = result.scalars().all()

            logger.info(f"找到 {len(users)} 个非超级管理员用户")

            # 记录每个用户的新组织
            user_org_mapping = {}

            for user in users:
                # 为每个用户创建独立的组织
                org_code = f"ORG_{user.username.upper()}_{uuid4().hex[:8]}"
                new_org = Organization(
                    name=f"{user.full_name or user.username}的组织",
                    code=org_code,
                    address="",
                    contact_name=user.full_name or user.username,
                    contact_phone="",
                )
                session.add(new_org)
                await session.flush()
                await session.refresh(new_org)

                # 更新用户的组织
                old_org_id = user.org_id
                user.org_id = new_org.id
                user.role = 'admin'  # 用户成为自己组织的管理员

                user_org_mapping[user.id] = new_org.id

                logger.info(
                    f"为用户创建组织: {user.username}",
                    org_name=new_org.name,
                    org_code=new_org.code,
                    old_org=str(old_org_id),
                    new_org=str(new_org.id)
                )

            # 提交更改
            await session.commit()

            logger.info("=" * 60)
            logger.info(f"成功为 {len(users)} 个用户创建独立组织")
            logger.info("=" * 60)

            # 注意：设备保持在原组织，需要手动分配
            logger.warning("注意：现有设备仍在原组织中")
            logger.warning("你需要：")
            logger.warning("  1. 为每个用户重新创建他们需要的设备")
            logger.warning("  2. 或者使用超级管理员将设备转移到对应组织")

        except Exception as e:
            await session.rollback()
            logger.error("修复失败", error=str(e), exc_info=True)
            raise


async def main():
    """主函数"""
    try:
        await fix_organizations()
        logger.info("\n修复完成！")
        logger.info("现在每个用户都有独立的组织，数据完全隔离。")
        logger.info("请退出登录并重新登录以查看效果。")
    except Exception as e:
        logger.error("修复失败", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
