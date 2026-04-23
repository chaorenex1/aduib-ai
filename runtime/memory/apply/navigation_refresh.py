from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from component.storage.base_storage import storage_manager
from configs import config
from runtime.memory.committed_tree import CommittedMemoryTree
from service.memory.base.contracts import MemoryWritePipelineContext

from .patch import parse_markdown_document, serialize_markdown_document
from .staged_write import _is_supported_navigation_dir


def refresh_navigation(context: MemoryWritePipelineContext) -> dict:
    staged = context.phase_results.get("build_staged_write_set") or {}
    navigation_files: list[str] = []
    for mutation in staged.get("navigation_mutations") or []:
        directory_path = mutation["directory_path"]
        if not _is_supported_navigation_dir(directory_path):
            continue
        entries = CommittedMemoryTree.list_entries(
            path=directory_path, recursive=False, include_files=True, include_dirs=True
        )
        navigable_entries = []
        for entry in entries.get("entries") or []:
            path = entry["path"]
            if (
                path.endswith("/overview.md")
                or path.endswith("/summary.md")
                or path.endswith("overview.md")
                or path.endswith("summary.md")
            ):
                continue
            title = path.rsplit("/", 1)[-1]
            if entry["type"] == "file":
                metadata, _body = parse_markdown_document(storage_manager.read_text(_to_scoped_path(path)))
                title = str(metadata.get("title") or title).strip()
            navigable_entries.append({"path": path, "type": entry["type"], "title": title})
        overview_content = _render_navigation_document(
            kind="overview",
            scope_path=directory_path,
            navigable_entries=navigable_entries,
        )
        summary_content = _render_navigation_document(
            kind="summary",
            scope_path=directory_path,
            navigable_entries=navigable_entries,
        )
        storage_manager.write_text_atomic(_to_scoped_path(mutation["overview_path"]), overview_content)
        storage_manager.write_text_atomic(_to_scoped_path(mutation["summary_path"]), summary_content)
        navigation_files.extend([mutation["overview_path"], mutation["summary_path"]])
    return {
        "task_id": context.task_id,
        "phase": "refresh_navigation",
        "navigation_files": navigation_files,
    }


def _render_navigation_document(*, kind: str, scope_path: str, navigable_entries: list[dict[str, Any]]) -> str:
    now = datetime.now(UTC).isoformat()
    title = f"{scope_path.rsplit('/', 1)[-1].replace('-', ' ').title()} {kind.title()}"
    top_entries = [entry["title"] for entry in navigable_entries[:3]]
    metadata = {
        "schema_version": 1,
        "kind": kind,
        "scope_path": scope_path,
        "title": title,
        "created_at": now,
        "updated_at": now,
        "source": {"type": "derived", "trace": f"generated_directory_{kind}"},
        "visibility": "internal",
        "status": "active",
        "target_token_range": "1000-2000" if kind == "overview" else "100-200",
        "entry_count": len(navigable_entries),
        "top_entries": top_entries,
        "keywords": top_entries,
    }
    if kind == "overview":
        body = "\n".join(
            [
                "# Overview",
                f"This directory tracks content under `{scope_path}`.",
                "",
                "# Navigation Map",
                *[f"- `{entry['path']}` -> {entry['title']}" for entry in navigable_entries[:10]],
            ]
        )
    else:
        body = "\n".join(
            [
                "# Summary",
                f"This directory contains {len(navigable_entries)} navigable entries.",
                "",
                "# Key Entries",
                *[f"- `{entry['path']}`: {entry['title']}" for entry in navigable_entries[:3]],
            ]
        )
    return serialize_markdown_document(metadata=metadata, body=body)


def _to_scoped_path(relative_path: str) -> str:
    return "/".join(part for part in [config.MEMORY_TREE_ROOT_DIR, relative_path] if part)
