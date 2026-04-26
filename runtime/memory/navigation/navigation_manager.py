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
    MemoryUpdateContext,
    MetadataRefreshResult,
    NavigationDocumentPlan,
    NavigationManagerResult,
    NavigationPatchPlanResult,
    NavigationRefreshResult,
    NavigationSummaryBranchPlan,
    NavigationSummaryResult,
    PatchApplyResult,
    PatchPlanResult,
    ResolveNavigationOperationsResult,
)
from runtime.memory.committed_tree import CommittedMemoryTree
from runtime.memory.navigation.common import (
    read_current_branch_files,
    read_existing_navigation_docs,
)
from runtime.memory.navigation.prompts import build_navigation_summary_messages
from runtime.model_manager import ModelManager

logger = logging.getLogger(__name__)


class NavigationManager:
    def generate_navigation_summary(
        self,
        *,
        update_ctx: MemoryUpdateContext,
        patch_plan: PatchPlanResult,
        patch_apply: PatchApplyResult | None = None,
    ) -> NavigationSummaryResult:
        return self.generate_navigation_summary_from_inputs(
            task_id=update_ctx.task_id,
            user_id=update_ctx.user_id,
            patch_plan=patch_plan,
            patch_apply=patch_apply,
        )

    @classmethod
    def generate_navigation_summary_from_inputs(
        cls,
        *,
        task_id: str,
        user_id: str | None,
        patch_plan: PatchPlanResult,
        patch_apply: PatchApplyResult | None = None,
    ) -> NavigationSummaryResult:
        mutation_lookup = {
            item.target_path: item.model_dump(mode="python", exclude_none=True)
            for item in patch_plan.memory_mutations
            if item.target_path
        }
        plans: list[NavigationSummaryBranchPlan] = []
        for target in patch_plan.navigation_targets:
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

    def build_navigation_patch_plan(
        self,
        *,
        update_ctx: MemoryUpdateContext,
        patch_plan: PatchPlanResult,
        summary_result: NavigationSummaryResult,
    ) -> tuple[ResolveNavigationOperationsResult, NavigationPatchPlanResult]:
        from runtime.memory.apply.memory_updater import MemoryUpdater

        resolve_result = MemoryUpdater.resolve_navigation_operations_from_inputs(
            task_id=update_ctx.task_id,
            patch_plan_result=patch_plan,
            navigation_summary_result=summary_result,
        )
        patch_plan_result = self.build_navigation_patch_plan_from_inputs(
            task_id=update_ctx.task_id,
            resolve_navigation_result=resolve_result,
        )
        return resolve_result, patch_plan_result

    @classmethod
    def build_navigation_patch_plan_from_inputs(
        cls,
        *,
        task_id: str,
        resolve_navigation_result: ResolveNavigationOperationsResult,
    ) -> NavigationPatchPlanResult:
        from runtime.memory.apply.patch_handler import PatchHandler

        return PatchHandler.build_navigation_staged_write_set_from_inputs(
            task_id=task_id,
            resolve_navigation_result=resolve_navigation_result,
        )

    def refresh_navigation(
        self,
        *,
        update_ctx: MemoryUpdateContext,
        patch_plan_result: NavigationPatchPlanResult,
    ) -> NavigationRefreshResult:
        return self.refresh_navigation_from_inputs(
            task_id=update_ctx.task_id,
            patch_plan_result=patch_plan_result,
        )

    @classmethod
    def refresh_navigation_from_inputs(
        cls,
        *,
        task_id: str,
        patch_plan_result: NavigationPatchPlanResult,
    ) -> NavigationRefreshResult:
        from runtime.memory.apply.patch_handler import PatchHandler

        return PatchHandler.apply_navigation_files_from_inputs(
            task_id=task_id,
            navigation_patch_plan=patch_plan_result,
        )

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
            "memory_directory_index": [],
            "memory_timeline_index": [],
            "memory_dedupe_index": [],
            "memory_retrieval_hint": [],
        }
        for scope_path in metadata_scopes:
            projection = cls._extend_scope_projection(projection=projection, scope_path=scope_path, task_id=task_id)
        cls._persist_metadata_projection(task_id=task_id, projection=projection)
        return MetadataRefreshResult(
            task_id=task_id,
            metadata_scopes=metadata_scopes,
            record_counts={key: len(value) for key, value in projection.items()},
        )

    def run(
        self,
        *,
        update_ctx: MemoryUpdateContext,
        patch_plan: PatchPlanResult,
        patch_apply: PatchApplyResult,
    ) -> NavigationManagerResult:
        summary_result = self.generate_navigation_summary(
            update_ctx=update_ctx,
            patch_plan=patch_plan,
            patch_apply=patch_apply,
        )
        resolve_result, patch_plan_result = self.build_navigation_patch_plan(
            update_ctx=update_ctx,
            patch_plan=patch_plan,
            summary_result=summary_result,
        )
        refresh_result = self.refresh_navigation_from_inputs(
            task_id=update_ctx.task_id,
            patch_plan_result=patch_plan_result,
        )
        metadata_result = self.refresh_metadata(update_ctx=update_ctx, patch_plan=patch_plan)
        return NavigationManagerResult(
            summary_result=summary_result,
            resolve_result=resolve_result,
            patch_plan_result=patch_plan_result,
            refresh_result=refresh_result,
            metadata_result=metadata_result,
        )

    @staticmethod
    def _invoke_navigation_model(*, messages: list, user: str | None) -> str:
        try:
            model_manager = ModelManager()
            model_instance = (
                model_manager.get_planner_model_instance() or model_manager.get_default_model_instance("llm")
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
        directories = [item for item in tree.get("tree") or [] if item["type"] == "dir"]
        for file_item in files:
            path = file_item["path"]
            if path.endswith("overview.md") or path.endswith("summary.md"):
                continue
            metadata, body = parse_markdown_document(file_item.get("content") or "")
            projection["memory_index"].append(
                cls._build_memory_index_record(path=path, metadata=metadata, body=body, task_id=task_id)
            )
            projection["memory_dedupe_index"].append(
                cls._build_dedupe_record(path=path, metadata=metadata, body=body, task_id=task_id)
            )
            projection["memory_retrieval_hint"].append(
                cls._build_retrieval_hint_record(path=path, metadata=metadata, body=body, task_id=task_id)
            )
            timeline_record = cls._build_timeline_record(path=path, metadata=metadata, task_id=task_id)
            if timeline_record:
                projection["memory_timeline_index"].append(timeline_record)
        all_directories = {scope_path, *[item["path"] for item in directories]}
        for directory_path in sorted(all_directories):
            projection["memory_directory_index"].append(
                cls._build_directory_index_record(directory_path=directory_path, task_id=task_id)
            )
        return projection

    @classmethod
    def _build_memory_index_record(
        cls,
        *,
        path: str,
        metadata: dict[str, Any],
        body: str,
        task_id: str,
    ) -> dict[str, Any]:
        scope_type, user_id, agent_id = cls._resolve_scope(path)
        memory_class = cls._resolve_memory_class(path)
        raw_content = storage_manager.read_text(cls._to_scoped_path(path))
        return {
            "memory_id": metadata.get("memory_id") or f"mem_{sha256(path.encode('utf-8')).hexdigest()[:16]}",
            "memory_class": memory_class,
            "kind": metadata.get("kind") or memory_class,
            "user_id": user_id,
            "agent_id": agent_id,
            "project_id": metadata.get("project_id"),
            "scope_type": scope_type,
            "scope_path": cls._scope_path_for_file(path),
            "directory_path": path.rsplit("/", 1)[0],
            "file_path": path,
            "title": metadata.get("title") or path.rsplit("/", 1)[-1],
            "topic": metadata.get("topic") or metadata.get("tool_name") or metadata.get("subject"),
            "source_type": cls._extract_source_type(metadata),
            "visibility": metadata.get("visibility"),
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

    @classmethod
    def _build_directory_index_record(cls, *, directory_path: str, task_id: str) -> dict[str, Any]:
        scoped_path = cls._to_scoped_path(directory_path)
        entries = storage_manager.list_dir(scoped_path, recursive=False)
        memory_files = [
            entry
            for entry in entries
            if entry.is_file and not entry.path.endswith("overview.md") and not entry.path.endswith("summary.md")
        ]
        overview_path = f"{directory_path}/overview.md"
        summary_path = f"{directory_path}/summary.md"
        scope_type, user_id, agent_id = cls._resolve_scope(directory_path)
        return {
            "user_id": user_id,
            "agent_id": agent_id,
            "project_id": None,
            "scope_type": scope_type,
            "scope_path": cls._scope_path_for_directory(directory_path),
            "directory_path": directory_path,
            "parent_directory_path": directory_path.rsplit("/", 1)[0] if "/" in directory_path else None,
            "memory_class": cls._resolve_memory_class(directory_path),
            "directory_kind": directory_path.split("/", 3)[-1],
            "title": directory_path.rsplit("/", 1)[-1].replace("-", " ").title(),
            "overview_path": overview_path if storage_manager.exists(cls._to_scoped_path(overview_path)) else None,
            "summary_path": summary_path if storage_manager.exists(cls._to_scoped_path(summary_path)) else None,
            "memory_entry_count": len(memory_files),
            "child_directory_count": len([entry for entry in entries if entry.is_dir]),
            "latest_memory_updated_at": None,
            "projection_payload": {"entry_names": [entry.path.rsplit("/", 1)[-1] for entry in entries]},
            "refreshed_at": datetime.now().isoformat(),
            "refreshed_by_task_id": task_id,
        }

    @classmethod
    def _build_timeline_record(cls, *, path: str, metadata: dict[str, Any], task_id: str) -> dict[str, Any] | None:
        kind = str(metadata.get("kind") or "").strip()
        time_field = None
        for candidate in (
            "event_time",
            "task_time",
            "verification_time",
            "review_time",
            "deploy_time",
            "incident_time",
            "rollback_time",
        ):
            if metadata.get(candidate):
                time_field = candidate
                break
        if not time_field:
            return None
        scope_type, user_id, agent_id = cls._resolve_scope(path)
        return {
            "memory_id": metadata.get("memory_id") or f"mem_{sha256(path.encode('utf-8')).hexdigest()[:16]}",
            "user_id": user_id,
            "agent_id": agent_id,
            "project_id": metadata.get("project_id"),
            "memory_class": cls._resolve_memory_class(path),
            "kind": kind,
            "timeline_kind": kind,
            "file_path": path,
            "title": metadata.get("title") or path.rsplit("/", 1)[-1],
            "sort_at": metadata.get(time_field),
            "happened_at": metadata.get(time_field),
            "result_status": metadata.get("status"),
            "projection_payload": metadata,
            "indexed_at": datetime.now().isoformat(),
            "refreshed_by_task_id": task_id,
        }

    @classmethod
    def _build_dedupe_record(cls, *, path: str, metadata: dict[str, Any], body: str, task_id: str) -> dict[str, Any]:
        scope_type, user_id, agent_id = cls._resolve_scope(path)
        title = str(metadata.get("title") or path.rsplit("/", 1)[-1]).strip().lower()
        return {
            "memory_id": metadata.get("memory_id") or f"mem_{sha256(path.encode('utf-8')).hexdigest()[:16]}",
            "user_id": user_id,
            "agent_id": agent_id,
            "project_id": metadata.get("project_id"),
            "memory_class": cls._resolve_memory_class(path),
            "kind": metadata.get("kind") or cls._resolve_memory_class(path),
            "file_path": path,
            "dedupe_scope_path": cls._scope_path_for_file(path),
            "title_norm": title,
            "semantic_key": metadata.get("topic") or metadata.get("tool_name") or title,
            "content_sha256": compute_content_sha256(body),
            "fingerprint_version": "v1",
            "fingerprint_payload": {"title": title, "body_len": len(body)},
            "indexed_at": datetime.now().isoformat(),
            "refreshed_by_task_id": task_id,
        }

    @classmethod
    def _build_retrieval_hint_record(
        cls,
        *,
        path: str,
        metadata: dict[str, Any],
        body: str,
        task_id: str,
    ) -> dict[str, Any]:
        scope_type, user_id, agent_id = cls._resolve_scope(path)
        title = str(metadata.get("title") or path.rsplit("/", 1)[-1]).strip()
        primary_topic = metadata.get("topic") or metadata.get("tool_name") or metadata.get("subject") or title
        return {
            "memory_id": metadata.get("memory_id") or f"mem_{sha256(path.encode('utf-8')).hexdigest()[:16]}",
            "user_id": user_id,
            "agent_id": agent_id,
            "project_id": metadata.get("project_id"),
            "memory_class": cls._resolve_memory_class(path),
            "kind": metadata.get("kind") or cls._resolve_memory_class(path),
            "file_path": path,
            "title": title,
            "primary_topic": primary_topic,
            "body_summary": body[:200],
            "tags": metadata.get("tags") or [],
            "aliases": [],
            "entity_refs": [],
            "keywords": [keyword for keyword in {title, primary_topic} if keyword],
            "query_hints": [primary_topic] if primary_topic else [],
            "importance_score": None,
            "freshness_at": metadata.get("updated_at"),
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
    def _resolve_memory_class(path: str) -> str:
        parts = [part for part in path.split("/") if part]
        if len(parts) >= 4 and parts[0] == "users" and parts[2] == "memories":
            return parts[3]
        if len(parts) >= 4 and parts[0] == "agent" and parts[2] == "memories":
            return parts[3]
        return "unknown"

    @staticmethod
    def _scope_path_for_file(path: str) -> str:
        parts = [part for part in path.split("/") if part]
        if len(parts) >= 4 and parts[0] == "users" and parts[2] == "memories":
            return "/".join(parts[:4])
        if len(parts) >= 4 and parts[0] == "agent" and parts[2] == "memories":
            return "/".join(parts[:4])
        return path.rsplit("/", 1)[0]

    @staticmethod
    def _scope_path_for_directory(path: str) -> str:
        parts = [part for part in path.split("/") if part]
        if len(parts) >= 4 and parts[0] == "users" and parts[2] == "memories":
            return "/".join(parts[:4])
        if len(parts) >= 4 and parts[0] == "agent" and parts[2] == "memories":
            return "/".join(parts[:4])
        if len(parts) >= 3 and parts[0] == "users" and parts[2] == "project":
            return "/".join(parts[:3])
        return path

    @staticmethod
    def _extract_source_type(metadata: dict[str, Any]) -> str | None:
        source = metadata.get("source")
        if isinstance(source, dict):
            return source.get("type")
        return None

    @staticmethod
    def _to_scoped_path(relative_path: str) -> str:
        return "/".join(part for part in [config.MEMORY_TREE_ROOT_DIR, relative_path] if part)

    @staticmethod
    def _persist_metadata_projection(*, task_id: str, projection: dict) -> None:
        from service.memory.repository import MemoryMetadataRepository

        MemoryMetadataRepository.persist_projection(task_id=task_id, projection=projection)
