"""DTOs for the programmer memory REST surface."""

from typing import Literal

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


class ProjectBranchCreateRequest(MemorySchema):
    name: str = Field(..., min_length=1, max_length=120)
    localPath: str = Field(..., min_length=1, max_length=1000)


class ProjectBranchResponse(ProjectBranchCreateRequest):
    id: str = Field(..., min_length=1)


class ProjectCreateRequest(MemorySchema):
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(None, max_length=2000)
    mode: Literal["web", "desktop"]
    status: Literal["planning", "active", "done"] | None = None
    branches: list[ProjectBranchCreateRequest] = Field(default_factory=list)


class ProjectUpdateRequest(MemorySchema):
    name: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = Field(None, max_length=2000)
    status: Literal["planning", "active", "done"] | None = None
    branches: list[ProjectBranchResponse] | None = None


class ProjectListQuery(MemorySchema):
    search: str | None = None
    mode: Literal["web", "desktop", "all"] | None = None


class ProjectResponse(MemorySchema):
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field("", max_length=2000)
    mode: Literal["web", "desktop"]
    status: Literal["planning", "active", "done"]
    updatedAt: str = Field(..., min_length=1)
    branches: list[ProjectBranchResponse] = Field(default_factory=list)


class ProjectRecentRequest(MemorySchema):
    projectId: str | None = Field(None, min_length=1)


class ProjectRecentResponse(MemorySchema):
    projectId: str | None = None


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
