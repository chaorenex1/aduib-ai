from pydantic import Field
from pydantic_settings import BaseSettings


class SentryConfig(BaseSettings):
    SENTRY_DSN: str=Field(default="",description="Sentry DSN")
    SENTRY_TRACE_SAMPLE_RATE: float=Field(default=1.0,description="Sentry trace sample rate")
    SENTRY_PROFILING_SAMPLE_RATE: float=Field(default=1.0,description="Sentry profiling sample rate")