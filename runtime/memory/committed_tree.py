from __future__ import annotations

import fnmatch
import re
from collections.abc import Iterable
from difflib import SequenceMatcher
from typing import Any

from component.storage.base_storage import normalize_storage_path, storage_manager
from configs import config


class MemoryTreeError(ValueError):
    """Raised when a committed memory tree request is invalid."""


class CommittedMemoryTree:
    @staticmethod
    def list_entries(
        *,
        path: str = "",
        recursive: bool = False,
        include_files: bool = True,
        include_dirs: bool = True,
        max_results: int | None = None,
    ) -> dict[str, Any]:
        if not include_files and not include_dirs:
            raise MemoryTreeError("At least one of include_files or include_dirs must be true")

        resolved_max_results = max_results if max_results is not None else config.MEMORY_TREE_LIST_MAX_RESULTS
        if resolved_max_results < 1:
            raise MemoryTreeError("max_results must be at least 1")
        if storage_manager.storage_instance is None:
            raise MemoryTreeError("Memory storage is not initialized")

        relative_path = CommittedMemoryTree._normalize_relative_path(path)
        scoped_path = CommittedMemoryTree._scoped_path(relative_path)
        entries = storage_manager.list_dir(scoped_path, recursive=recursive)
        filtered = []
        for entry in entries:
            entry_path = CommittedMemoryTree._to_relative_path(entry.path)
            if entry_path is None:
                continue
            if entry.is_file and not include_files:
                continue
            if entry.is_dir and not include_dirs:
                continue
            filtered.append(
                {
                    "path": entry_path,
                    "type": "file" if entry.is_file else "dir",
                    "size": entry.size,
                }
            )

        truncated = len(filtered) > resolved_max_results
        return {
            "path": relative_path or ".",
            "entries": filtered[:resolved_max_results],
            "total": len(filtered),
            "truncated": truncated,
            "committed_view": True,
        }

    @staticmethod
    def read_file(
        *,
        path: str,
        start_line: int | None = None,
        end_line: int | None = None,
        max_chars: int | None = None,
        include_metadata: bool = True,
    ) -> dict[str, Any]:
        resolved_max_chars = max_chars if max_chars is not None else config.MEMORY_TREE_READ_MAX_CHARS
        if resolved_max_chars < 1:
            raise MemoryTreeError("max_chars must be at least 1")
        if start_line is not None and start_line < 1:
            raise MemoryTreeError("start_line must be at least 1")
        if end_line is not None and end_line < 1:
            raise MemoryTreeError("end_line must be at least 1")
        if start_line is not None and end_line is not None and end_line < start_line:
            raise MemoryTreeError("end_line must be greater than or equal to start_line")
        if storage_manager.storage_instance is None:
            raise MemoryTreeError("Memory storage is not initialized")

        relative_path = CommittedMemoryTree._normalize_relative_path(path, allow_empty=False)
        scoped_path = CommittedMemoryTree._scoped_path(relative_path)
        if not storage_manager.exists(scoped_path):
            raise MemoryTreeError(f"Memory file not found: {relative_path}")

        content = storage_manager.read_text(scoped_path)
        selected_content, line_start, line_end = CommittedMemoryTree._slice_content(content, start_line, end_line)
        selected_content, truncated = CommittedMemoryTree._truncate_text(selected_content, resolved_max_chars)
        result = {
            "path": relative_path,
            "content": selected_content,
            "line_start": line_start,
            "line_end": line_end,
            "truncated": truncated,
            "committed_view": True,
        }
        if include_metadata:
            result["metadata"] = {
                "size": storage_manager.size(scoped_path),
                "kind": CommittedMemoryTree._detect_kind(relative_path),
            }
        return result

    @staticmethod
    def build_tree(
        *,
        path: str = "",
        include_dirs: bool = True,
        include_content: bool = True,
        max_depth: int | None = None,
        max_files: int | None = None,
        max_chars_per_file: int | None = None,
        max_total_chars: int | None = None,
    ) -> dict[str, Any]:
        resolved_max_files = max_files if max_files is not None else config.MEMORY_TREE_MAX_FILES
        resolved_max_chars_per_file = (
            max_chars_per_file if max_chars_per_file is not None else config.MEMORY_TREE_MAX_CHARS_PER_FILE
        )
        resolved_max_total_chars = (
            max_total_chars if max_total_chars is not None else config.MEMORY_TREE_MAX_TOTAL_CHARS
        )

        if max_depth is not None and max_depth < 0:
            raise MemoryTreeError("max_depth must be at least 0")
        if resolved_max_files < 1:
            raise MemoryTreeError("max_files must be at least 1")
        if resolved_max_chars_per_file < 1:
            raise MemoryTreeError("max_chars_per_file must be at least 1")
        if resolved_max_total_chars < 1:
            raise MemoryTreeError("max_total_chars must be at least 1")
        if storage_manager.storage_instance is None:
            raise MemoryTreeError("Memory storage is not initialized")

        relative_path = CommittedMemoryTree._normalize_relative_path(path)
        scoped_path = CommittedMemoryTree._scoped_path(relative_path)
        entries = storage_manager.list_dir(scoped_path, recursive=True)
        filtered_entries = []
        for entry in entries:
            entry_path = CommittedMemoryTree._to_relative_path(entry.path)
            if entry_path is None:
                continue
            if max_depth is not None and CommittedMemoryTree._path_depth(relative_path, entry_path) > max_depth:
                continue
            filtered_entries.append((entry, entry_path))

        total_files = sum(1 for entry, _ in filtered_entries if entry.is_file)
        tree: list[dict[str, Any]] = []
        emitted_files = 0
        remaining_chars = resolved_max_total_chars
        truncated = False

        for entry, entry_path in filtered_entries:
            if entry.is_dir:
                if include_dirs:
                    tree.append({"path": entry_path, "type": "dir"})
                continue

            if emitted_files >= resolved_max_files:
                truncated = True
                break

            item: dict[str, Any] = {
                "path": entry_path,
                "type": "file",
                "size": entry.size,
            }
            if include_content:
                raw_content = storage_manager.read_text(CommittedMemoryTree._scoped_path(entry_path))
                allowed_chars = min(resolved_max_chars_per_file, remaining_chars)
                content, content_truncated = CommittedMemoryTree._truncate_text(raw_content, allowed_chars)
                item["content"] = content
                item["truncated"] = content_truncated
                remaining_chars -= len(content)
                if content_truncated or remaining_chars <= 0:
                    truncated = True
            tree.append(item)
            emitted_files += 1
            if remaining_chars <= 0:
                break

        return {
            "path": relative_path or ".",
            "tree": tree,
            "total_files": total_files,
            "truncated": truncated,
            "committed_view": True,
        }

    @staticmethod
    def search_paths(
        *,
        query: str,
        path: str = "",
        glob_pattern: str | None = None,
        max_results: int | None = None,
    ) -> dict[str, Any]:
        return CommittedMemoryTree._search(
            query=query,
            path=path,
            glob_pattern=glob_pattern,
            max_results=max_results,
            value_getter=lambda relative_path: relative_path,
        )

    @staticmethod
    def search_content(
        *,
        query: str,
        path: str = "",
        glob_pattern: str | None = None,
        max_results: int | None = None,
    ) -> dict[str, Any]:
        return CommittedMemoryTree._search(
            query=query,
            path=path,
            glob_pattern=glob_pattern,
            max_results=max_results,
            value_getter=lambda relative_path: storage_manager.read_text(
                CommittedMemoryTree._scoped_path(relative_path)
            ),
        )

    @staticmethod
    def _search(
        *,
        query: str,
        path: str,
        glob_pattern: str | None,
        max_results: int | None,
        value_getter,
    ) -> dict[str, Any]:
        if not isinstance(query, str) or not query.strip():
            raise MemoryTreeError("query must be a non-empty string")

        resolved_max_results = max_results if max_results is not None else config.MEMORY_TREE_SEARCH_MAX_RESULTS
        if resolved_max_results < 1:
            raise MemoryTreeError("max_results must be at least 1")
        if storage_manager.storage_instance is None:
            raise MemoryTreeError("Memory storage is not initialized")
        relative_path = CommittedMemoryTree._normalize_relative_path(path)
        matches: list[dict[str, Any]] = []
        for entry_path in CommittedMemoryTree._iter_file_paths(relative_path=relative_path, glob_pattern=glob_pattern):
            score = CommittedMemoryTree._semantic_score(query, value_getter(entry_path))
            if score <= 0:
                continue
            matches.append({"path": entry_path, "score": round(score, 4)})

        matches.sort(key=lambda item: (-item["score"], item["path"]))
        truncated = len(matches) > resolved_max_results
        return {
            "query": query.strip(),
            "path": relative_path or ".",
            "matches": matches[:resolved_max_results],
            "total": len(matches),
            "truncated": truncated,
            "committed_view": True,
        }

    @staticmethod
    def _iter_file_paths(
        *,
        relative_path: str,
        glob_pattern: str | None,
    ) -> Iterable[str]:
        scoped_path = CommittedMemoryTree._scoped_path(relative_path)
        entries = storage_manager.list_dir(scoped_path, recursive=True)
        for entry in entries:
            if not entry.is_file:
                continue
            entry_path = CommittedMemoryTree._to_relative_path(entry.path)
            if entry_path is None:
                continue
            if glob_pattern and not fnmatch.fnmatch(entry_path, glob_pattern):
                continue
            yield entry_path

    @staticmethod
    def _scoped_path(relative_path: str) -> str:
        return "/".join(part for part in [CommittedMemoryTree._root_prefix(), relative_path] if part)

    @staticmethod
    def _root_prefix() -> str:
        return CommittedMemoryTree._normalize_relative_path(config.MEMORY_TREE_ROOT_DIR, allow_empty=False)

    @staticmethod
    def _to_relative_path(scoped_path: str) -> str | None:
        normalized = normalize_storage_path(scoped_path)
        root_prefix = f"{CommittedMemoryTree._root_prefix()}/"
        if normalized == CommittedMemoryTree._root_prefix():
            return "."
        if normalized.startswith(root_prefix):
            return normalized[len(root_prefix) :]
        return None

    @staticmethod
    def _normalize_relative_path(path: str, *, allow_empty: bool = True) -> str:
        if path is None:
            if allow_empty:
                return ""
            raise MemoryTreeError("path must be a non-empty string")
        if not isinstance(path, str):
            raise MemoryTreeError("path must be a string")

        raw = path.strip().replace("\\", "/")
        if raw in {"", ".", "/"}:
            if allow_empty:
                return ""
            raise MemoryTreeError("path must be a non-empty string")

        if raw.startswith("/"):
            raise MemoryTreeError("path must be memory-relative")

        parts = []
        for part in raw.split("/"):
            if part in {"", "."}:
                continue
            if part == "..":
                raise MemoryTreeError("path must not contain '..'")
            parts.append(part)

        normalized = normalize_storage_path("/".join(parts))
        if not normalized and not allow_empty:
            raise MemoryTreeError("path must be a non-empty string")
        return normalized

    @staticmethod
    def _slice_content(content: str, start_line: int | None, end_line: int | None) -> tuple[str, int, int]:
        if start_line is None and end_line is None:
            total_lines = content.count("\n") + 1 if content else 0
            return content, 1 if total_lines else 0, total_lines

        lines = content.splitlines(keepends=True)
        start_index = (start_line - 1) if start_line is not None else 0
        end_index = end_line if end_line is not None else len(lines)
        selected = "".join(lines[start_index:end_index])
        actual_start = start_line if start_line is not None else 1
        actual_end = min(end_index, len(lines))
        return selected, actual_start, actual_end

    @staticmethod
    def _truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
        if len(text) <= max_chars:
            return text, False
        return text[:max_chars], True

    @staticmethod
    def _path_depth(base_path: str, entry_path: str) -> int:
        if not base_path:
            return len(entry_path.split("/"))
        relative = entry_path[len(base_path) :].lstrip("/")
        return len(relative.split("/")) if relative else 0

    @staticmethod
    def _detect_kind(relative_path: str) -> str:
        filename = relative_path.rsplit("/", 1)[-1]
        if filename == "overview.md":
            return "overview"
        if filename == "summary.md":
            return "summary"
        return "memory_file"

    @staticmethod
    def _semantic_score(query: str, text: str) -> float:
        query_normalized = CommittedMemoryTree._normalize_text(query)
        text_normalized = CommittedMemoryTree._normalize_text(text)
        if not query_normalized or not text_normalized:
            return 0.0

        if query_normalized in text_normalized:
            return 1.0

        query_tokens = CommittedMemoryTree._tokenize(query_normalized)
        text_tokens = CommittedMemoryTree._tokenize(text_normalized)
        if not query_tokens or not text_tokens:
            return 0.0

        overlap = len(query_tokens & text_tokens)
        partial_overlap = sum(
            1
            for query_token in query_tokens
            for text_token in text_tokens
            if query_token in text_token or text_token in query_token
        )

        score = 0.0
        if overlap:
            score = max(score, 0.5 + (overlap / len(query_tokens)) * 0.45)
        elif partial_overlap:
            score = max(score, 0.3 + (partial_overlap / len(query_tokens)) * 0.35)

        ratio = SequenceMatcher(None, query_normalized, text_normalized).ratio()
        score = max(score, ratio * 0.4)
        return score if score >= 0.25 else 0.0

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"\s+", " ", text.lower()).strip()

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        raw_tokens = re.findall(r"[a-z0-9]+", text.lower())
        tokens: set[str] = set()
        for token in raw_tokens:
            tokens.add(token)
            if len(token) > 3 and token.endswith("s"):
                tokens.add(token[:-1])
        return tokens
