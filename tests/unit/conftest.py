"""Pytest configuration for unit tests.

asyncio_mode = "auto" is set in pyproject.toml so all async fixtures/tests
work without any extra markers.
"""
from __future__ import annotations

import pytest


@pytest.fixture
async def db_session():
    """Provide an in-memory async SQLite session for unit tests."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.db.models import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        async with session.begin():
            yield session
    await engine.dispose()
