from pydantic import Field
from pydantic_settings import BaseSettings


class CeleryConfig(BaseSettings):
    """
    Celery configuration scoped to Aduib AI services.
    """

    CELERY_BROKER_URL: str | None = Field(
        default=None,
        description="Celery broker URL; defaults to the primary Redis instance when unset.",
    )
    CELERY_RESULT_BACKEND: str | None = Field(
        default=None,
        description="Celery result backend URL; defaults to CELERY_BROKER_URL when unset.",
    )
    CELERY_TASK_DEFAULT_QUEUE: str = Field(
        default="aduib_ai",
        description="Default Celery queue name for background jobs.",
    )
    CELERY_BEAT_SCHEDULE_ENABLED: bool = Field(
        default=True,
        description="Enable default Celery beat schedules provided by the app.",
    )
    CELERY_EXPIRE_TASK_INTERVAL_SECONDS: int = Field(
        default=900,
        description="Interval in seconds between QA memory expiry sweeps.",
    )
