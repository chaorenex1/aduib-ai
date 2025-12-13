import logging
from decimal import Decimal
from enum import StrEnum
from typing import Optional, Union, Sequence, Any

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

from .message_entities import (
    PromptMessage,
    AssistantPromptMessage,
    PromptMessageFunction,
    StreamOptions,
    AnyResponseFormat,
    PromptMessageRole,
    UserPromptMessage,
    SystemPromptMessage,
    ToolPromptMessage,
    ThinkingOptions, PromptMessageTool,
)
from .model_entities import ModelUsage, PriceInfo

logger=logging.getLogger(__name__)


class ChatCompletionRequest(BaseModel):
    messages: Optional[list[PromptMessage]] = None
    model: Optional[str] = None
    tools: Optional[list[PromptMessageFunction]] = None
    tool_choice: Optional[
        Union[
            str,dict[str,Any]
        ]
    ] = None  # "none", "auto", "required" or {"type": "function", "function": {"name": "my_function"}}
    stream: bool = None
    stream_options: Optional[StreamOptions] | None = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = Field(
        default=None,
        description="The maximum number of tokens that can be present in a prompt.",
        deprecated="max_tokens is deprecated, use max_completion_tokens instead",
    )
    max_completion_tokens: Optional[int] = Field(
        default=None, description="The maximum number of tokens that can be generated in the completion."
    )
    # n: Optional[int] = 1
    miniP: Optional[float] = None
    # logit_bias: Optional[dict[str, float]] = None
    # logprobs: Optional[bool] = False
    # top_logprobs: Optional[int] = 0
    stop: Optional[Union[str, Sequence[str]]] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    response_format: Optional[AnyResponseFormat] = None
    seed: Optional[int] = None
    user: Optional[str] = None
    reasoning_effort: str = None
    include_reasoning: bool = None
    enable_thinking: bool = None
    thinking_budget: Optional[int] = None
    thinking: Optional[ThinkingOptions] = None
    system: list[dict[str, Any]] = None # for compatibility with anthropic
    stop_sequences: Optional[Union[str, Sequence[str]]] = None # for compatibility with anthropic

    @field_validator("messages", mode="before")
    @classmethod
    def convert_prompt_messages(cls, v):
        if not isinstance(v, list):
            raise ValueError("prompt_messages must be a list")

        for i in range(len(v)):
            i_ = v[i]
            if isinstance(i_, dict):
                if i_["role"] == PromptMessageRole.USER.value:
                    v[i] = UserPromptMessage(**i_)
                elif i_["role"] == PromptMessageRole.ASSISTANT.value:
                    v[i] = AssistantPromptMessage(**i_)
                elif i_["role"] == PromptMessageRole.SYSTEM.value:
                    v[i] = SystemPromptMessage(**i_)
                elif i_["role"] == PromptMessageRole.TOOL.value:
                    v[i] = ToolPromptMessage(**i_)
                else:
                    v[i] = PromptMessage(**i_)
            else:
                v[i] = i_

        return v

    @field_validator("tools", mode="before")
    @classmethod
    def convert_tools(cls, v):
        if not v:
            return v
        if not isinstance(v, list):
            raise ValueError("tools must be a list")
        for i in range(len(v)):
            i_ = v[i]
            if isinstance(i_, dict):
                if "type" in i_:
                    v[i] = PromptMessageFunction(**i_)
                elif 'name' in i_:
                    v[i] = PromptMessageFunction(type='function', function=PromptMessageTool(
                        name=i_['name'],
                        description=i_.get('description', ''),
                        parameters=i_.get('parameters', {}) or i_.get('input_schema', {}),
                        input_schema=i_.get('parameters', {}) or i_.get('input_schema', {}),
                    ))
            else:
                v[i] = i_
        return v

    @model_validator(mode="before")
    @classmethod
    def validate_stream_options(cls, data):
        if data.get("stream_options") and not data.get("stream"):
            raise ValueError("Stream options can only be defined when `stream=True`.")

        return data

    @model_validator(mode="after")
    def change_tool_calls_sequence(self):
        """
        ToolPromptMessage to match assistant.tool_calls order
        - Move ToolPromptMessage entries to follow their AssistantPromptMessage in the exact order
          of assistant.tool_calls ids.
        - Delete tool messages from their original positions.
        - Preserve other messages' order; append unmatched tool messages at the end.
        """
        try:
            msgs = self.messages or []
            if not msgs:
                return self

            from .message_entities import AssistantPromptMessage as _Assistant, ToolPromptMessage as _Tool

            # Build map of tool_call_id -> list of ToolPromptMessage (preserve original relative order per id)
            tool_msg_map: dict[str, list[_Tool]] = {}
            original_tool_msgs: list[_Tool] = []
            for m in msgs:
                if isinstance(m, _Tool) and getattr(m, "tool_call_id", None):
                    tool_msg_map.setdefault(m.tool_call_id, []).append(m)
                    original_tool_msgs.append(m)

            consumed_ids: set[str] = set()
            new_messages: list = []

            for m in msgs:
                # Skip original ToolPromptMessage positions (they will be re-inserted in order later)
                if isinstance(m, _Tool):
                    continue

                # Append non-tool messages as-is
                new_messages.append(m)

                # If assistant, insert its related tool messages in the declared order immediately after
                if isinstance(m, _Assistant) and getattr(m, "tool_calls", None):
                    ordered_ids: list[str] = []
                    for tc in m.tool_calls or []:
                        tc_id = getattr(tc, "id", None)
                        if tc_id:
                            ordered_ids.append(str(tc_id))

                    for tc_id in ordered_ids:
                        if tc_id in consumed_ids:
                            continue
                        if tc_id in tool_msg_map and tool_msg_map[tc_id]:
                            for tm in tool_msg_map[tc_id]:
                                new_messages.append(tm)
                            consumed_ids.add(tc_id)
                            tool_msg_map[tc_id] = []

            # Append any remaining tool messages that were not matched to an assistant (preserve original grouping)
            for id_, tms in tool_msg_map.items():
                for tm in tms:
                    new_messages.append(tm)

            self.messages = new_messages
            #打印消息顺序
            logger.warning("Reordered messages:")
            for i, m in enumerate(self.messages):
                logger.warning(f"  [{i}] {m.role}")
        except Exception:
            logger.exception("Failed to reorder tool calls sequence; keeping original messages order.")
            return self

        return self


