from abc import ABC
from enum import StrEnum, Enum
from typing import Optional, Sequence, Annotated, Union, Literal, Any, Mapping

from pydantic import BaseModel, Field, field_validator


class StreamOptions(BaseModel):
    include_usage: Optional[bool] = True
    continuous_usage_stats: Optional[bool] = False


class JsonSchemaResponseFormat(BaseModel):
    name: str
    description: Optional[str] = None
    # schema is the field in openai but that causes conflicts with pydantic so
    # instead use json_schema with an alias
    json_schema: Optional[dict[str, Any]] = Field(default=None, alias="schema")
    strict: Optional[bool] = None


class StructuralTag(BaseModel):
    begin: str
    # schema is the field, but that causes conflicts with pydantic so
    # instead use structural_tag_schema with an alias
    structural_tag_schema: Optional[dict[str, Any]] = Field(default=None, alias="schema")
    end: str


class StructuralTagResponseFormat(BaseModel):
    type: Literal["structural_tag"]
    structures: list[StructuralTag]
    triggers: list[str]


class ResponseFormat(BaseModel):
    # type must be "json_schema", "json_object", or "text"
    type: Literal["text", "json_object", "json_schema"]
    json_schema: Optional[JsonSchemaResponseFormat] = None


AnyResponseFormat = Union[ResponseFormat, StructuralTagResponseFormat]


class ThinkingOptions(BaseModel):
    type: Optional[str] = None
    budget_tokens: Optional[int] = None


class PromptMessageRole(Enum):
    """
    Enum class for prompt message.
    """

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

    @classmethod
    def value_of(cls, value: str) -> "PromptMessageRole":
        """
        Get value of given mode.

        :param value: mode value
        :return: mode
        """
        for mode in cls:
            if mode.value == value:
                return mode
        raise ValueError(f"invalid prompt message type value {value}")


class PromptMessageTool(BaseModel):
    """
    Model class for prompt message tool.
    """

    name: str
    description: str
    parameters: dict
    input_schema: Optional[dict] = None  # openai specific

class PromptMessageFunction(BaseModel):
    """
    Model class for prompt message function.
    """

    type: str = "function"
    function: PromptMessageTool=None
    name: str=Field(default=None, description="the name of function") # anthropic specific
    max_usage: Optional[int] = Field(default=None, description="the max usage of function") # anthropic specific


class PromptMessageNamedFunction(BaseModel):
    name: str


class PromptMessageToolChoiceParam(BaseModel):
    function: PromptMessageNamedFunction
    type: Literal["function"] = "function"
    name: str=Field(default=None, description="the name of tool choice param")


class PromptMessageContentType(StrEnum):
    """
    Enum class for prompt message content type.
    """

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    # claude specific
    CLAUDE_THINKING = "thinking"
    CLAUDE_REDACTED_TEXT = "redacted_thinking"
    CLAUDE_TOOL_USE = "tool_use"
    CLAUDE_TOOL_RESULT = "tool_result"
    CLAUDE_MCP_USER = "mcp_use"
    CLAUDE_MCP_RESULT = "mcp_result"


class PromptMessageContent(BaseModel):
    """
    Model class for prompt message content.
    """

    type: PromptMessageContentType


class TextPromptMessageContent(PromptMessageContent):
    """
    Model class for text prompt message content.
    """

    type: Literal[PromptMessageContentType.TEXT] = PromptMessageContentType.TEXT
    data: str = Field(default="", description="the text content of prompt message")
    text: str = Field(default="", description="the text content of prompt message")


class MultiModalPromptMessageContent(PromptMessageContent):
    """
    Model class for multi-modal prompt message content.
    """

    type: PromptMessageContentType
    format: str = Field(default=..., description="the format of multi-modal file")
    base64_data: str = Field(default="", description="the base64 data of multi-modal file")
    url: str = Field(default="", description="the url of multi-modal file")
    mime_type: str = Field(default=..., description="the mime type of multi-modal file")

    @property
    def data(self):
        return self.url or f"data:{self.mime_type};base64,{self.base64_data}"


