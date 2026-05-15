"""Structured JSON logging via Loguru, integrated with stdlib logging.

All modules should ``from app.core.logging import logger`` rather than
configuring loggers ad-hoc.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from loguru import logger as _logger

from app.core.config import settings


class _InterceptHandler(logging.Handler):
    """Forward stdlib log records to Loguru."""

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
        try:
            level: str | int = _logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1

        _logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def configure_logging() -> None:
    """Idempotently configure Loguru for the current process."""
    _logger.remove()
    serialize = settings.is_production
    _logger.add(
        sys.stdout,
        level=settings.app_log_level.upper(),
        serialize=serialize,
        backtrace=not settings.is_production,
        diagnose=not settings.is_production,
        enqueue=True,
    )

    # Bridge stdlib loggers (uvicorn, httpx, sqlalchemy, etc.).
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi", "httpx", "asyncio"):
        logging.getLogger(name).handlers = [_InterceptHandler()]
        logging.getLogger(name).propagate = False


def bind(**ctx: Any):
    """Return a logger bound to the given context fields."""
    return _logger.bind(**ctx)


logger = _logger
