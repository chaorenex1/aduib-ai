from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FIND_L0_LEVEL = "l0"
FIND_L1_LEVEL = "l1"


class FindModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FindRequest(FindModel):
    query: str = Field(..., min_length=1)
    include_types: list[str] = Field(default_factory=list)
    top_k: int = Field(..., ge=1)
    score_threshold: float = Field(..., ge=0.0, le=1.0)


class NavigationIndexSourceRow(FindModel):
    memory_id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    project_id: str | None = None
    memory_type: str = Field(..., min_length=1)
    memory_level: Literal["l0", "l1"]
    branch_path: str = Field(..., min_length=1)
    file_path: str = Field(..., min_length=1)
    abstract_text: str = Field(..., min_length=1)
    tags: list[str] = Field(default_factory=list)
    memory_updated_at: str | None = None
    vector_doc_id: str = Field(..., min_length=1)


class L0VectorHit(FindModel):
    branch_path: str = Field(..., min_length=1)
    file_path: str = Field(..., min_length=1)
    memory_type: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    score: float = Field(..., ge=0.0, le=1.0)
    updated_at: str | None = None
    tags: list[str] = Field(default_factory=list)


class L1BranchHit(FindModel):
    branch_path: str = Field(..., min_length=1)
    file_path: str = Field(..., min_length=1)
    memory_type: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    source_l0_score: float = Field(..., ge=0.0, le=1.0)
    updated_at: str | None = None
    tags: list[str] = Field(default_factory=list)


class FindCandidate(FindModel):
    branch_path: str = Field(..., min_length=1)
    file_path: str = Field(..., min_length=1)
    memory_type: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    source_level: Literal["l0", "l1"]
    vector_score: float = Field(..., ge=0.0, le=1.0)
    rerank_score: float | None = Field(default=None, ge=0.0, le=1.0)
    final_score: float | None = Field(default=None, ge=0.0, le=1.0)
    updated_at: str | None = None
    tags: list[str] = Field(default_factory=list)


class MemoryFindRequestDTO(FindModel):
    query: str = Field(..., min_length=1)
    include_types: list[str] = Field(default_factory=list)
    top_k: int = Field(10, ge=1, le=50)
    score_threshold: float = Field(0.35, ge=0.0, le=1.0)


class MemoryFindResultItemDTO(FindModel):
    abstract: str = Field(..., min_length=1)
    score: float = Field(..., ge=0.0, le=1.0)
    memory_type: str = Field(..., min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)


class MemoryFindResponseDTO(FindModel):
    query: str = Field(..., min_length=1)
    results: list[MemoryFindResultItemDTO] = Field(default_factory=list)
