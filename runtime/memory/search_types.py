from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from configs import config
from controllers.memory.schemas import ConversationMessagePayload

SEARCH_L0_LEVEL = "l0"
SEARCH_L1_LEVEL = "l1"
SEARCH_L2_LEVEL = "l2"


class SearchModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchRequest(SearchModel):
    query: str = Field(..., min_length=1)
    session: list[ConversationMessagePayload] = Field(..., min_length=1)
    include_types: list[str] = Field(default_factory=list)
    top_k: int = Field(..., ge=1)
    score_threshold: float = Field(..., ge=0.0, le=1.0)


class L0L1Hit(SearchModel):
    branch_path: str = Field(..., min_length=1)
    file_path: str = Field(..., min_length=1)
    memory_type: str = Field(..., min_length=1)
    memory_level: Literal["l0", "l1"]
    content: str = Field(..., min_length=1)
    score: float = Field(..., ge=0.0, le=1.0)
    updated_at: str | None = None
    tags: list[str] = Field(default_factory=list)


class SearchPlan(SearchModel):
    normalized_query: str = ""
    intent: str = ""
    query_rewrites: list[str] = Field(default_factory=list)
    target_memory_types: list[str] = Field(default_factory=list)
    selected_branch_paths: list[str] = Field(default_factory=list)
    expand_l2: bool = False
    max_l2_files: int = 5


class L2Candidate(SearchModel):
    branch_path: str = Field(..., min_length=1)
    file_path: str = Field(..., min_length=1)
    memory_type: str = Field(..., min_length=1)
    updated_at: str | None = None
    tags: list[str] = Field(default_factory=list)


class L2ReadResult(SearchModel):
    branch_path: str = Field(..., min_length=1)
    file_path: str = Field(..., min_length=1)
    memory_type: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    abstract: str = Field(..., min_length=1)
    updated_at: str | None = None
    tags: list[str] = Field(default_factory=list)


class SearchCandidate(SearchModel):
    branch_path: str = Field(..., min_length=1)
    file_path: str = Field(..., min_length=1)
    memory_type: str = Field(..., min_length=1)
    source_level: Literal["l0", "l1", "l2"]
    content: str = Field(..., min_length=1)
    abstract: str = Field(..., min_length=1)
    vector_score: float | None = Field(default=None, ge=0.0, le=1.0)
    rerank_score: float | None = Field(default=None, ge=0.0, le=1.0)
    final_score: float | None = Field(default=None, ge=0.0, le=1.0)
    updated_at: str | None = None
    tags: list[str] = Field(default_factory=list)


class MemorySearchRequestDTO(SearchModel):
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
    def validate_search_payload_limits(self) -> MemorySearchRequestDTO:
        for message in self.session:
            if len(message.content_parts) > config.MEMORY_SEARCH_CONTENT_PARTS_MAX:
                raise ValueError("memory search session message exceeds content_parts limit")
            for part in message.content_parts:
                if part.type == "text" and part.text and len(part.text) > config.MEMORY_SEARCH_TEXT_PART_MAX_CHARS:
                    raise ValueError("memory search text content exceeds max length")
        return self


class MemorySearchResultItemDTO(SearchModel):
    abstract: str = Field(..., min_length=1)
    score: float = Field(..., ge=0.0, le=1.0)
    memory_type: str = Field(..., min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)


class MemorySearchResponseDTO(SearchModel):
    query: str = Field(..., min_length=1)
    results: list[MemorySearchResultItemDTO] = Field(default_factory=list)
