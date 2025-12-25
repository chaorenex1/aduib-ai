from __future__ import annotations

from celery import Celery

from configs import config


def _build_default_redis_url(db_override: int | None = None) -> str:
    host = getattr(config, "REDIS_HOST", "localhost")
    port = getattr(config, "REDIS_PORT", 6379)
    db = db_override if db_override is not None else getattr(config, "REDIS_DB", 0)
    username = getattr(config, "REDIS_USERNAME", None)
    password = getattr(config, "REDIS_PASSWORD", None)

    credentials = ""
    if username and password:
        credentials = f"{username}:{password}@"
    elif password:
        credentials = f":{password}@"

    return f"redis://{credentials}{host}:{port}/{db}"


def _resolve_broker_url() -> str:
    return getattr(config, "CELERY_BROKER_URL", None) or _build_default_redis_url()


def _resolve_backend_url(broker_url: str) -> str:
    return getattr(config, "CELERY_RESULT_BACKEND", None) or broker_url


broker_url = _resolve_broker_url()
backend_url = _resolve_backend_url(broker_url)

celery_app = Celery(
    "aduib_ai",
    broker=broker_url,
    backend=backend_url,
    include=["runtime.tasks.qa_memory_tasks"],
)

celery_app.conf.task_default_queue = getattr(config, "CELERY_TASK_DEFAULT_QUEUE", "aduib_ai")
celery_app.conf.result_expires = 600
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.task_acks_late = True

if getattr(config, "CELERY_BEAT_SCHEDULE_ENABLED", True):
    interval = max(60, int(getattr(config, "CELERY_EXPIRE_TASK_INTERVAL_SECONDS", 900)))
    celery_app.conf.beat_schedule = {
        "qa-memory-expiry-sweep": {
            "task": "runtime.tasks.qa_memory_tasks.expire_qa_memory_task",
            "schedule": interval,
            "options": {"queue": celery_app.conf.task_default_queue},
        }
    }

__all__ = ["celery_app"]
