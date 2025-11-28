#!/usr/bin/env python3
"""Reset admin user password to use bcrypt hashing."""

import asyncio
import sys
from pathlib import Path

# Add backend directory to path
sys.path.append(str(Path(__file__).parent))

from sqlalchemy import select
from app.db.postgres import init_db, AsyncSessionLocal
from app.models.user import User
from app.core.security import get_password_hash


async def reset_admin_password():
    """Reset admin password with proper bcrypt hashing."""

    # Initialize database
    print("Initializing database...")
    await init_db()

    async with AsyncSessionLocal() as session:
        try:
            # Find admin user
            result = await session.execute(
                select(User).where(User.username == "admin")
            )
            admin_user = result.scalar_one_or_none()

            if admin_user:
                print(f"Found admin user: {admin_user.username}")

                # Update password with bcrypt
                new_password = "admin123"
                admin_user.hashed_password = get_password_hash(new_password)

                await session.commit()
                print(f"✅ Password reset successful!")
                print(f"   Username: admin")
                print(f"   Password: {new_password}")
            else:
                print("❌ Admin user not found. Please create it first.")

        except Exception as e:
            print(f"❌ Error resetting password: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(reset_admin_password())