"""Memory system environment variable settings mixin."""

from pydantic_settings import BaseSettings


class MemorySettingsConfig(BaseSettings):
    """Memory-related environment variables — simplified."""

    MEMORY_GATE_DUPLICATE_SIMILARITY: float = 0.95
