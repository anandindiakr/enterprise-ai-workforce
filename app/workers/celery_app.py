"""Celery application factory.

Start workers with:
    celery -A app.workers.celery_app worker --loglevel=info

Start beat scheduler with:
    celery -A app.workers.celery_app beat --loglevel=info
"""
from __future__ import annotations

from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "ai_workforce",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    # Beat schedule for periodic tasks
    beat_schedule={
        "purge-expired-sessions": {
            "task": "app.workers.tasks.purge_expired_voice_sessions",
            "schedule": 300.0,  # every 5 minutes
        },
        "sync-analytics-snapshot": {
            "task": "app.workers.tasks.sync_analytics_snapshot",
            "schedule": 900.0,  # every 15 minutes
        },
    },
)
