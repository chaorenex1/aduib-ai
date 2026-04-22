"""DTOs for the programmer memory REST surface."""

from typing import Literal

from fastapi import UploadFile
from pydantic import BaseModel, ConfigDict, Field, model_validator


class MemorySchema(BaseModel):
    """Base schema with strict payload validation."""

    model_config = ConfigDict(extra="forbid")


class MemoryScope(MemorySchema):
    user_id: str = Field(..., min_length=1)
    agent_id: str | None = Field(None, min_length=1)
    project_id: str | None = Field(None, min_length=1)


class MemoryMetadata(MemorySchema):
    language: str | None = Field(None, min_length=1, max_length=32)
    tags: list[str] = Field(default_factory=list)


class SourceRef(MemorySchema):
    type: str = Field(..., min_length=1)
    id: str = Field(..., min_length=1)
    path: str = Field(..., min_length=1)
    external_source: str | None = Field(None, min_length=1)
    external_session_id: str | None = Field(None, min_length=1)


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


class ConversationCreateRequest(MemoryScope):
    conversation: ConversationPayload
    metadata: MemoryMetadata | None = None


class ConversationAppendMessageRequest(MemoryScope):
    message: ConversationMessagePayload


class ProjectItemPayload(MemorySchema):
    item_type: str = Field(..., min_length=1)
    doc_type: str | None = None
    snippet_type: str | None = None
    title: str = Field(..., min_length=1)
    target_subdir: str = Field(..., min_length=1)
    content_parts: list[ContentPart] = Field(default_factory=list, min_length=1)


class ProjectPayload(MemorySchema):
    project_key: str | None = None
    title: str | None = None
    items: list[ProjectItemPayload] = Field(default_factory=list, min_length=1)


class ProjectImportRequest(MemorySchema):
    user_id: str = Field(..., min_length=1)
    project_path: str | None = None
    project: ProjectPayload
    metadata: MemoryMetadata | None = None


class ProjectGetQuery(MemorySchema):
    user_id: str = Field(..., min_length=1)


class TaskCreateRequest(MemoryScope):
    trigger_type: str = Field(..., min_length=1)
    source_ref: SourceRef


class MemoryListQuery(MemoryScope):
    kind: str | None = None
    path_prefix: str | None = None
    updated_after: str | None = None
    cursor: str | None = None
    limit: int = Field(20, ge=1, le=100)


class MemoryByPathQuery(MemorySchema):
    path: str = Field(..., min_length=1)


class MemorySearchRequest(MemoryScope):
    query: str = Field(..., min_length=1)
    mode: Literal["online", "recent", "global"] = "online"
    session_id: str | None = None
    include_types: list[str] = Field(default_factory=list)
    top_k: int = Field(10, ge=1, le=100)
    rerank: bool = True
    hotness_boost: bool = True


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


class MemoryUsageCreateRequest(MemoryScope):
    session_id: str = Field(..., min_length=1)
    used_contexts: list[MemoryUsageContext] = Field(default_factory=list)


class MemoryFeedbackCreateRequest(MemoryScope):
    memory_id: str = Field(..., min_length=1)
    feedback_type: Literal["helpful", "not_helpful", "incorrect", "outdated", "ranking_issue"]
    value: int | float | None = None
    note: str | None = None
    session_id: str | None = None
