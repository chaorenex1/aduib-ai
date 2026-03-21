from pydantic_settings import BaseSettings


class ToolChoiceConfig(BaseSettings):
    TOOL_CHOICE_LLM_MODEL: str = ""
    TOOL_CHOICE_LLM_PROVIDER: str = ""
    TOOL_CHOICE_SLICE_SIZE: int = 10
    TOOL_CHOICE_SLICE_WORKERS: int = 4
    TOOL_CHOICE_CANDIDATE_COUNT: int = 3
    TOOL_CHOICE_CACHE_ENABLED: bool = True
    TOOL_CHOICE_CACHE_TTL: int = 86400
