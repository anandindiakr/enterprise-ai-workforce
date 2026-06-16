"""Database initialisation: create tables and seed default users."""
from __future__ import annotations

from loguru import logger

from app.core.config import settings
from app.db.models import Base
from app.db.session import AsyncSessionLocal, engine
from app.db.crud import (
    create_user,
    get_user_by_username,
    hash_password,
)


async def init_db() -> None:
    """Create all tables and seed built-in accounts on first start.

    Credentials are read from environment variables (ADMIN_PASSWORD,
    AGENT_PASSWORD) set in the server's .env file — they are never
    hardcoded here or shown on any public-facing page.

    Behaviour:
    - If the account does NOT exist → create it with the env password.
    - If the account already exists → leave the password untouched so
      that admin-initiated password changes survive a container restart.
    - Roles and scopes are always kept up to date.
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
        # ── Admin account ──────────────────────────────────────────────────
        admin = await get_user_by_username(db, "admin")
        if admin is None:
            await create_user(
                db,
                username="admin",
                email="admin@workforce.local",
                password=settings.admin_password,
                full_name="Platform Admin",
                roles=["admin", "agent"],
                scopes=["chat", "voice", "workflows", "audit"],
                is_superuser=True,
            )
            logger.info("Seeded admin user from ADMIN_PASSWORD env var.")
        else:
            # Keep roles / scopes current; leave password unchanged so that
            # any password change made in production survives a restart.
            admin.roles = ["admin", "agent"]
            admin.scopes = ["chat", "voice", "workflows", "audit"]
            admin.is_superuser = True
            admin.is_active = True
            logger.info("Admin account verified (password unchanged).")

        # ── Agent account ──────────────────────────────────────────────────
        agent = await get_user_by_username(db, "agent")
        if agent is None:
            await create_user(
                db,
                username="agent",
                email="agent@workforce.local",
                password=settings.agent_password,
                full_name="Platform Agent",
                roles=["agent"],
                scopes=["chat", "voice"],
            )
            logger.info("Seeded agent user from AGENT_PASSWORD env var.")
        else:
            agent.roles = ["agent"]
            agent.is_active = True
            logger.info("Agent account verified (password unchanged).")

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
