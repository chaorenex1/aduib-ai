"""
Anthropic Messages API native entity models.
Strongly-typed — zero use of `Any`.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field

from runtime.entities.message_entities import ThinkingOptions

# ── Cache Control ─────────────────────────────────────────────────────────────


class AnthropicCacheControlType(StrEnum):
    EPHEMERAL = "ephemeral"


class AnthropicCacheControl(BaseModel):
    type: AnthropicCacheControlType = AnthropicCacheControlType.EPHEMERAL


# ── Text Block ────────────────────────────────────────────────────────────────


class AnthropicTextBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str = ""
    cache_control: Optional[AnthropicCacheControl] = None


# ── Image Block ───────────────────────────────────────────────────────────────


class AnthropicImageMediaType(StrEnum):
    JPEG = "image/jpeg"
    PNG = "image/png"
    GIF = "image/gif"
    WEBP = "image/webp"


class AnthropicBase64ImageSource(BaseModel):
    type: Literal["base64"] = "base64"
    media_type: AnthropicImageMediaType
    data: str  # base64 string


class AnthropicURLImageSource(BaseModel):
    type: Literal["url"] = "url"
    url: str


AnthropicImageSource = Annotated[
    Union[AnthropicBase64ImageSource, AnthropicURLImageSource],
    Field(discriminator="type"),
]


class AnthropicImageBlock(BaseModel):
    type: Literal["image"] = "image"
    source: AnthropicImageSource
    cache_control: Optional[AnthropicCacheControl] = None


# ── Document Block ────────────────────────────────────────────────────────────


class AnthropicDocumentMediaType(StrEnum):
    PDF = "application/pdf"
    PLAIN_TEXT = "text/plain"


class AnthropicBase64DocumentSource(BaseModel):
    type: Literal["base64"] = "base64"
    media_type: AnthropicDocumentMediaType
    data: str


class AnthropicTextDocumentSource(BaseModel):
    type: Literal["text"] = "text"
    data: str


class AnthropicURLDocumentSource(BaseModel):
    type: Literal["url"] = "url"
    url: str


class AnthropicContentDocumentSource(BaseModel):
    type: Literal["content"] = "content"
    content: list[AnthropicTextBlock]


AnthropicDocumentSource = Annotated[
    Union[
        AnthropicBase64DocumentSource,
        AnthropicTextDocumentSource,
        AnthropicURLDocumentSource,
        AnthropicContentDocumentSource,
    ],
    Field(discriminator="type"),
]


class AnthropicDocumentBlock(BaseModel):
    type: Literal["document"] = "document"
    source: AnthropicDocumentSource
    title: Optional[str] = None
    context: Optional[str] = None
    cache_control: Optional[AnthropicCacheControl] = None


# ── Thinking Blocks ───────────────────────────────────────────────────────────


class AnthropicThinkingBlock(BaseModel):
    type: Literal["thinking"] = "thinking"
    thinking: str = ""
    signature: str = ""


class AnthropicRedactedThinkingBlock(BaseModel):
    type: Literal["redacted_thinking"] = "redacted_thinking"
    data: str = ""


# ── Tool Blocks ───────────────────────────────────────────────────────────────


class AnthropicToolUseBlock(BaseModel):
    type: Literal["tool_use"] = "tool_use"
    id: str = ""
    name: str = ""
    input: dict[str, object] = Field(default_factory=dict)


class AnthropicToolResultBlock(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str = ""
    content: Union[str, list[AnthropicTextBlock]] = ""
    is_error: bool = False


class AnthropicServerToolUseBlock(BaseModel):
    """Server-side built-in tool use block (e.g. web_search)."""

    type: Literal["server_tool_use"] = "server_tool_use"
    id: str = ""
    name: str = ""
    input: dict[str, object] = Field(default_factory=dict)


class AnthropicSearchResultBlock(BaseModel):
    """Search result returned by web_search built-in tool."""

    type: Literal["search_result"] = "search_result"
    source: str = ""
    title: str = ""
    content: list[AnthropicTextBlock] = Field(default_factory=list)


# ── Content Block Union ───────────────────────────────────────────────────────

AnthropicContentBlock = Annotated[
    Union[
        AnthropicTextBlock,
        AnthropicImageBlock,
        AnthropicDocumentBlock,
        AnthropicThinkingBlock,
        AnthropicRedactedThinkingBlock,
        AnthropicToolUseBlock,
        AnthropicToolResultBlock,
        AnthropicServerToolUseBlock,
        AnthropicSearchResultBlock,
    ],
    Field(discriminator="type"),
]


# ── Message ───────────────────────────────────────────────────────────────────


class AnthropicMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: Union[str, list[AnthropicContentBlock]]


# ── Tool Definition ───────────────────────────────────────────────────────────


class AnthropicTool(BaseModel):
    name: str
    description: Optional[str] = None
    input_schema: dict[str, object] = Field(default_factory=dict)
    type: Optional[str] = None


class AnthropicToolChoiceType(StrEnum):
    AUTO = "auto"
    ANY = "any"
    TOOL = "tool"
    NONE = "none"


class AnthropicToolChoice(BaseModel):
    type: AnthropicToolChoiceType = AnthropicToolChoiceType.AUTO
    name: Optional[str] = None
    disable_parallel_tool_use: Optional[bool] = None


# ── System Block ──────────────────────────────────────────────────────────────


class AnthropicSystemBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str
    cache_control: Optional[AnthropicCacheControl] = None


# ── Metadata ──────────────────────────────────────────────────────────────────


class AnthropicMetadata(BaseModel):
    user_id: Optional[str] = None


class AnthropicOutputConfig(BaseModel):
    effort: Optional[str] = None


# ── Request ───────────────────────────────────────────────────────────────────


class AnthropicMessageRequest(BaseModel):
    """Native Anthropic Messages API request."""

    model: str
    messages: list[AnthropicMessage]
    system: Optional[Union[str, list[AnthropicSystemBlock]]] = None
    tools: Optional[list[AnthropicTool]] = None
    tool_choice: Optional[Union[str, AnthropicToolChoice]] = None
    max_tokens: int = 4096
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    stream: bool = False
    stop_sequences: Optional[list[str]] = None
    thinking: Optional[ThinkingOptions] = None
    output_config: Optional[AnthropicOutputConfig] = None
    metadata: Optional[AnthropicMetadata] = None


# ── Usage ─────────────────────────────────────────────────────────────────────


class AnthropicServerToolUseUsage(BaseModel):
    web_search_requests: Optional[int] = None


class AnthropicUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: Optional[int] = None
    cache_read_input_tokens: Optional[int] = None
    server_tool_use: Optional[AnthropicServerToolUseUsage] = None


# ── Non-streaming Response ────────────────────────────────────────────────────


class AnthropicStopReason(StrEnum):
    END_TURN = "end_turn"
    MAX_TOKENS = "max_tokens"
    STOP_SEQUENCE = "stop_sequence"
    TOOL_USE = "tool_use"
    PAUSE_TURN = "pause_turn"


class AnthropicMessageResponse(BaseModel):
    """Strongly-typed Anthropic Messages API response."""

    id: str = ""
    type: Literal["message"] = "message"
    role: Literal["assistant"] = "assistant"
    content: list[AnthropicContentBlock] = Field(default_factory=list)
    model: str = ""
    stop_reason: Optional[AnthropicStopReason] = None
    stop_sequence: Optional[str] = None
    usage: AnthropicUsage = Field(default_factory=AnthropicUsage)


# ── Streaming SSE Events ──────────────────────────────────────────────────────


class AnthropicStreamEvent(BaseModel):
    """Base streaming event."""

    type: str
    id: Optional[str] = None
    model: Optional[str] = None
    role: Optional[str] = None
    done: bool = False


class AnthropicMessageStartMessage(BaseModel):
    """The initial message object inside message_start event."""

    id: str = ""
    type: str = "message"
    role: str = "assistant"
    content: list[object] = Field(default_factory=list)
    model: str = ""
    stop_reason: Optional[str] = None
    stop_sequence: Optional[str] = None
    usage: Optional[AnthropicUsage] = None


class AnthropicMessageStartEvent(AnthropicStreamEvent):
    type: Literal["message_start"] = "message_start"
    message: AnthropicMessageStartMessage = Field(default_factory=AnthropicMessageStartMessage)


class AnthropicPingEvent(AnthropicStreamEvent):
    type: Literal["ping"] = "ping"


class AnthropicStreamContentBlock(BaseModel):
    """Initial (empty) content block sent in content_block_start."""

    type: str
    id: Optional[str] = None
    name: Optional[str] = None
    input: Optional[dict[str, object]] = None
    text: Optional[str] = None
    thinking: Optional[str] = None
    signature: Optional[str] = None
    data: Optional[str] = None


class AnthropicContentBlockStartEvent(AnthropicStreamEvent):
    type: Literal["content_block_start"] = "content_block_start"
    index: int = 0
    content_block: AnthropicStreamContentBlock = Field(default_factory=lambda: AnthropicStreamContentBlock(type="text"))


class AnthropicStreamDeltaType(StrEnum):
    TEXT_DELTA = "text_delta"
    INPUT_JSON_DELTA = "input_json_delta"
    THINKING_DELTA = "thinking_delta"
    SIGNATURE_DELTA = "signature_delta"


class AnthropicStreamDelta(BaseModel):
    """Delta payload inside content_block_delta event."""

    type: AnthropicStreamDeltaType
    text: Optional[str] = None
    partial_json: Optional[str] = None
    thinking: Optional[str] = None
    signature: Optional[str] = None


class AnthropicContentBlockDeltaEvent(AnthropicStreamEvent):
    type: Literal["content_block_delta"] = "content_block_delta"
    index: int = 0
    delta: AnthropicStreamDelta = Field(
        default_factory=lambda: AnthropicStreamDelta(type=AnthropicStreamDeltaType.TEXT_DELTA)
    )


class AnthropicContentBlockStopEvent(AnthropicStreamEvent):
    type: Literal["content_block_stop"] = "content_block_stop"
    index: int = 0


class AnthropicMessageDelta(BaseModel):
    """Delta payload inside message_delta event."""

    stop_reason: Optional[AnthropicStopReason] = None
    stop_sequence: Optional[str] = None


class AnthropicMessageDeltaEvent(AnthropicStreamEvent):
    type: Literal["message_delta"] = "message_delta"
    delta: AnthropicMessageDelta = Field(default_factory=AnthropicMessageDelta)
    usage: AnthropicUsage = Field(default_factory=AnthropicUsage)


class AnthropicMessageStopEvent(AnthropicStreamEvent):
    type: Literal["message_stop"] = "message_stop"


ANTHROPIC_SSE_EVENT_TYPES: dict[str, type[AnthropicStreamEvent]] = {
    "message_start": AnthropicMessageStartEvent,
    "ping": AnthropicPingEvent,
    "content_block_start": AnthropicContentBlockStartEvent,
    "content_block_delta": AnthropicContentBlockDeltaEvent,
    "content_block_stop": AnthropicContentBlockStopEvent,
    "message_delta": AnthropicMessageDeltaEvent,
    "message_stop": AnthropicMessageStopEvent,
}


def parse_sse_event(data: dict[str, object]) -> AnthropicStreamEvent:
    """Deserialize a raw SSE data dict into a typed AnthropicStreamEvent."""
    event_type = data.get("type", "")
    cls = ANTHROPIC_SSE_EVENT_TYPES.get(str(event_type), AnthropicStreamEvent)
    return cls(**data)
