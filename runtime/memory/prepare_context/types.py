from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from runtime.memory.base.contracts import MemoryContract


class NormalizedSourceMaterial(MemoryContract):
    source_kind: str
    source_hash: str
    messages: list[dict[str, Any]] = Field(default_factory=list)
    text_blocks: list[str] = Field(default_factory=list)
    language: str | None = None
    conversation_snapshot: dict[str, Any] | None = None
    session_snapshot: dict[str, Any] | None = None
    archived_snapshot: dict[str, Any] | None = None
    user_id: str | None = None
    agent_id: str | None = None
    project_id: str | None = None


class PrefetchTreeNode(MemoryContract):
    path: str
    children: list[PrefetchTreeNode] = Field(default_factory=list)


class DirectoryTreeResult(MemoryContract):
    roots: list[PrefetchTreeNode] = Field(default_factory=list)


class DirectoryEntryRecord(MemoryContract):
    path: str
    type: Literal["file", "dir"]
    size: int | None = None


class DirectoryViewRecord(MemoryContract):
    path: str
    entries: list[DirectoryEntryRecord] = Field(default_factory=list)
    total: int = 0
    truncated: bool = False
    committed_view: bool = True
    exists: bool = False
    directory_tree: DirectoryTreeResult | None = None


class FileReadRecord(MemoryContract):
    path: str
    content: str
    line_start: int | None = None
    line_end: int | None = None
    truncated: bool = False
    committed_view: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    branch_path: str
    scope_type: str
    memory_type: str | None = None
    summary_level: Literal["l0", "l1"] | None = None


class BranchSummaryRecord(MemoryContract):
    branch_path: str
    scope_type: str
    memory_type: str | None = None
    summary_level: Literal["l0", "l1"]
    file_path: str
    content: str


class CandidateSearchQuery(MemoryContract):
    query: str
    path_scopes: list[str] = Field(default_factory=list)
    reason: str = ""


class CandidatePathMatch(MemoryContract):
    file_path: str
    score: float = 0.0


class CandidateMemoryRecord(MemoryContract):
    title: str
    file_path: str
    branch_path: str
    memory_type: str | None = None
    match_source: Literal["path_search"]
    match_reason: str = ""
    content_summary: str = ""


class SearchResultRecord(MemoryContract):
    query: str
    path: str
    matches: list[CandidatePathMatch] = Field(default_factory=list)
    total: int = 0
    truncated: bool = False
    committed_view: bool = True
    candidate_memories: list[CandidateMemoryRecord] = Field(default_factory=list)


class PreparedPrefetchContext(MemoryContract):
    directory_views: list[DirectoryViewRecord] = Field(default_factory=list)
    file_reads: list[FileReadRecord] = Field(default_factory=list)
    search_results: list[SearchResultRecord] = Field(default_factory=list)
    already_read_paths: list[str] = Field(default_factory=list)
    directory_tree: DirectoryTreeResult = Field(default_factory=DirectoryTreeResult)
    branch_summaries: list[BranchSummaryRecord] = Field(default_factory=list)
    candidate_memories: list[CandidateMemoryRecord] = Field(default_factory=list)


class CandidateDiscoveryWorkingState(MemoryContract):
    source: NormalizedSourceMaterial
    static_context: PreparedPrefetchContext
    query_history: list[CandidateSearchQuery] = Field(default_factory=list)
    search_results: list[SearchResultRecord] = Field(default_factory=list)
    candidate_memories: list[CandidateMemoryRecord] = Field(default_factory=list)
    completed: bool = False


class CandidateDiscoveryAction(MemoryContract):
    action: Literal["search_candidate_paths", "read_candidate_files", "finalize", "stop_noop"]
    reasoning: str = ""
    search_query: CandidateSearchQuery | None = None
    candidate_paths: list[str] = Field(default_factory=list)
