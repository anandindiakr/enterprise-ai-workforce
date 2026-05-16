"""Reset admin password and ensure correct role."""
import asyncio
import sys
sys.path.insert(0, "/app")

from app.db.session import AsyncSessionLocal
from app.db import crud


async def main():
    async with AsyncSessionLocal() as db:
        user = await crud.get_user_by_username(db, "admin")
        if not user:
            print("Admin user not found — creating...")
            user = await crud.create_user(
                db,
                username="admin",
                email="admin@workforce.ai",
                password="changeme123",
                full_name="Platform Admin",
                roles=["admin", "agent"],
                scopes=["*"],
            )
            await db.commit()
            print(f"Created admin user: {user.username}")
        else:
            print(f"Found user: {user.username}, roles={user.roles}")
            # Reset password
            user.hashed_password = crud.hash_password("changeme123")
            user.roles = ["admin", "agent"]
            user.scopes = ["*"]
            user.is_active = True
            await db.commit()
            print("Password reset to: changeme123, roles set to: admin,agent")


asyncio.run(main())
