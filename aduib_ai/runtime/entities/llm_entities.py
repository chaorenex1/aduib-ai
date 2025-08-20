from decimal import Decimal
from enum import StrEnum
from typing import Optional, Union

from pydantic import BaseModel

from .message_entities import PromptMessage, AssistantPromptMessage
from .model_entities import ModelUsage, PriceInfo


class LLMMode(StrEnum):
    """
    Enum class for large language model mode.
    """

    COMPLETION = "completion"
    CHAT = "chat"

    @classmethod
    def value_of(cls, value: str) -> "LLMMode":
        """
        Get value of given mode.

        :param value: mode value
        :return: mode
        """
        for mode in cls:
            if mode.value == value:
                return mode
        raise ValueError(f"invalid mode value {value}")


class LLMUsage(ModelUsage):
    """
    Model class for llm usage.
    """

    prompt_tokens: int = 0
    prompt_unit_price: Decimal= Decimal("0.0")
    prompt_price_unit: Decimal= Decimal("0.0")
    prompt_price: Decimal = Decimal("0.0")
    completion_tokens: int = 0
    completion_unit_price: Decimal = Decimal("0.0")
    completion_price_unit: Decimal = Decimal("0.0")
    completion_price: Decimal = Decimal("0.0")
    total_tokens: int = 0
    total_price: Decimal = Decimal("0.0")
    currency: str = "USD"
    latency: float = 0.0

    @classmethod
    def empty_usage(cls):
        return cls(
            prompt_tokens=0,
            prompt_unit_price=Decimal("0.0"),
            prompt_price_unit=Decimal("0.0"),
            prompt_price=Decimal("0.0"),
            completion_tokens=0,
            completion_unit_price=Decimal("0.0"),
            completion_price_unit=Decimal("0.0"),
            completion_price=Decimal("0.0"),
            total_tokens=0,
            total_price=Decimal("0.0"),
            currency="USD",
            latency=0.0,
        )

    def plus(self, other: "LLMUsage") -> "LLMUsage":
        """
        Add two LLMUsage instances together.

        :param other: Another LLMUsage instance to add
        :return: A new LLMUsage instance with summed values
        """
        if self.total_tokens == 0:
            return other
        else:
            return LLMUsage(
                prompt_tokens=self.prompt_tokens + other.prompt_tokens,
                prompt_unit_price=other.prompt_unit_price,
                prompt_price_unit=other.prompt_price_unit,
                prompt_price=self.prompt_price + other.prompt_price,
                completion_tokens=self.completion_tokens + other.completion_tokens,
                completion_unit_price=other.completion_unit_price,
                completion_price_unit=other.completion_price_unit,
                completion_price=self.completion_price + other.completion_price,
                total_tokens=self.total_tokens + other.total_tokens,
                total_price=self.total_price + other.total_price,
                currency=other.currency,
                latency=self.latency + other.latency,
            )

    def __add__(self, other: "LLMUsage") -> "LLMUsage":
        """
        Overload the + operator to add two LLMUsage instances.

        :param other: Another LLMUsage instance to add
        :return: A new LLMUsage instance with summed values
        """
        return self.plus(other)


class ChatCompletionResponseChunkDelta(BaseModel):
    """
    Model class for llm result chunk delta.
    """

    index: int
    message: AssistantPromptMessage= None
    text: Optional[str] = None
    usage: Optional[LLMUsage] = None
    finish_reason: Optional[str] = None
    delta: Optional[AssistantPromptMessage] = None


class ChatCompletionResponseChunk(BaseModel):
    """
    Model class for llm result chunk.
    """
    id: Optional[str] = None
    object: Optional[str] = None
    created: Optional[int] = None
    model: str= None
    prompt_messages: Union[list[PromptMessage], str]= None
    system_fingerprint: Optional[str] = None
    choices: list[ChatCompletionResponseChunkDelta]= None
    delta: ChatCompletionResponseChunkDelta= None
    usage: Optional[LLMUsage] = None
    done: bool = False


class ChatCompletionResponse(BaseModel):
    """
    Model class for llm result.
    """

    id: Optional[str] = None
    model: str
    prompt_messages: Union[list[PromptMessage], str] = None
    message: AssistantPromptMessage = None
    usage: LLMUsage
    system_fingerprint: Optional[str] = None
    done: bool = False
    choices: list[ChatCompletionResponseChunkDelta] = None


class NumTokensResult(PriceInfo):
    """
    Model class for number of tokens result.
    """

    tokens: int
