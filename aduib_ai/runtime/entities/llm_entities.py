from decimal import Decimal
from enum import StrEnum
from typing import Optional, Union, Literal, Sequence

from pydantic import BaseModel, Field, field_validator, model_validator

from .message_entities import PromptMessage, AssistantPromptMessage, PromptMessageFunction, \
    PromptMessageToolChoiceParam, StreamOptions, AnyResponseFormat, PromptMessageRole, UserPromptMessage, \
    SystemPromptMessage, ToolPromptMessage
from .model_entities import ModelUsage, PriceInfo


class ChatCompletionRequest(BaseModel):
    messages: Optional[list[PromptMessage]] = None
    model: Optional[str] = None
    tools: Optional[list[PromptMessageFunction]] = None
    tool_choice: Optional[Union[
        Literal["none"],
        Literal["auto"],
        Literal["required"],
        PromptMessageToolChoiceParam,
    ]] = "none"
    stream: bool = None
    stream_options: Optional[StreamOptions] | None = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = Field(
        default=None,
        description="The maximum number of tokens that can be present in a prompt.",
        deprecated="max_tokens is deprecated, use max_completion_tokens instead"
    )
    max_completion_tokens: Optional[int] = Field(
        default=None,
        description="The maximum number of tokens that can be generated in the completion."
    )
    n: Optional[int] = 1
    miniP: Optional[float] = None
    logit_bias: Optional[dict[str, float]] = None
    logprobs: Optional[bool] = False
    top_logprobs: Optional[int] = 0
    stop: Optional[Union[str, Sequence[str]]] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    response_format: Optional[AnyResponseFormat] = None
    seed: Optional[int] = None
    user: Optional[str] = None
    reasoning_effort: Optional[Literal["low", "medium", "high"]] = None
    include_reasoning: bool = None
    thinking: bool = None

    @field_validator("messages", mode="before")
    @classmethod
    def convert_prompt_messages(cls, v):
        if not isinstance(v, list):
            raise ValueError("prompt_messages must be a list")

        for i in range(len(v)):
            if v[i]["role"] == PromptMessageRole.USER.value:
                v[i] = UserPromptMessage(**v[i])
            elif v[i]["role"] == PromptMessageRole.ASSISTANT.value:
                v[i] = AssistantPromptMessage(**v[i])
            elif v[i]["role"] == PromptMessageRole.SYSTEM.value:
                v[i] = SystemPromptMessage(**v[i])
            elif v[i]["role"] == PromptMessageRole.TOOL.value:
                v[i] = ToolPromptMessage(**v[i])
            else:
                v[i] = PromptMessage(**v[i])

        return v

    @model_validator(mode="before")
    @classmethod
    def validate_stream_options(cls, data):
        if data.get("stream_options") and not data.get("stream"):
            raise ValueError(
                "Stream options can only be defined when `stream=True`.")

        return data

    @model_validator(mode="before")
    @classmethod
    def check_tool_usage(cls, data):

        # if "tool_choice" is not specified but tools are provided,
        # default to "auto" tool_choice
        if "tool_choice" not in data and data.get("tools"):
            data["tool_choice"] = "auto"

        # if "tool_choice" is "none" -- no validation is needed for tools
        if "tool_choice" in data and data["tool_choice"] == "none":
            return data

        # if "tool_choice" is specified -- validation
        if "tool_choice" in data and data["tool_choice"] is not None:

            # ensure that if "tool choice" is specified, tools are present
            if "tools" not in data or data["tools"] is None:
                raise ValueError(
                    "When using `tool_choice`, `tools` must be set.")

            # make sure that tool choice is either a named tool
            # OR that it's set to "auto" or "required"
            if data["tool_choice"] not in [
                "auto", "required"
            ] and not isinstance(data["tool_choice"], dict):
                raise ValueError(
                    f'Invalid value for `tool_choice`: {data["tool_choice"]}! ' \
                    'Only named tools, "none", "auto" or "required" ' \
                    'are supported.'
                )

            # if tool_choice is "required" but the "tools" list is empty,
            # override the data to behave like "none" to align with
            # OpenAI’s behavior.
            if data["tool_choice"] == "required" and isinstance(
                    data["tools"], list) and len(data["tools"]) == 0:
                data["tool_choice"] = "none"
                del data["tools"]
                return data

            # ensure that if "tool_choice" is specified as an object,
            # it matches a valid tool
            correct_usage_message = 'Correct usage: `{"type": "function",' \
                                    ' "function": {"name": "my_function"}}`'
            if isinstance(data["tool_choice"], dict):
                valid_tool = False
                function = data["tool_choice"].get("function")
                if not isinstance(function, dict):
                    raise ValueError(
                        f"Invalid value for `function`: `{function}` in "
                        f"`tool_choice`! {correct_usage_message}")
                if "name" not in function:
                    raise ValueError(f"Expected field `name` in `function` in "
                                     f"`tool_choice`! {correct_usage_message}")
                function_name = function["name"]
                if not isinstance(function_name,
                                  str) or len(function_name) == 0:
                    raise ValueError(
                        f"Invalid `name` in `function`: `{function_name}`"
                        f" in `tool_choice`! {correct_usage_message}")
                for tool in data["tools"]:
                    if tool["function"]["name"] == function_name:
                        valid_tool = True
                        break
                if not valid_tool:
                    raise ValueError(
                        "The tool specified in `tool_choice` does not match any"
                        " of the specified `tools`")
        return data


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
        deprecated="max_tokens is deprecated, use max_completion_tokens instead"
    )
    max_completion_tokens: Optional[int] = Field(
        default=None,
        description="The maximum number of tokens that can be generated in the completion."
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
            raise ValueError(
                "Stream options can only be defined when `stream=True`.")

        return data

    @model_validator(mode="before")
    @classmethod
    def check_tool_usage(cls, data):

        # if "tool_choice" is not specified but tools are provided,
        # default to "auto" tool_choice
        if "tool_choice" not in data and data.get("tools"):
            data["tool_choice"] = "auto"

        # if "tool_choice" is "none" -- no validation is needed for tools
        if "tool_choice" in data and data["tool_choice"] == "none":
            return data

        # if "tool_choice" is specified -- validation
        if "tool_choice" in data and data["tool_choice"] is not None:

            # ensure that if "tool choice" is specified, tools are present
            if "tools" not in data or data["tools"] is None:
                raise ValueError(
                    "When using `tool_choice`, `tools` must be set.")

            # make sure that tool choice is either a named tool
            # OR that it's set to "auto" or "required"
            if data["tool_choice"] not in [
                "auto", "required"
            ] and not isinstance(data["tool_choice"], dict):
                raise ValueError(
                    f'Invalid value for `tool_choice`: {data["tool_choice"]}! ' \
                    'Only named tools, "none", "auto" or "required" ' \
                    'are supported.'
                )

            # if tool_choice is "required" but the "tools" list is empty,
            # override the data to behave like "none" to align with
            # OpenAI’s behavior.
            if data["tool_choice"] == "required" and isinstance(
                    data["tools"], list) and len(data["tools"]) == 0:
                data["tool_choice"] = "none"
                del data["tools"]
                return data

            # ensure that if "tool_choice" is specified as an object,
            # it matches a valid tool
            correct_usage_message = 'Correct usage: `{"type": "function",' \
                                    ' "function": {"name": "my_function"}}`'
            if isinstance(data["tool_choice"], dict):
                valid_tool = False
                function = data["tool_choice"].get("function")
                if not isinstance(function, dict):
                    raise ValueError(
                        f"Invalid value for `function`: `{function}` in "
                        f"`tool_choice`! {correct_usage_message}")
                if "name" not in function:
                    raise ValueError(f"Expected field `name` in `function` in "
                                     f"`tool_choice`! {correct_usage_message}")
                function_name = function["name"]
                if not isinstance(function_name,
                                  str) or len(function_name) == 0:
                    raise ValueError(
                        f"Invalid `name` in `function`: `{function_name}`"
                        f" in `tool_choice`! {correct_usage_message}")
                for tool in data["tools"]:
                    if tool["function"]["name"] == function_name:
                        valid_tool = True
                        break
                if not valid_tool:
                    raise ValueError(
                        "The tool specified in `tool_choice` does not match any"
                        " of the specified `tools`")
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

    index: int
    message: AssistantPromptMessage = None
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
    model: str = None
    prompt_messages: Union[list[PromptMessage], str] = None
    system_fingerprint: Optional[str] = None
    choices: list[ChatCompletionResponseChunkDelta] = None
    delta: ChatCompletionResponseChunkDelta = None
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
