from enum import Enum
from typing import Sequence, Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator

from .model_entities import ModelType, AIModelEntity


class ProviderSDKType(Enum):
    OPENAI = "openai"
    OPENAI_LIKE = "openai_like"
    TRANSFORMER = "transformer"
    HUGGINGFACE = "huggingface"
    OLLAMA = "ollama"
    MODELSCOPE = "modelscope"
    GITHUB = "github"
    OTHER = "other"

    @classmethod
    def value_of(cls, origin_sdk_type) -> "ProviderSDKType":
        """Get ModelType from string."""
        for sdk_type in cls:
            if sdk_type.value == origin_sdk_type:
                return sdk_type
        raise ValueError(f"{origin_sdk_type} is not a valid sdk type")

    def to_model_type(self) -> str:
        if self == self.OPENAI:
            return "openai"
        elif self == self.OPENAI_LIKE:
            return "openai_like"
        elif self == self.HUGGINGFACE:
            return "huggingface"
        elif self == self.OLLAMA:
            return "ollama"
        elif self == self.MODELSCOPE:
            return "modelscope"
        elif self == self.OTHER:
            return "other"
        else:
            raise ValueError(f"{self} is not a valid sdk type")

class ProviderConfig(BaseModel):
    """
    Model class for provider config.
    """

    provider: str
    credentials: dict
    sdk_type: ProviderSDKType

class ProviderEntity(BaseModel):
    """
    Model class for provider.
    """

    provider: str
    supported_model_types: Sequence[ModelType]
    models: list[AIModelEntity] = Field(default_factory=list)
    provider_credential: Optional[ProviderConfig] = None

    # pydantic configs
    model_config = ConfigDict(protected_namespaces=())

    @field_validator("models", mode="before")
    @classmethod
    def validate_models(cls, v):
        # returns EmptyList if v is empty
        if not v:
            return []
        return v