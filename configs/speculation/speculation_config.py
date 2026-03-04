from pydantic_settings import BaseSettings


class SpeculationConfig(BaseSettings):
    """Speculative tool execution configuration."""

    SPECULATION_ENABLED: bool = False
    SPECULATION_PLANNER_MODEL: str = ""
    SPECULATION_PLANNER_PROVIDER: str = ""
    SPECULATION_MAX_SPECULATIVE_TOOLS: int = 3
    SPECULATION_CONFIDENCE_THRESHOLD: float = 0.7
    SPECULATION_CACHE_MAX_SIZE: int = 50
