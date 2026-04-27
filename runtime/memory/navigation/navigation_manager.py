from __future__ import annotations

import json
import logging
from datetime import datetime
from hashlib import sha256
from typing import Any

from component.storage.base_storage import storage_manager
from configs import config
from runtime.entities.llm_entities import ChatCompletionRequest
from runtime.memory.apply.patch import compute_content_sha256, parse_markdown_document
from runtime.memory.base.contracts import (
    DocumentMutationPlan,
    MemoryUpdateContext,
    MetadataRefreshResult,
    NavigationDocumentPlan,
    NavigationPlanningPreview,
    NavigationSummaryBranchPlan,
    NavigationSummaryResult,
    PatchPlanResult,
)
from runtime.memory.committed_tree import CommittedMemoryTree
from runtime.memory.navigation.common import (
    read_current_branch_files,
    read_existing_navigation_docs,
)
from runtime.memory.navigation.prompts import build_navigation_summary_messages
from runtime.memory.prepare_context.common import classify_branch_scope
from runtime.memory.schema.registry import normalize_memory_type
from runtime.model_manager import ModelManager

logger = logging.getLogger(__name__)


class NavigationManager:
    @classmethod
    def build_planning_preview_from_patch_plan(
        cls,
        *,
        task_id: str,
        patch_plan: PatchPlanResult,
    ) -> NavigationPlanningPreview:
        return NavigationPlanningPreview(
            task_id=task_id,
            navigation_targets=[item.model_copy(deep=True) for item in patch_plan.navigation_targets],
            document_previews=[
                item.model_copy(deep=True)
                for item in patch_plan.document_mutations
                if cls._is_navigation_source_document(item)
            ],
        )

    def generate_navigation_summary(
        self,
        *,
        update_ctx: MemoryUpdateContext,
        planning_preview: NavigationPlanningPreview,
    ) -> NavigationSummaryResult:
        return self.generate_navigation_summary_from_inputs(
            task_id=update_ctx.task_id,
            user_id=update_ctx.user_id,
            planning_preview=planning_preview,
        )

    @classmethod
    def generate_navigation_summary_from_inputs(
        cls,
        *,
        task_id: str,
        user_id: str | None,
        planning_preview: NavigationPlanningPreview,
    ) -> NavigationSummaryResult:
        mutation_lookup = {
            item.target_path: {"desired_content": item.desired_content}
            for item in planning_preview.document_previews
            if item.target_path
        }
        plans: list[NavigationSummaryBranchPlan] = []
        for target in planning_preview.navigation_targets:
            branch_path = target.branch_path
            existing_docs = read_existing_navigation_docs(branch_path)
            branch_files = read_current_branch_files(branch_path, mutation_lookup=mutation_lookup)
            raw = cls._invoke_navigation_model(
                messages=build_navigation_summary_messages(
                    task_id=task_id,
                    branch_path=branch_path,
                    existing_overview_md=existing_docs.get("overview_md"),
                    existing_summary_md=existing_docs.get("summary_md"),
                    branch_files=branch_files,
                ),
                user=user_id,
            )
            payload = cls._load_json_payload(raw)
            plans.append(
                cls._normalize_navigation_plan(
                    payload=payload,
                    branch_path=branch_path,
                    existing_overview_md=existing_docs.get("overview_md"),
                    existing_summary_md=existing_docs.get("summary_md"),
                )
            )
        return NavigationSummaryResult(
            task_id=task_id,
            navigation_mutations=plans,
            planner_error=None,
        )

    @staticmethod
    def _is_navigation_source_document(document_mutation: DocumentMutationPlan) -> bool:
        return document_mutation.document_family in {"memory", "project"}

    def refresh_metadata(
        self,
        *,
        update_ctx: MemoryUpdateContext,
        patch_plan: PatchPlanResult,
    ) -> MetadataRefreshResult:
        return self.refresh_metadata_from_inputs(task_id=update_ctx.task_id, patch_plan=patch_plan)

    @classmethod
    def refresh_metadata_from_inputs(
        cls,
        *,
        task_id: str,
        patch_plan: PatchPlanResult,
    ) -> MetadataRefreshResult:
        metadata_scopes = sorted({item.scope_path for item in patch_plan.metadata_targets})
        projection = {
            "scope_paths": metadata_scopes,
            "memory_index": [],
        }
        for scope_path in metadata_scopes:
            projection = cls._extend_scope_projection(projection=projection, scope_path=scope_path, task_id=task_id)
        cls._persist_metadata_projection(task_id=task_id, projection=projection)
        return MetadataRefreshResult(
            task_id=task_id,
            metadata_scopes=metadata_scopes,
            record_counts={key: len(value) for key, value in projection.items()},
        )

    @staticmethod
    def _invoke_navigation_model(*, messages: list, user: str | None) -> str:
        try:
            model_manager = ModelManager()
            model_instance = model_manager.get_planner_model_instance() or model_manager.get_default_model_instance(
                "llm"
            )
        except Exception as exc:
            logger.warning("navigation summary model unavailable: %s", exc)
            return ""
        if model_instance is None:
            return ""

        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=messages,
            temperature=0.0,
            stream=False,
        )
        response = model_instance.invoke_llm_sync(
            prompt_messages=request,
            user=user,
        )
        return str(response.message.content or "").strip()

    @staticmethod
    def _load_json_payload(raw_text: str) -> dict:
        text = str(raw_text or "").strip()
        if not text:
            raise ValueError("navigation summary output is empty")
        candidates = [text]
        start_index = text.find("{")
        end_index = text.rfind("}")
        if start_index != -1 and end_index != -1 and end_index > start_index:
            candidates.append(text[start_index : end_index + 1])
        for candidate in candidates:
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        raise ValueError("navigation summary output is not valid JSON")

    @classmethod
    def _normalize_navigation_plan(
        cls,
        *,
        payload: dict,
        branch_path: str,
        existing_overview_md: str | None,
        existing_summary_md: str | None,
    ) -> NavigationSummaryBranchPlan:
        plan = NavigationSummaryBranchPlan.model_validate(payload)
        if plan.branch_path != branch_path:
            raise ValueError(f"navigation summary branch_path mismatch: {plan.branch_path} != {branch_path}")
        cls._validate_document_plan(
            document_name="overview",
            plan=plan.overview,
            expected_path=f"{branch_path}/overview.md",
            existing_markdown=existing_overview_md,
        )
        cls._validate_document_plan(
            document_name="summary",
            plan=plan.summary,
            expected_path=f"{branch_path}/summary.md",
            existing_markdown=existing_summary_md,
        )
        return plan

    @staticmethod
    def _validate_document_plan(
        *,
        document_name: str,
        plan: NavigationDocumentPlan,
        expected_path: str,
        existing_markdown: str | None,
    ) -> None:
        if plan.path != expected_path:
            raise ValueError(f"{document_name} path mismatch: {plan.path} != {expected_path}")
        existing_body = None
        if existing_markdown is not None:
            _existing_metadata, existing_body = parse_markdown_document(existing_markdown)

        if plan.op == "noop":
            if plan.markdown_body.strip():
                raise ValueError(f"{document_name} noop must not include markdown_body")
            if plan.line_operations:
                raise ValueError(f"{document_name} noop must not include line_operations")
            return

        if plan.op == "write":
            if existing_markdown is not None:
                raise ValueError(f"{document_name} cannot write when existing markdown is present")
            if plan.based_on_existing:
                raise ValueError(f"{document_name} write cannot be based_on_existing")
            if not plan.markdown_body.strip():
                raise ValueError(f"{document_name} write requires markdown_body")
            if plan.line_operations:
                raise ValueError(f"{document_name} write must not include line_operations")
            return

        if existing_markdown is None:
            raise ValueError(f"{document_name} cannot edit without existing markdown")
        if not plan.based_on_existing:
            raise ValueError(f"{document_name} edit must declare based_on_existing")
        if plan.markdown_body.strip():
            raise ValueError(f"{document_name} edit must not include markdown_body")
        if not plan.line_operations:
            raise ValueError(f"{document_name} edit requires line_operations")
        if not plan.expected_body_sha256:
            raise ValueError(f"{document_name} edit requires expected_body_sha256")
        actual_body_sha256 = compute_content_sha256(str(existing_body or ""))
        if plan.expected_body_sha256 != actual_body_sha256:
            raise ValueError(
                f"{document_name} expected_body_sha256 mismatch: {plan.expected_body_sha256} != {actual_body_sha256}"
            )

    @classmethod
    def _extend_scope_projection(
        cls,
        *,
        projection: dict[str, list[dict]],
        scope_path: str,
        task_id: str,
    ) -> dict[str, list[dict]]:
        tree = CommittedMemoryTree.build_tree(path=scope_path, include_dirs=True, include_content=True, max_depth=None)
        files = [item for item in tree.get("tree") or [] if item["type"] == "file"]
        for file_item in files:
            path = file_item["path"]
            metadata, _body = parse_markdown_document(file_item.get("content") or "")
            projection["memory_index"].append(
                cls._build_memory_index_record(path=path, metadata=metadata, task_id=task_id)
            )
        return projection

    @classmethod
    def _build_memory_index_record(
        cls,
        *,
        path: str,
        metadata: dict[str, Any],
        task_id: str,
    ) -> dict[str, Any]:
        scope_type, user_id, agent_id = cls._resolve_scope(path)
        raw_content = storage_manager.read_text(cls._to_scoped_path(path))
        filename = path.rsplit("/", 1)[-1]
        return {
            "memory_id": metadata.get("memory_id") or f"mem_{sha256(path.encode('utf-8')).hexdigest()[:16]}",
            "memory_type": cls._resolve_memory_type(path),
            "memory_level": cls._resolve_memory_level(path),
            "user_id": user_id,
            "agent_id": agent_id,
            "project_id": metadata.get("project_id"),
            "scope_type": scope_type,
            "directory_path": path.rsplit("/", 1)[0],
            "file_path": path,
            "filename": filename,
            "status": metadata.get("status"),
            "tags": metadata.get("tags") or [],
            "file_sha256": compute_content_sha256(raw_content),
            "content_bytes": len(raw_content.encode("utf-8")),
            "projection_payload": metadata,
            "memory_created_at": metadata.get("created_at"),
            "memory_updated_at": metadata.get("updated_at"),
            "indexed_at": datetime.now().isoformat(),
            "refreshed_by_task_id": task_id,
        }

    @staticmethod
    def _resolve_scope(path: str) -> tuple[str, str | None, str | None]:
        parts = [part for part in path.split("/") if part]
        if len(parts) >= 2 and parts[0] == "users":
            return "user", parts[1], None
        if len(parts) >= 2 and parts[0] == "agent":
            return "agent", None, parts[1]
        return "unknown", None, None

    @staticmethod
    def _resolve_memory_type(path: str) -> str:
        branch_path = path.rsplit("/", 1)[0] if "/" in path else path
        _scope_type, memory_type = classify_branch_scope(branch_path)
        return normalize_memory_type(memory_type or "unknown")

    @staticmethod
    def _resolve_memory_level(path: str) -> str:
        if path.endswith("/overview.md"):
            return "l0"
        if path.endswith("/summary.md"):
            return "l1"
        return "l2"

    @staticmethod
    def _to_scoped_path(relative_path: str) -> str:
        return "/".join(part for part in [config.MEMORY_TREE_ROOT_DIR, relative_path] if part)

    @staticmethod
    def _persist_metadata_projection(*, task_id: str, projection: dict) -> None:
        from service.memory.repository import MemoryMetadataRepository

        MemoryMetadataRepository.persist_projection(task_id=task_id, projection=projection)
