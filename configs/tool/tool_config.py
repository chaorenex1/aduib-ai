from pydantic_settings import BaseSettings


class ToolConfig(BaseSettings):
    SKILLS_PATH: str = ""
    SKILL_VALIDATE: bool = True
    TOOL_CACHE_ENABLED: bool = True
    TOOL_CACHE_TTL: int = 3600
    TOOL_CACHE_MAX_SIZE: int = 500
    CAPABILITY_SEARCH_LIMIT: int = 10
    CAPABILITY_SYNC_ON_STARTUP: bool = True