class CompletionRequest(BaseModel):
    prompt: Optional[Union[list[int], list[list[int]], str, list[str]]] = None
    prompt_embeds: Optional[Union[bytes, list[bytes]]] = None
    model: Optional[str] = None
    stream: bool = None
    stream_options: Optional[StreamOptions] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = Field(
        default=None,
        description="The maximum number of tokens that can be present in a prompt.",
        deprecated="max_tokens is deprecated, use max_completion_tokens instead",
    )
    max_completion_tokens: Optional[int] = Field(
        default=None, description="The maximum number of tokens that can be generated in the completion."
    )
    n: Optional[int] = 1
    logit_bias: Optional[dict[str, float]] = None
    logprobs: Optional[bool] = False
    top_logprobs: Optional[int] = 0
    stop: Optional[Union[str, Sequence[str]]] = None
    suffix: Optional[str] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    response_format: Optional[AnyResponseFormat] = None
    seed: Optional[int] = None
    user: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def validate_stream_options(cls, data):
        if data.get("stream_options") and not data.get("stream"):
            raise ValueError("Stream options can only be defined when `stream=True`.")

        return data


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
    prompt_unit_price: Decimal = Decimal("0.0")
    prompt_price_unit: Decimal = Decimal("0.0")
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

    index: int=0
    message: AssistantPromptMessage = None
    text: Optional[str] = None
    usage: Optional[LLMUsage] = None
    finish_reason: Optional[str] = None
    delta: Optional[AssistantPromptMessage] = None


class CompletionResponse(BaseModel):
    """
    Model class for llm result.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    done: bool = False


class ChatCompletionResponseChunk(CompletionResponse):
    """
    Model class for llm result chunk.
    """
    id: Optional[str] = None
    object: Optional[str] = None
    created: Optional[int] = None
    model: str = None
    prompt_messages: Union[list[PromptMessage], str] = None
    system_fingerprint: Optional[str] = None
    choices: list[ChatCompletionResponseChunkDelta] = None
    delta: ChatCompletionResponseChunkDelta = None
    usage: Optional[LLMUsage] = None


class ChatCompletionResponse(CompletionResponse):
    """
    Model class for llm result.
    """

    id: Optional[str] = None
    model: str
    prompt_messages: Union[list[PromptMessage], str] = None
    message: AssistantPromptMessage = None
    usage: LLMUsage
    system_fingerprint: Optional[str] = None
    choices: list[ChatCompletionResponseChunkDelta] = None


class ClaudeChatCompletionResponse(CompletionResponse):
    """
    Model class for Claude llm result.
    """

    id: str= None
    type: str= None
    role: str= None
    index:int=0
    prompt_messages: Union[list[PromptMessage], str] = None
    content: list[dict] = None
    delta:Optional[dict[str,Any]] = None
    model: str= None
    stop_reason: Optional[str] = None
    stop_sequence: Optional[str] = None
    usage: Optional[dict[str,Any]] = None
    message: dict[str,Any]= None
    content_block: Optional[dict[str,Any]] = None


class NumTokensResult(PriceInfo):
    """
    Model class for number of tokens result.
    """

    tokens: int
