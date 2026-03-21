from pydantic_settings import BaseSettings


class ToolConfig(BaseSettings):
    SKILLS_PATH: str = ""
    SKILL_VALIDATE: bool = True
    TOOL_CACHE_ENABLED: bool = True
    TOOL_CACHE_TTL: int = 3600
    TOOL_CHOICE_LLM_MODEL: str = ""
    TOOL_CHOICE_LLM_PROVIDER: str = ""
    TOOL_CHOICE_SLICE_SIZE: int = 10
    TOOL_CHOICE_SLICE_WORKERS: int = 4
