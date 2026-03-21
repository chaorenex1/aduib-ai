"""
OpenAI Responses API entity models — zero use of `Any`.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field

from .llm_entities import LLMUsage

# ── Input Content Types ───────────────────────────────────────────────────────


class ResponseInputContentType(StrEnum):
    TEXT = "text"
    IMAGE_URL = "image_url"
    INPUT_AUDIO = "input_audio"
    INPUT_FILE = "input_file"


class ImageURL(BaseModel):
    url: str
    detail: Optional[str] = "auto"


class InputAudio(BaseModel):
    id: str
    data: str  # base64 encoded


class InputFile(BaseModel):
    id: str
    data: str  # base64 encoded


class TextContentBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str = ""


class ImageURLContentBlock(BaseModel):
    type: Literal["image_url"] = "image_url"
    image_url: ImageURL


class InputAudioContentBlock(BaseModel):
    type: Literal["input_audio"] = "input_audio"
    input_audio: InputAudio


class InputFileContentBlock(BaseModel):
    type: Literal["input_file"] = "input_file"
    input_file: InputFile


class ResponseInputItem(BaseModel):
    role: str  # "user", "assistant"
    content: Union[str, list[ContentBlockItem]]


# ── Tool Definition ───────────────────────────────────────────────────────────


class ResponseFunctionTool(BaseModel):
    type: str = "function"
    name: str
    description: Optional[str] = ""
    parameters: Optional[dict[str, object]] = Field(default_factory=dict)


class ResponseToolChoice(BaseModel):
    type: str = "function"
    function: str


# ── Text Format ───────────────────────────────────────────────────────────────


class ResponseTextFormatType(StrEnum):
    TEXT = "text"
    JSON_SCHEMA = "json_schema"
    JSON_OBJECT = "json_object"


class ResponseTextFormat(BaseModel):
    type: ResponseTextFormatType = ResponseTextFormatType.TEXT
    json_schema: Optional[dict[str, object]] = None


class ResponseTextConfig(BaseModel):
    format: Optional[ResponseTextFormat] = None


# ── Request ───────────────────────────────────────────────────────────────────


class ResponseRequest(BaseModel):
    model: str
    input: Union[str, list[ResponseInputItem]]
    instructions: Optional[str] = None  # system prompt top-level field
    tools: Optional[list[ResponseFunctionTool]] = None
    tool_choice: Optional[Union[str, ResponseToolChoice]] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    max_completion_tokens: Optional[int] = None
    stream: bool = False
    top_p: Optional[float] = None
    stop: Optional[Union[str, list[str]]] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    user: Optional[str] = None
    text: Optional[ResponseTextConfig] = None
    response_format: Optional[dict[str, object]] = None  # backward compat
    previous_response_id: Optional[str] = None
    store: Optional[bool] = True


# ── Output Item Types ─────────────────────────────────────────────────────────


class ResponseOutputStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    INCOMPLETE = "incomplete"


class ResponseToolCall(BaseModel):
    id: str
    type: str = "function"
    function: dict[str, str]  # {name: str, arguments: str}


class ResponseOutputMessage(BaseModel):
    type: Literal["message"] = "message"
    id: str = ""
    status: ResponseOutputStatus = ResponseOutputStatus.COMPLETED
    role: str = "assistant"
    content: list[ContentBlockItem] = Field(default_factory=list)
    tool_calls: Optional[list[ResponseToolCall]] = None


class ResponseOutputFunctionCall(BaseModel):
    type: Literal["function_call"] = "function_call"
    id: str = ""
    status: ResponseOutputStatus = ResponseOutputStatus.COMPLETED
    call_id: str = ""
    name: str = ""
    arguments: str = ""


class ResponseOutputFunctionCallOutput(BaseModel):
    type: Literal["function_call_output"] = "function_call_output"
    id: str = ""
    status: ResponseOutputStatus = ResponseOutputStatus.COMPLETED
    call_id: str = ""
    output: str = ""


class ResponseReasoningSummary(BaseModel):
    type: Literal["summary_text"] = "summary_text"
    text: str = ""


class ResponseOutputReasoning(BaseModel):
    type: Literal["reasoning"] = "reasoning"
    id: str = ""
    status: ResponseOutputStatus = ResponseOutputStatus.COMPLETED
    summary: list[ResponseReasoningSummary] = Field(default_factory=list)


class ResponseOutputImage(BaseModel):
    type: Literal["image"] = "image"
    id: str = ""
    status: ResponseOutputStatus = ResponseOutputStatus.COMPLETED
    image_url: Optional[ImageURL] = None


class ResponseOutputAudio(BaseModel):
    type: Literal["audio"] = "audio"
    id: str = ""
    status: ResponseOutputStatus = ResponseOutputStatus.COMPLETED
    data: str = ""  # base64 audio
    transcript: Optional[str] = None


class ResponseOutputFile(BaseModel):
    type: Literal["file"] = "file"
    id: str = ""
    status: ResponseOutputStatus = ResponseOutputStatus.COMPLETED
    file_id: str = ""


class ResponseComputerAction(BaseModel):
    type: str
    coordinate: Optional[list[int]] = None
    text: Optional[str] = None


class ResponseOutputComputerCall(BaseModel):
    type: Literal["computer_call"] = "computer_call"
    id: str = ""
    status: ResponseOutputStatus = ResponseOutputStatus.COMPLETED
    call_id: str = ""
    action: Optional[ResponseComputerAction] = None


class ResponseOutputComputerCallOutput(BaseModel):
    type: Literal["computer_call_output"] = "computer_call_output"
    id: str = ""
    status: ResponseOutputStatus = ResponseOutputStatus.COMPLETED
    call_id: str = ""
    output: str = ""


ContentBlockItem = Annotated[
    Union[
        TextContentBlock,
        ImageURLContentBlock,
        InputAudioContentBlock,
        InputFileContentBlock,
        ResponseOutputFunctionCallOutput,
    ],
    Field(discriminator="type"),
]

ResponseOutputItem = Annotated[
    Union[
        ResponseOutputMessage,
        ResponseOutputFunctionCall,
        ResponseOutputFunctionCallOutput,
        ResponseOutputReasoning,
        ResponseOutputImage,
        ResponseOutputAudio,
        ResponseOutputFile,
        ResponseOutputComputerCall,
        ResponseOutputComputerCallOutput,
    ],
    Field(discriminator="type"),
]


# ── Response Output ───────────────────────────────────────────────────────────


class ResponseStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    IN_PROGRESS = "in_progress"
    INCOMPLETE = "incomplete"
    CANCELLED = "cancelled"


class ResponseError(BaseModel):
    code: str
    message: str


class ResponseOutput(BaseModel):
    id: str
    object: str = "response"
    created: int
    model: str
    output: list[ResponseOutputItem]
    usage: LLMUsage
    status: ResponseStatus = ResponseStatus.COMPLETED
    error: Optional[ResponseError] = None
    instructions: Optional[str] = None


# ── SSE Streaming Events (14 types) ──────────────────────────────────────────


class ResponseStreamEvent(BaseModel):
    """Base SSE event for Responses API."""

    type: str


class ResponseCreatedEvent(ResponseStreamEvent):
    type: Literal["response.created"] = "response.created"
    response: ResponseOutput


class ResponseInProgressEvent(ResponseStreamEvent):
    type: Literal["response.in_progress"] = "response.in_progress"
    response: ResponseOutput


class ResponseOutputItemAddedEvent(ResponseStreamEvent):
    type: Literal["response.output_item.added"] = "response.output_item.added"
    output_index: int
    item: ResponseOutputItem


class ResponseOutputItemDoneEvent(ResponseStreamEvent):
    type: Literal["response.output_item.done"] = "response.output_item.done"
    output_index: int
    item: ResponseOutputItem


class ResponseContentPartAddedEvent(ResponseStreamEvent):
    type: Literal["response.content_part.added"] = "response.content_part.added"
    item_id: str
    output_index: int
    content_index: int
    part: ContentBlockItem


class ResponseContentPartDoneEvent(ResponseStreamEvent):
    type: Literal["response.content_part.done"] = "response.content_part.done"
    item_id: str
    output_index: int
    content_index: int
    part: ContentBlockItem


class ResponseTextDeltaEvent(ResponseStreamEvent):
    type: Literal["response.text.delta"] = "response.text.delta"
    item_id: str
    output_index: int
    content_index: int
    delta: str


class ResponseTextDoneEvent(ResponseStreamEvent):
    type: Literal["response.text.done"] = "response.text.done"
    item_id: str
    output_index: int
    content_index: int
    text: str


class ResponseRefusalDeltaEvent(ResponseStreamEvent):
    type: Literal["response.refusal.delta"] = "response.refusal.delta"
    item_id: str
    output_index: int
    content_index: int
    delta: str


class ResponseRefusalDoneEvent(ResponseStreamEvent):
    type: Literal["response.refusal.done"] = "response.refusal.done"
    item_id: str
    output_index: int
    content_index: int
    refusal: str


class ResponseFunctionCallArgumentsDeltaEvent(ResponseStreamEvent):
    type: Literal["response.function_call_arguments.delta"] = "response.function_call_arguments.delta"
    item_id: str
    output_index: int
    delta: str


class ResponseFunctionCallArgumentsDoneEvent(ResponseStreamEvent):
    type: Literal["response.function_call_arguments.done"] = "response.function_call_arguments.done"
    item_id: str
    output_index: int
    arguments: str


class RateLimit(BaseModel):
    name: str
    limit: int
    remaining: int
    reset_seconds: float


class ResponseRateLimitsUpdatedEvent(ResponseStreamEvent):
    type: Literal["response.rate_limits_updated"] = "response.rate_limits_updated"
    rate_limits: list[RateLimit] = Field(default_factory=list)


class ResponseErrorEvent(ResponseStreamEvent):
    type: Literal["error"] = "error"
    code: str
    message: str
    param: Optional[str] = None


class ResponseDoneEvent(ResponseStreamEvent):
    type: Literal["response.done"] = "response.done"
    response: ResponseOutput


# Backward-compatible aliases
ResponseStreamDelta = ResponseOutputItemAddedEvent
ResponseStreamContent = ResponseTextDeltaEvent
ResponseStreamDone = ResponseDoneEvent


RESPONSE_SSE_EVENT_TYPES: dict[str, type[ResponseStreamEvent]] = {
    "response.created": ResponseCreatedEvent,
    "response.in_progress": ResponseInProgressEvent,
    "response.output_item.added": ResponseOutputItemAddedEvent,
    "response.output_item.done": ResponseOutputItemDoneEvent,
    "response.content_part.added": ResponseContentPartAddedEvent,
    "response.content_part.done": ResponseContentPartDoneEvent,
    "response.text.delta": ResponseTextDeltaEvent,
    "response.text.done": ResponseTextDoneEvent,
    "response.refusal.delta": ResponseRefusalDeltaEvent,
    "response.refusal.done": ResponseRefusalDoneEvent,
    "response.function_call_arguments.delta": ResponseFunctionCallArgumentsDeltaEvent,
    "response.function_call_arguments.done": ResponseFunctionCallArgumentsDoneEvent,
    "response.rate_limits_updated": ResponseRateLimitsUpdatedEvent,
    "error": ResponseErrorEvent,
    "response.done": ResponseDoneEvent,
}


def parse_response_sse_event(data: dict[str, object]) -> ResponseStreamEvent:
    """Deserialize a raw SSE data dict into a typed ResponseStreamEvent."""
    event_type = data.get("type", "")
    cls = RESPONSE_SSE_EVENT_TYPES.get(str(event_type), ResponseStreamEvent)
    return cls(**data)