class VideoPromptMessageContent(MultiModalPromptMessageContent):
    type: Literal[PromptMessageContentType.VIDEO] = PromptMessageContentType.VIDEO


class AudioPromptMessageContent(MultiModalPromptMessageContent):
    type: Literal[PromptMessageContentType.AUDIO] = PromptMessageContentType.AUDIO


class ImagePromptMessageContent(MultiModalPromptMessageContent):
    """
    Model class for image prompt message content.
    """

    class DETAIL(StrEnum):
        LOW = "low"
        HIGH = "high"

    type: Literal[PromptMessageContentType.IMAGE] = PromptMessageContentType.IMAGE
    detail: DETAIL = DETAIL.LOW


class DocumentPromptMessageContent(MultiModalPromptMessageContent):
    type: Literal[PromptMessageContentType.DOCUMENT] = PromptMessageContentType.DOCUMENT


class ClaudeTextPromptMessageContent(PromptMessageContent):
    """
    Model class for text prompt message content.
    """

    type: Literal[PromptMessageContentType.TEXT] = PromptMessageContentType.TEXT
    data: str = Field(default="", description="the text content of prompt message")
    text: str = Field(default="", description="the text content of prompt message")

class ClaudeThinkingPromptMessageContent(PromptMessageContent):
    type: Literal[PromptMessageContentType.CLAUDE_THINKING] = PromptMessageContentType.CLAUDE_THINKING
    thinking: Union[str,list[dict[str,Any]]] = Field(default="", description="the thinking content of prompt message")
    signature: str = Field(default="", description="the signature of thinking content of prompt message")

class ClaudeRedactedTextPromptMessageContent(PromptMessageContent):
    type: Literal[PromptMessageContentType.CLAUDE_REDACTED_TEXT] = PromptMessageContentType.CLAUDE_REDACTED_TEXT
    data: str = Field(default="", description="the text content of prompt message")

class ClaudeToolUsePromptMessageContent(PromptMessageContent):
    type: Literal[PromptMessageContentType.CLAUDE_TOOL_USE] = PromptMessageContentType.CLAUDE_TOOL_USE
    id: str = Field(default="", description="the id of tool use content of prompt message")
    input: dict[str, Any] = Field(default={}, description="the input of tool use content of prompt message")
    name: Optional[str] = Field(default=None, description="the name of tool use content of prompt message")

class ClaudeToolResultPromptMessageContent(PromptMessageContent):
    type: Literal[PromptMessageContentType.CLAUDE_TOOL_RESULT] = PromptMessageContentType.CLAUDE_TOOL_RESULT
    tool_use_id: str = Field(default="", description="the tool use id of tool result content of prompt message")
    content: Union[str,list[dict[str,Any]]] = Field(default="", description="the content of tool result content of prompt message")
    is_error: Optional[bool] = Field(default=False, description="whether the tool result content is error")

class ClaudeMCPUserPromptMessageContent(PromptMessageContent):
    type: Literal[PromptMessageContentType.CLAUDE_MCP_USER] = PromptMessageContentType.CLAUDE_MCP_USER
    id: str = Field(default="", description="the id of mcp user content of prompt message")
    input: dict[str, Any] = Field(default={}, description="the input of mcp user content of prompt message")
    name: Optional[str] = Field(default=None, description="the name of mcp user content of prompt message")
    server_name: Optional[str] = Field(default=None, description="the server name of mcp user content of prompt message")


class ClaudeMCPResultPromptMessageContent(PromptMessageContent):
    type: Literal[PromptMessageContentType.CLAUDE_MCP_RESULT] = PromptMessageContentType.CLAUDE_MCP_RESULT
    mcp_user_id: str = Field(default="", description="the mcp user id of mcp result content of prompt message")
    content: Union[str,list[dict[str,Any]]] = Field(default="", description="the content of mcp result content of prompt message")
    is_error: Optional[bool] = Field(default=False, description="whether the mcp result content is error")


