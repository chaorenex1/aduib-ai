from __future__ import annotations

import re
from collections import defaultdict

from configs import config
from runtime.memory.apply.patch import parse_markdown_document
from runtime.memory.committed_tree import CommittedMemoryTree
from service.memory.repository import MemoryMetadataRepository

from .search_types import L2Candidate, L2ReadResult


class MemorySearchL2Reader:
    @classmethod
    def list_l2_candidates(
        cls,
        user_id: str,
        branch_paths: list[str],
        include_types: list[str],
        max_files: int,
    ) -> list[L2Candidate]:
        if not branch_paths or max_files < 1:
            return []
        rows = MemoryMetadataRepository.list_l2_rows_by_branch_paths(
            user_id=user_id,
            branch_paths=branch_paths,
            include_types=include_types or None,
        )
        candidates_by_branch: dict[str, list[L2Candidate]] = defaultdict(list)
        for item in rows:
            file_path = str(item.get("file_path") or "").strip()
            if not file_path or file_path.endswith(("/overview.md", "/summary.md")):
                continue
            branch_path = cls._resolve_branch_path(file_path=file_path, requested_branch_paths=branch_paths)
            if not branch_path:
                continue
            candidates_by_branch[branch_path].append(
                L2Candidate(
                    branch_path=branch_path,
                    file_path=file_path,
                    memory_type=str(item.get("memory_type") or "unknown"),
                    updated_at=item.get("memory_updated_at"),
                    tags=list(item.get("tags") or []),
                )
            )

        ordered: list[L2Candidate] = []
        for branch_path in branch_paths:
            ordered.extend(candidates_by_branch.get(branch_path, [])[:max_files])
        return ordered

    @classmethod
    def read_candidates(cls, query: str, candidates: list[L2Candidate]) -> list[L2ReadResult]:
        reads: list[L2ReadResult] = []
        for item in candidates:
            content = cls._read_file(item.file_path)
            abstract = cls._build_l2_abstract(query=query, content=content)
            if not abstract:
                continue
            reads.append(
                L2ReadResult(
                    branch_path=item.branch_path,
                    file_path=item.file_path,
                    memory_type=item.memory_type,
                    content=content,
                    abstract=abstract,
                    updated_at=item.updated_at,
                    tags=item.tags,
                )
            )
        return reads

    @staticmethod
    def _read_file(path: str) -> str:
        file_view = CommittedMemoryTree.read_file(
            path=path,
            max_chars=config.MEMORY_SEARCH_L2_READ_MAX_CHARS,
            include_metadata=False,
        )
        return MemorySearchL2Reader._truncate_content_for_read(str(file_view.get("content") or ""))

    @staticmethod
    def _build_l2_abstract(query: str, content: str) -> str:
        metadata, body = parse_markdown_document(content)
        text = str(body or "").strip()
        if not text:
            return ""

        query_text = str(query or "").strip().lower()
        query_tokens = [token for token in re.split(r"\s+", query_text) if token]
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        matched_lines = [
            line
            for line in lines
            if (query_text and query_text in line.lower())
            or any(token and token in line.lower() for token in query_tokens)
        ]
        selected_lines = matched_lines[:3] if matched_lines else lines[:3]

        summary_parts: list[str] = []
        title = str(metadata.get("title") or "").strip()
        if title:
            summary_parts.append(title)
        summary_parts.extend(selected_lines)
        return "\n".join(summary_parts).strip()[:1500]

    @staticmethod
    def _truncate_content_for_read(content: str) -> str:
        text = str(content or "")
        if len(text) <= config.MEMORY_SEARCH_L2_READ_MAX_CHARS:
            return text
        return text[: config.MEMORY_SEARCH_L2_READ_MAX_CHARS]

    @staticmethod
    def _resolve_branch_path(file_path: str, requested_branch_paths: list[str]) -> str | None:
        normalized_path = str(file_path or "").strip().strip("/")
        for branch_path in requested_branch_paths:
            normalized_branch = str(branch_path or "").strip().strip("/")
            if normalized_path == normalized_branch or normalized_path.startswith(f"{normalized_branch}/"):
                return normalized_branch
        return None
