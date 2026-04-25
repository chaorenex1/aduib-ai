from __future__ import annotations

from typing import Any

from component.storage.base_storage import storage_manager
from configs import config
from runtime.memory.apply.patch import parse_markdown_document
from runtime.memory.base.contracts import NavigationBranchFileState
from runtime.memory.committed_tree import CommittedMemoryTree
from runtime.memory.prepare_context.common import SUMMARY_FILENAMES


def to_scoped_navigation_path(relative_path: str) -> str:
    return "/".join(part for part in [config.MEMORY_TREE_ROOT_DIR, relative_path] if part)


def read_existing_navigation_docs(branch_path: str) -> dict[str, str | None]:
    overview_path = f"{branch_path}/overview.md"
    summary_path = f"{branch_path}/summary.md"
    return {
        "overview_md": _read_optional_text(overview_path),
        "summary_md": _read_optional_text(summary_path),
    }


def read_current_branch_files(
    branch_path: str,
    *,
    mutation_lookup: dict[str, dict[str, Any]] | None = None,
) -> list[NavigationBranchFileState]:
    raw_entries = CommittedMemoryTree.list_entries(
        path=branch_path,
        recursive=False,
        include_files=True,
        include_dirs=False,
    )
    states: list[NavigationBranchFileState] = []
    for entry in raw_entries.get("entries") or []:
        path = str(entry.get("path") or "").strip()
        if not path or any(path.endswith(f"/{name}") or path.endswith(name) for name in SUMMARY_FILENAMES):
            continue
        mutation = (mutation_lookup or {}).get(path) or {}
        states.append(
            NavigationBranchFileState(
                path=path,
                memory_type=_memory_type_for_path(path),
                op=str(mutation.get("op") or "existing").strip() or "existing",
                desired_content=_read_optional_text(path),
                previous_content=mutation.get("previous_content"),
            )
        )
    return states


def list_branch_navigable_entries(branch_path: str) -> list[dict[str, Any]]:
    entries = CommittedMemoryTree.list_entries(
        path=branch_path,
        recursive=False,
        include_files=True,
        include_dirs=True,
    )
    navigable_entries = []
    for entry in entries.get("entries") or []:
        path = str(entry.get("path") or "").strip()
        if not path:
            continue
        if any(path.endswith(f"/{name}") or path.endswith(name) for name in SUMMARY_FILENAMES):
            continue
        title = path.rsplit("/", 1)[-1]
        if str(entry.get("type") or "") == "file":
            metadata, _body = parse_markdown_document(storage_manager.read_text(to_scoped_navigation_path(path)))
            title = str(metadata.get("title") or title).strip()
        navigable_entries.append({"path": path, "type": entry.get("type"), "title": title})
    return navigable_entries


def _read_optional_text(relative_path: str) -> str | None:
    scoped_path = to_scoped_navigation_path(relative_path)
    if not storage_manager.exists(scoped_path):
        return None
    return storage_manager.read_text(scoped_path)


def _memory_type_for_path(path: str) -> str:
    parts = [part for part in str(path or "").split("/") if part]
    if len(parts) >= 2:
        return parts[-2]
    return "unknown"
