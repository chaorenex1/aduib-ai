"""Memory system environment variable settings mixin."""

from pydantic_settings import BaseSettings


class MemorySettingsConfig(BaseSettings):
    """Memory-related environment variables — simplified."""

    MEMORY_GATE_DUPLICATE_SIMILARITY: float = 0.95
    MEMORY_RETRIEVE_REACT_ENABLED: bool = True
    MEMORY_RETRIEVE_REACT_MAX_STEPS: int = 5
    MEMORY_RETRIEVE_REACT_MAX_SEARCH_ACTIONS: int = 3
    MEMORY_RETRIEVE_REACT_MAX_EXPAND_ACTIONS: int = 2
    MEMORY_RETRIEVE_REACT_CANDIDATE_POOL_MULTIPLIER: int = 4
    MEMORY_RETRIEVE_REACT_JUDGE_POOL_MULTIPLIER: int = 6
    MEMORY_RETRIEVE_REACT_STOP_SCORE: float = 0.88
    MEMORY_RETRIEVE_REACT_MIN_NEW_CANDIDATES: int = 1
