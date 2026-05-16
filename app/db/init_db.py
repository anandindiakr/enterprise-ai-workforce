"""Database initialisation: create tables and seed default users."""
from __future__ import annotations

from loguru import logger

from app.db.models import Base
from app.db.session import AsyncSessionLocal, engine
from app.db.crud import create_user, get_user_by_username


async def init_db() -> None:
    """Create all tables and seed default users on first start."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified.")

    async with AsyncSessionLocal() as db:
        # Seed admin
        if not await get_user_by_username(db, "admin"):
            await create_user(
                db,
                username="admin",
                email="admin@workforce.local",
                password="admin123",
                full_name="Platform Admin",
                roles=["admin", "agent"],
                scopes=["chat", "voice", "workflows", "audit"],
                is_superuser=True,
            )
            logger.info("Seeded default admin user (admin/admin123).")

        # Seed demo agent user
        if not await get_user_by_username(db, "agent"):
            await create_user(
                db,
                username="agent",
                email="agent@workforce.local",
                password="agent123",
                full_name="Demo Agent",
                roles=["agent"],
                scopes=["chat", "voice"],
            )
            logger.info("Seeded default agent user (agent/agent123).")

        await db.commit()

    logger.info("Database initialisation complete.")
