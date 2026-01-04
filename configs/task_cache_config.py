"""
Task Cache Configuration for P2 Performance Optimization
"""
from pydantic_settings import BaseSettings


class TaskCacheConfig(BaseSettings):
    """Task Cache P2 configuration"""

    # Cache settings
    TASK_CACHE_STATS_TTL: int = 300  # Statistics cache TTL in seconds (5 minutes)
    TASK_CACHE_ENABLE_REDIS: bool = True  # Enable Redis caching for statistics

    # Retention settings
    TASK_CACHE_RETENTION_DAYS: int = 90  # Keep tasks for 90 days by default
    TASK_CACHE_AUTO_CLEANUP_ENABLED: bool = True  # Enable automatic cleanup
    TASK_CACHE_CLEANUP_HOUR: int = 2  # Run cleanup at 2 AM daily

    # Performance settings
    TASK_CACHE_BATCH_SIZE: int = 500  # Batch insert size for optimization
    TASK_CACHE_ENABLE_METRICS: bool = True  # Enable performance metrics logging

    # Rate limiting
    TASK_CACHE_MAX_EXPORT_SIZE: int = 10000  # Maximum export size
    TASK_CACHE_MAX_BATCH_SIZE: int = 100  # Maximum batch save size

    class Config:
        env_prefix = ""
