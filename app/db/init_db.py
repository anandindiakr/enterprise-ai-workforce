"""Database initialisation: create tables and seed default users."""
from __future__ import annotations

from loguru import logger

from app.db.models import Base
from app.db.session import AsyncSessionLocal, engine
from app.db.crud import (
    create_user,
    get_user_by_username,
    hash_password,
)


async def init_db() -> None:
    """Create all tables and seed default users on first start.

    The two built-in demo accounts (``admin`` / ``agent``) have their
    credentials **reset deterministically on every startup** so the documented
    logins always work, even if an earlier build seeded them with a different
    password. This is intentional for the demo/default tenant.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified.")

    async with AsyncSessionLocal() as db:
        # ── Admin: admin / admin ────────────────────────────────────────────
        admin = await get_user_by_username(db, "admin")
        if admin is None:
            await create_user(
                db,
                username="admin",
                email="admin@workforce.local",
                password="admin",
                full_name="Platform Admin",
                roles=["admin", "agent"],
                scopes=["chat", "voice", "workflows", "audit"],
                is_superuser=True,
            )
            logger.info("Seeded default admin user (admin/admin).")
        else:
            # Force-reset to the documented credentials + privileges.
            admin.hashed_password = hash_password("admin")
            admin.roles = ["admin", "agent"]
            admin.scopes = ["chat", "voice", "workflows", "audit"]
            admin.is_superuser = True
            admin.is_active = True
            logger.info("Reset default admin user credentials (admin/admin).")

        # ── Demo agent: agent / agent123 ────────────────────────────────────
        agent = await get_user_by_username(db, "agent")
        if agent is None:
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
        else:
            agent.hashed_password = hash_password("agent123")
            agent.is_active = True
            logger.info("Reset default agent user credentials (agent/agent123).")

        await db.commit()

    logger.info("Database initialisation complete.")
