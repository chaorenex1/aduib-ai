from decimal import Decimal
from enum import Enum, StrEnum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ModelType(Enum):
    """Model type enum."""
    LLM = "llm"
    EMBEDDING = "embedding"
    ASR = "asr"
    TTS = "tts"
    RERANKER = "reranker"
    MODERATION = "moderation"

    @classmethod
    def value_of(cls, origin_model_type)->"ModelType":
        """Get ModelType from string."""
        for model_type in cls:
            if model_type.value == origin_model_type:
                return model_type
        raise ValueError(f"{origin_model_type} is not a valid model type")

    def to_model_type(self)->str:
        if self==self.LLM:
            return "llm"
        elif self==self.EMBEDDING:
            return "embedding"
        elif self==self.ASR:
            return "asr"
        elif self==self.TTS:
            return "tts"
        elif self==self.RERANKER:
            return "reranker"
        elif self==self.MODERATION:
            return "moderation"
        else:
            raise ValueError(f"{self} is not a valid model type")


class ModelFeature(Enum):
    """
    Enum class for llm feature.
    """

    TOOL = "tool"
    PARALLEL_TOOL = "parallel_tool"
    VISION = "vision"
    DOCUMENT = "document"
    VIDEO = "video"
    AUDIO = "audio"
    THINKING = "thinking"
    STREAMING = "streaming"
    STRUCTURED_OUTPUTS = "structured_outputs"


class DefaultParameterName(StrEnum):
    """
    Enum class for parameter template variable.
    """

    TEMPERATURE = "temperature"
    TOP_P = "top_p"
    TOP_K = "top_k"
    PRESENCE_PENALTY = "presence_penalty"
    FREQUENCY_PENALTY = "frequency_penalty"
    REPEAT_PENALTY = "repeat_penalty"
    MAX_TOKENS = "max_tokens"
    RESPONSE_FORMAT = "response_format"
    JSON_SCHEMA = "json_schema"
    MAX_EMBEDDING_TOKENS = "max_embedding_tokens"

    @classmethod
    def value_of(cls, value: Any) -> "DefaultParameterName":
        """
        Get parameter name from value.

        :param value: parameter value
        :return: parameter name
        """
        for name in cls:
            if name.value == value:
                return name
        raise ValueError(f"invalid parameter name {value}")


class ParameterType(Enum):
    """
    Enum class for parameter type.
    """

    FLOAT = "float"
    INT = "int"
    STRING = "string"
    BOOLEAN = "boolean"
    TEXT = "text"


class ProviderModel(BaseModel):
    """
    Model class for provider model.
    """

    model: str
    model_type: ModelType
    features: Optional[list[ModelFeature]] = None
    model_properties: dict[str, Any]
    deprecated: bool = False
    model_config = ConfigDict(protected_namespaces=())


class ParameterRule(BaseModel):
    """
    Model class for parameter rule.
    """

    name: str
    use_template: Optional[str] = None
    type: ParameterType
    required: bool = False
    default: Optional[Any] = None
    min: Optional[float] = None
    max: Optional[float] = None
    precision: Optional[int] = None
    options: list[str] = []


class PriceConfig(BaseModel):
    """
    Model class for pricing info.
    """

    input: Decimal
    output: Optional[Decimal] = None
    unit: Decimal = Decimal("1.0")
    currency: str= "USD"


class AIModelEntity(ProviderModel):
    """
    Model class for AI model.
    """

    parameter_rules: list[ParameterRule] = []
    pricing: Optional[PriceConfig] = None


class ModelUsage(BaseModel):
    pass


class PriceType(Enum):
    """
    Enum class for price type.
    """

    INPUT = "input"
    OUTPUT = "output"


class PriceInfo(BaseModel):
    """
    Model class for price info.
    """

    unit_price: Decimal
    unit: Decimal
    total_amount: Decimal
    currency: str





