"""Memory system environment variable settings mixin."""

from pydantic_settings import BaseSettings


class MemorySettingsConfig(BaseSettings):
    """Memory-related environment variables — simplified."""

    MEMORY_GATE_DUPLICATE_SIMILARITY: float = 0.95
    MEMORY_TREE_ROOT_DIR: str = "memory_pipeline"
    MEMORY_TREE_LIST_MAX_RESULTS: int = 200
    MEMORY_TREE_READ_MAX_CHARS: int = 200_000
    MEMORY_TREE_SEARCH_MAX_RESULTS: int = 20
    MEMORY_TREE_MAX_FILES: int = 50
    MEMORY_TREE_MAX_CHARS_PER_FILE: int = 4_000
    MEMORY_TREE_MAX_TOTAL_CHARS: int = 20_000
    MEMORY_RETRIEVE_REACT_ENABLED: bool = True
    MEMORY_RETRIEVE_REACT_MAX_STEPS: int = 5
    MEMORY_RETRIEVE_REACT_MAX_SEARCH_ACTIONS: int = 3
    MEMORY_RETRIEVE_REACT_MAX_EXPAND_ACTIONS: int = 2
    MEMORY_RETRIEVE_REACT_CANDIDATE_POOL_MULTIPLIER: int = 4
    MEMORY_RETRIEVE_REACT_JUDGE_POOL_MULTIPLIER: int = 6
    MEMORY_RETRIEVE_REACT_STOP_SCORE: float = 0.88
    MEMORY_RETRIEVE_REACT_MIN_NEW_CANDIDATES: int = 1
