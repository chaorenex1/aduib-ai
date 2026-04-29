"""DTOs for the programmer memory REST surface."""

from typing import Literal

from fastapi import UploadFile
from pydantic import BaseModel, ConfigDict, Field, model_validator

from configs import config


class MemorySchema(BaseModel):
    """Base schema with strict payload validation."""

    model_config = ConfigDict(extra="forbid")


class MemoryScope(MemorySchema):
    user_id: str = Field(..., min_length=1)
    project_id: str | None = Field(None, min_length=1)


class MemoryActorScope(MemorySchema):
    user_id: str = Field(..., min_length=1)
    agent_id: str | None = Field(None, min_length=1)
    project_id: str | None = Field(None, min_length=1)


class MemoryMetadata(MemorySchema):
    language: str | None = Field(None, min_length=1, max_length=32)
    tags: list[str] = Field(default_factory=list)


class SourceRef(MemorySchema):
    type: str = Field(..., min_length=1)
    conversation_id: str = Field(..., min_length=1)
    path: str | None = Field(None, min_length=1)
    external_source: str | None = Field(None, min_length=1)
    external_session_id: str | None = Field(None, min_length=1)

    @model_validator(mode="after")
    def validate_source_ref_shape(self) -> "SourceRef":
        if self.type == "conversation":
            return self

        if not self.path:
            raise ValueError(f"{self.type} source_ref requires path")
        return self


class ContentPart(MemorySchema):
    type: Literal["text", "image", "audio", "file"]
    text: str | None = None
    data_base64: str | None = None
    file_id: str | None = None
    mime_type: str | None = None
    name: str | None = None

    @model_validator(mode="after")
    def validate_payload(self) -> "ContentPart":
        if self.type == "text" and not self.text:
            raise ValueError("text content_part requires text")
        if self.type in {"image", "audio", "file"} and not (self.file_id or self.data_base64):
            raise ValueError(f"{self.type} content_part requires file_id or data_base64")
        if self.type in {"image", "audio", "file"} and not self.mime_type:
            raise ValueError(f"{self.type} content_part requires mime_type")
        return self


class ConversationMessagePayload(MemorySchema):
    role: Literal["system", "user", "assistant", "tool"]
    content_parts: list[ContentPart] = Field(default_factory=list, min_length=1)
    created_at: str | None = None


class ConversationPayload(MemorySchema):
    external_source: str = Field(..., min_length=1)
    external_session_id: str = Field(..., min_length=1)
    title: str | None = None
    messages: list[ConversationMessagePayload] = Field(default_factory=list, min_length=1)


class ConversationActorScope(MemorySchema):
    agent_id: str | None = Field(None, min_length=1)
    project_id: str | None = Field(None, min_length=1)


class ConversationCreateRequest(ConversationActorScope):
    conversation: ConversationPayload
    metadata: MemoryMetadata | None = None


class ConversationAppendMessageRequest(ConversationActorScope):
    message: ConversationMessagePayload


class ConversationGetQuery(MemorySchema):
    pass


class ConversationSourceResponse(MemorySchema):
    conversation_id: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    title: str | None = None
    user_id: str = Field(..., min_length=1)
    agent_id: str | None = None
    project_id: str | None = None
    external_source: str = Field(..., min_length=1)
    external_session_id: str = Field(..., min_length=1)
    message_count: int = Field(..., ge=1)
    modalities: list[str] = Field(default_factory=list)
    version: int = Field(..., ge=1)
    created_at: str | None = None
    updated_at: str | None = None


class ProjectItemPayload(MemorySchema):
    item_type: str = Field(..., min_length=1)
    doc_type: str | None = None
    snippet_type: str | None = None
    title: str = Field(..., min_length=1)
    content_parts: list[ContentPart] = Field(default_factory=list, min_length=1)


class ProjectImportRequest(MemorySchema):
    user_id: str = Field(..., min_length=1)
    project_id: str = Field(..., min_length=1)
    items: list[ProjectItemPayload] = Field(default_factory=list, min_length=1)
    metadata: MemoryMetadata | None = None


class ProjectGetQuery(MemorySchema):
    user_id: str = Field(..., min_length=1)


class TaskCreateRequest(MemoryActorScope):
    trigger_type: str = Field(..., min_length=1)
    source_ref: SourceRef


class MemoryArchiveRef(MemorySchema):
    path: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    storage: str = Field("default", min_length=1)
    content_sha256: str | None = None
    size_bytes: int | None = None


class MemoryWriteAcceptedResponse(MemorySchema):
    task_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    trigger_type: str = Field(..., min_length=1)
    status: str | None = None
    phase: str = Field(..., min_length=1)
    source_ref: SourceRef
    archive_ref: MemoryArchiveRef | None = None


class MemoryWriteTaskResponse(MemoryWriteAcceptedResponse):
    failure_message: str | None = None
    queued_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class MemoryWriteTaskResultResponse(MemorySchema):
    task_id: str = Field(..., min_length=1)
    status: str | None = None
    phase: str = Field(..., min_length=1)
    archive_ref: MemoryArchiveRef | None = None
    failure_message: str | None = None