PromptMessageContentUnionTypes = Annotated[
    Union[
        TextPromptMessageContent,
        ImagePromptMessageContent,
        DocumentPromptMessageContent,
        AudioPromptMessageContent,
        VideoPromptMessageContent,
        ClaudeThinkingPromptMessageContent,
        ClaudeRedactedTextPromptMessageContent,
        ClaudeToolUsePromptMessageContent,
        ClaudeToolResultPromptMessageContent,
        ClaudeMCPUserPromptMessageContent,
        ClaudeMCPResultPromptMessageContent,
    ],
    Field(discriminator="type"),
]

CONTENT_TYPE_MAPPING: Mapping[PromptMessageContentType, type[PromptMessageContent]] = {
    PromptMessageContentType.TEXT: TextPromptMessageContent,
    PromptMessageContentType.IMAGE: ImagePromptMessageContent,
    PromptMessageContentType.AUDIO: AudioPromptMessageContent,
    PromptMessageContentType.VIDEO: VideoPromptMessageContent,
    PromptMessageContentType.DOCUMENT: DocumentPromptMessageContent,
    PromptMessageContentType.CLAUDE_THINKING: ClaudeThinkingPromptMessageContent,
    PromptMessageContentType.CLAUDE_REDACTED_TEXT: ClaudeRedactedTextPromptMessageContent,
    PromptMessageContentType.CLAUDE_TOOL_USE: ClaudeToolUsePromptMessageContent,
    PromptMessageContentType.CLAUDE_TOOL_RESULT: ClaudeToolResultPromptMessageContent,
    PromptMessageContentType.CLAUDE_MCP_USER: ClaudeMCPUserPromptMessageContent,
    PromptMessageContentType.CLAUDE_MCP_RESULT: ClaudeMCPResultPromptMessageContent,
}


class PromptMessage(ABC, BaseModel):
    """
    Model class for prompt message.
    """

    role: PromptMessageRole
    content: Optional[Union[str, PromptMessageContentUnionTypes, list[PromptMessageContentUnionTypes]]] = None
    name: Optional[str] = None

    def is_empty(self) -> bool:
        """
        Check if prompt message is empty.

        :return: True if prompt message is empty, False otherwise
        """
        return not self.content


class UserPromptMessage(PromptMessage):
    """
    Model class for user prompt message.
    """

    role: PromptMessageRole = PromptMessageRole.USER


class AssistantPromptMessage(PromptMessage):
    """
    Model class for assistant prompt message.
    """

    class ToolCall(BaseModel):
        """
        Model class for assistant prompt message tool call.
        """

        class ToolCallFunction(BaseModel):
            """
            Model class for assistant prompt message tool call function.
            """

            name: str
            arguments: str

        id: str
        type: str
        function: ToolCallFunction

        @field_validator("id", mode="before")
        @classmethod
        def transform_id_to_str(cls, value) -> str:
            if not isinstance(value, str):
                return str(value)
            else:
                return value

    role: PromptMessageRole = PromptMessageRole.ASSISTANT
    tool_calls: list[ToolCall] = []

    def is_empty(self) -> bool:
        """
        Check if prompt message is empty.

        :return: True if prompt message is empty, False otherwise
        """
        if not super().is_empty() and not self.tool_calls:
            return False

        return True


class SystemPromptMessage(PromptMessage):
    """
    Model class for system prompt message.
    """

    role: PromptMessageRole = PromptMessageRole.SYSTEM


class ToolPromptMessage(PromptMessage):
    """
    Model class for tool prompt message.
    """

    role: PromptMessageRole = PromptMessageRole.TOOL
    tool_call_id: str

    def is_empty(self) -> bool:
        """
        Check if prompt message is empty.

        :return: True if prompt message is empty, False otherwise
        """
        if not super().is_empty() and not self.tool_call_id:
            return False

        return True
