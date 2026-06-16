"""Reset admin password from ADMIN_PASSWORD environment variable.

Usage (inside Docker):
    docker compose exec api python scripts/reset_admin.py

Usage (locally with venv):
    python scripts/reset_admin.py

The new password is read from the ADMIN_PASSWORD env var (set in .env).
Never hardcode credentials here — this file is committed to version control.
"""
import asyncio
import os
import sys
sys.path.insert(0, "/app")

from app.db.session import AsyncSessionLocal
from app.db import crud


async def main():
    new_password = os.environ.get("ADMIN_PASSWORD", "")
    if not new_password:
        print("ERROR: ADMIN_PASSWORD environment variable is not set.")
        print("Add ADMIN_PASSWORD=<your-password> to your .env file and retry.")
        sys.exit(1)

    async with AsyncSessionLocal() as db:
        user = await crud.get_user_by_username(db, "admin")
        if not user:
            print("Admin user not found — creating...")
            user = await crud.create_user(
                db,
                username="admin",
                email="admin@workforce.local",
                password=new_password,
                full_name="Platform Admin",
                roles=["admin", "agent"],
                scopes=["chat", "voice", "workflows", "audit"],
                is_superuser=True,
            )
            await db.commit()
            print(f"Created admin user with password from ADMIN_PASSWORD env var.")
        else:
            user.hashed_password = crud.hash_password(new_password)
            user.roles = ["admin", "agent"]
            user.scopes = ["chat", "voice", "workflows", "audit"]
            user.is_active = True
            user.is_superuser = True
            await db.commit()
            print(f"Password reset for user '{user.username}' using ADMIN_PASSWORD env var.")


asyncio.run(main())
