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

    Documented credentials (shown on the login screen):
      admin / admin123   (full access)
      agent / agent123   (agent access)
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified.")

    # ── Schema drift repair ────────────────────────────────────────────────
    # Older builds created users.roles / users.scopes as Postgres ``varchar[]``
    # (ARRAY). The current model maps them to JSON. ``create_all`` never alters
    # existing columns, so the type mismatch crashes the seed UPDATE below
    # (and thus the whole app). Convert ARRAY columns to JSON idempotently.
    await _migrate_user_array_columns_to_json()

    async with AsyncSessionLocal() as db:
        # ── Admin: admin / admin123 ─────────────────────────────────────────
        admin = await get_user_by_username(db, "admin")
        if admin is None:
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
        else:
            # Force-reset to the documented credentials + privileges.
            admin.hashed_password = hash_password("admin123")
            admin.roles = ["admin", "agent"]
            admin.scopes = ["chat", "voice", "workflows", "audit"]
            admin.is_superuser = True
            admin.is_active = True
            logger.info("Reset default admin user credentials (admin/admin123).")

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


async def _migrate_user_array_columns_to_json() -> None:
    """Convert legacy ``users.roles`` / ``users.scopes`` ARRAY columns to JSON.

    Idempotent and Postgres-only. On SQLite (tests) the information_schema
    query simply yields nothing and we no-op. Never raises — a failure here
    must not block startup.
    """
    from sqlalchemy import text

    try:
        async with engine.begin() as conn:
            for column in ("roles", "scopes"):
                row = await conn.execute(
                    text(
                        "SELECT data_type FROM information_schema.columns "
                        "WHERE table_name = 'users' AND column_name = :col"
                    ),
                    {"col": column},
                )
                data_type = (row.scalar() or "").lower()
                if data_type == "array":
                    await conn.execute(
                        text(
                            f"ALTER TABLE users ALTER COLUMN {column} TYPE json "
                            f"USING to_jsonb({column})"
                        )
                    )
                    logger.warning(
                        "Migrated users.{} from ARRAY to JSON (schema drift repair).",
                        column,
                    )
    except Exception as exc:  # noqa: BLE001
        logger.warning("User column type migration skipped: {}", exc)
