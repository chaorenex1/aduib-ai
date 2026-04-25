from __future__ import annotations

from datetime import UTC, datetime

from component.storage.base_storage import storage_manager
from runtime.memory.base.contracts import MemoryWritePipelineContext, NavigationSummaryBranchPlan

from ..navigation.common import list_branch_navigable_entries, to_scoped_navigation_path
from .patch import serialize_markdown_document
from .staged_write import _is_supported_navigation_dir


def refresh_navigation(context: MemoryWritePipelineContext) -> dict:
    summary_result = context.phase_results.get("generate_navigation_summary") or {}
    navigation_files: list[str] = []
    branch_plans = [
        NavigationSummaryBranchPlan.model_validate(item)
        for item in summary_result.get("navigation_mutations") or []
    ]
    for branch_plan in branch_plans:
        directory_path = branch_plan.branch_path
        if not _is_supported_navigation_dir(directory_path):
            continue
        navigable_entries = list_branch_navigable_entries(directory_path)
        if branch_plan.overview.op != "noop":
            overview_content = _render_planned_navigation_document(
                kind="overview",
                scope_path=directory_path,
                navigable_entries=navigable_entries,
                markdown_body=branch_plan.overview.markdown_body,
            )
            storage_manager.write_text_atomic(
                to_scoped_navigation_path(branch_plan.overview.path),
                overview_content,
            )
            navigation_files.append(branch_plan.overview.path)
        if branch_plan.summary.op != "noop":
            summary_content = _render_planned_navigation_document(
                kind="summary",
                scope_path=directory_path,
                navigable_entries=navigable_entries,
                markdown_body=branch_plan.summary.markdown_body,
            )
            storage_manager.write_text_atomic(
                to_scoped_navigation_path(branch_plan.summary.path),
                summary_content,
            )
            navigation_files.append(branch_plan.summary.path)
    return {
        "task_id": context.task_id,
        "phase": "refresh_navigation",
        "navigation_files": navigation_files,
    }


def _render_planned_navigation_document(
    *,
    kind: str,
    scope_path: str,
    navigable_entries: list[dict],
    markdown_body: str,
) -> str:
    now = datetime.now(UTC).isoformat()
    title = f"{scope_path.rsplit('/', 1)[-1].replace('-', ' ').title()} {kind.title()}"
    metadata = {
        "schema_version": 1,
        "kind": kind,
        "scope_path": scope_path,
        "title": title,
        "created_at": now,
        "updated_at": now,
        "source": {"type": "planner_summary", "trace": f"generated_directory_{kind}"},
        "visibility": "internal",
        "status": "active",
        "target_token_range": "1000-2000" if kind == "overview" else "100-200",
        "entry_count": len(navigable_entries),
        "top_entries": [entry["title"] for entry in navigable_entries[:3]],
        "keywords": [entry["title"] for entry in navigable_entries[:3]],
    }
    return serialize_markdown_document(metadata=metadata, body=markdown_body.strip())