class MemoryListQuery(MemoryScope):
    memory_type: str | None = None
    path_prefix: str | None = None
    updated_after: str | None = None
    cursor: str | None = None
    limit: int = Field(20, ge=1, le=100)


class MemoryByPathQuery(MemoryScope):
    path: str = Field(..., min_length=1)


class MemoryFindRequest(MemorySchema):
    query: str = Field(..., min_length=1)
    include_types: list[str] = Field(default_factory=list)
    top_k: int = Field(10, ge=1, le=50)
    score_threshold: float = Field(0.35, ge=0.0, le=1.0)


class MemoryFindResultItem(MemorySchema):
    abstract: str = Field(..., min_length=1)
    score: float = Field(..., ge=0.0, le=1.0)
    memory_type: str = Field(..., min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)


class MemoryFindResponse(MemorySchema):
    query: str = Field(..., min_length=1)
    results: list[MemoryFindResultItem] = Field(default_factory=list)


class MemorySearchRequest(MemorySchema):
    query: str = Field(..., min_length=1, max_length=config.MEMORY_SEARCH_QUERY_MAX_CHARS)
    session: list[ConversationMessagePayload] = Field(
        ...,
        min_length=1,
        max_length=config.MEMORY_SEARCH_MAX_SESSION_MESSAGES,
    )
    include_types: list[str] = Field(default_factory=list, max_length=config.MEMORY_SEARCH_INCLUDE_TYPES_MAX)
    top_k: int = Field(config.MEMORY_SEARCH_TOP_K_DEFAULT, ge=1, le=config.MEMORY_SEARCH_TOP_K_MAX)
    score_threshold: float = Field(
        config.MEMORY_SEARCH_SCORE_THRESHOLD_DEFAULT,
        ge=0.0,
        le=1.0,
    )

    @model_validator(mode="after")
    def validate_search_payload_limits(self) -> "MemorySearchRequest":
        for message in self.session:
            if len(message.content_parts) > config.MEMORY_SEARCH_CONTENT_PARTS_MAX:
                raise ValueError("memory search session message exceeds content_parts limit")
            for part in message.content_parts:
                if part.type == "text" and part.text and len(part.text) > config.MEMORY_SEARCH_TEXT_PART_MAX_CHARS:
                    raise ValueError("memory search text content exceeds max length")
        return self


class MemorySearchResultItem(MemorySchema):
    abstract: str = Field(..., min_length=1)
    score: float = Field(..., ge=0.0, le=1.0)
    memory_type: str = Field(..., min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)


class MemorySearchResponse(MemorySchema):
    query: str = Field(..., min_length=1)
    results: list[MemorySearchResultItem] = Field(default_factory=list)


class MemoryCreateRequest(MemorySchema):
    """Legacy memory create request kept for `/memory/store` compatibility."""

    content: str = Field(..., description="Memory content text, can be empty if file is provided")
    file: UploadFile | None = Field(None, description="Memory file")
    project_id: str = Field(..., description="Project ID associated with the memory")
    user_id: str = Field(..., description="User ID associated with the memory", exclude=True)
    agent_id: str | None = Field(None, description="Agent ID associated with the memory", exclude=True)
    summary_enabled: bool = Field(False, description="Whether to generate summary for the memory")
    memory_source: str | None = Field(
        None,
        description="Source of the memory, e.g. 'user_input', 'agent_observation'",
    )


class MemoryRetrieveRequest(MemorySchema):
    """Legacy memory retrieval request kept for `/memory/retrieve` compatibility."""

    query: str
    user_id: str
    agent_id: str | None = None
    project_id: str | None = None
    retrieve_type: str
    top_k: int = 5
    score_threshold: float = 0.6
    filters: dict[str, object] = Field(default_factory=dict)


class MemoryRetrieveResponse(MemorySchema):
    """Legacy memory retrieval response kept for `/memory/retrieve` compatibility."""

    content: str = Field(..., description="Memory content text, can be empty if file is provided")
    memory_id: str = Field(..., description="Memory ID")
    score: float = Field(..., description="Memory score")
    metadata: dict[str, object] = Field(default_factory=dict, description="Additional metadata for the memory")

    @classmethod
    def from_memory(
        cls,
        content: str,
        memory_id: str,
        score: float = 0.0,
        metadata: dict[str, object] | None = None,
    ) -> "MemoryRetrieveResponse":
        return cls(
            content=content,
            memory_id=memory_id,
            score=score,
            metadata=metadata or {},
        )


class MemoryUsageContext(MemorySchema):
    memory_id: str = Field(..., min_length=1)
    path: str = Field(..., min_length=1)
    kind: str = Field(..., min_length=1)


class MemoryUsageCreateRequest(MemoryActorScope):
    session_id: str = Field(..., min_length=1)
    used_contexts: list[MemoryUsageContext] = Field(default_factory=list)


class MemoryFeedbackCreateRequest(MemoryActorScope):
    memory_id: str = Field(..., min_length=1)
    feedback_type: Literal["helpful", "not_helpful", "incorrect", "outdated", "ranking_issue"]
    value: int | float | None = None
    note: str | None = None
    session_id: str | None = None
