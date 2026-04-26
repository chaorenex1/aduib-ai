from __future__ import annotations

import logging
from typing import Any

from component.storage.base_storage import storage_manager
from configs import config
from runtime.entities.llm_entities import ChatCompletionRequest
from runtime.memory.apply.patch import apply_line_operations_to_body, compute_content_sha256, parse_markdown_document
from runtime.memory.base.contracts import (
    DocumentMutationPlan,
    MemoryLineOperation,
    MemorySourceRef,
    NavigationPlanningPreview,
    NavigationTarget,
    PatchPlanResult,
)
from runtime.memory.project.context import ProjectMemoryContextBuilder
from runtime.memory.project.contracts import ProjectDocumentPlan, ProjectMemoryPlan, ProjectMemoryScope
from runtime.memory.project.errors import ProjectPayloadError
from runtime.memory.project.path_rules import build_docs_target_path, build_snippets_target_path
from runtime.memory.project.prompts import build_docs_classification_messages, build_snippets_classification_messages
from runtime.memory.project.structured_output import (
    load_json_payload,
    normalize_docs_inference,
    normalize_snippets_inference,
)
from runtime.model_manager import ModelManager

logger = logging.getLogger(__name__)


class ProjectMemoryManager:
    """
    Domain coordinator for:

    - users/<user-id>/project/docs/<project-id>/
    - users/<user-id>/project/snippets/
    - users/<user-id>/project/overview.md
    - users/<user-id>/project/summary.md

    This manager is LLM-first for docs/snippets inference and intentionally
    does not silently fall back to deterministic path guesses. If inference
    cannot be produced, the task should fail loudly so callers can inspect
    the prompt/model behavior instead of writing content to unstable paths.
    """

    def __init__(self, *, context_builder: ProjectMemoryContextBuilder | None = None) -> None:
        self.context_builder = context_builder or ProjectMemoryContextBuilder()

    def build_scope(
        self,
        *,
        user_id: str,
        project_id: str,
    ) -> ProjectMemoryScope:
        root_path = f"users/{user_id}/project"
        docs_root_path = f"{root_path}/docs"
        project_docs_path = f"{docs_root_path}/{project_id}"
        snippets_path = f"{root_path}/snippets"
        return ProjectMemoryScope(
            user_id=user_id,
            project_id=project_id,
            root_path=root_path,
            docs_root_path=docs_root_path,
            project_docs_path=project_docs_path,
            snippets_path=snippets_path,
            overview_path=f"{root_path}/overview.md",
            summary_path=f"{root_path}/summary.md",
        )

    def plan_import(
        self,
        *,
        scope: ProjectMemoryScope,
        source_ref: MemorySourceRef,
    ) -> ProjectMemoryPlan:
        payload = self._require_project_payload(source_ref)
        raw_items = payload.get("items") or []

        document_plans = [self._plan_single_item(scope=scope, item=item) for item in raw_items]
        navigation_targets = [
            NavigationTarget(
                branch_path=scope.root_path,
                overview_path=scope.overview_path,
                summary_path=scope.summary_path,
            )
        ]
        return ProjectMemoryPlan(
            scope=scope,
            document_plans=document_plans,
            navigation_targets=navigation_targets,
        )

    def build_navigation_preview(
        self,
        *,
        plan: ProjectMemoryPlan,
        patch_plan: PatchPlanResult,
    ) -> NavigationPlanningPreview:
        memory_document_previews = [
            item.model_copy(deep=True)
            for item in patch_plan.document_mutations
            if item.document_family == "memory" and self._is_under_project_root(item.target_path, scope=plan.scope)
        ]
        return NavigationPlanningPreview(
            task_id=patch_plan.task_id,
            navigation_targets=plan.navigation_targets,
            memory_document_previews=memory_document_previews,
        )

    def build_navigation_preview_from_plan(
        self,
        *,
        task_id: str,
        plan: ProjectMemoryPlan,
    ) -> NavigationPlanningPreview:
        memory_document_previews = [
            DocumentMutationPlan(
                document_family="memory",
                document_kind=item.target_family,
                op="write" if item.op == "noop" else item.op,
                target_path=item.target_path,
                file_exists=item.based_on_existing,
                desired_content=self._preview_content_from_plan(item),
                metadata={
                    **dict(item.inference_notes),
                    "topic": item.topic,
                    "category": item.category,
                    "domain": item.domain,
                    "implementation": item.implementation,
                },
            )
            for item in plan.document_plans
            if item.op != "noop"
        ]
        return NavigationPlanningPreview(
            task_id=task_id,
            navigation_targets=plan.navigation_targets,
            memory_document_previews=memory_document_previews,
        )

    def _plan_single_item(
        self,
        *,
        scope: ProjectMemoryScope,
        item: dict[str, Any],
    ) -> ProjectDocumentPlan:
        item_type = str(item.get("item_type") or "").strip()
        title = str(item.get("title") or "").strip()
        if not item_type:
            raise ProjectPayloadError("project item missing item_type")
        if not title:
            raise ProjectPayloadError("project item missing title")

        if self._is_snippet_item(item):
            inference = self._infer_snippet_location(scope=scope, item=item)
            target_path = build_snippets_target_path(
                snippets_path=scope.snippets_path,
                domain=inference["domain"],
                topic=inference["topic"],
                category=inference["category"],
            )
            return self._build_project_document_plan(
                title=title,
                target_family="snippets",
                target_path=target_path,
                topic=inference["topic"],
                category=inference["category"],
                domain=inference["domain"],
                implementation=inference["implementation"],
                source_payload=item,
                inference_notes=inference,
                reasoning="snippet planned from llm inference",
            )

        inference = self._infer_docs_location(scope=scope, item=item)
        target_path = build_docs_target_path(
            project_docs_path=scope.project_docs_path,
            topic=inference["topic"],
            category=inference["category"],
        )
        return self._build_project_document_plan(
            title=title,
            target_family="docs",
            target_path=target_path,
            topic=inference["topic"],
            category=inference["category"],
            source_payload=item,
            inference_notes=inference,
            reasoning="project doc planned from llm inference",
        )

    def _require_project_payload(self, source_ref: MemorySourceRef) -> dict[str, Any]:
        if source_ref.type != "project_memory_import":
            raise ProjectPayloadError(f"unsupported source_ref.type for project import: {source_ref.type}")
        payload = source_ref.project_payload or {}
        if not isinstance(payload, dict):
            raise ProjectPayloadError("project_payload must be an object")
        return payload

    @staticmethod
    def _is_snippet_item(item: dict[str, Any]) -> bool:
        item_type = str(item.get("item_type") or "").strip().lower()
        return item_type == "snippet" or bool(item.get("snippet_type"))

    def _infer_docs_location(
        self,
        *,
        scope: ProjectMemoryScope,
        item: dict[str, Any],
    ) -> dict[str, str]:
        context = self.context_builder.build_docs_context(scope=scope, item=item)
        return self._invoke_docs_inference(context=context)

    def _infer_snippet_location(
        self,
        *,
        scope: ProjectMemoryScope,
        item: dict[str, Any],
    ) -> dict[str, str]:
        context = self.context_builder.build_snippets_context(scope=scope, item=item)
        return self._invoke_snippets_inference(context=context)

    def _invoke_docs_inference(self, *, context: dict[str, Any]) -> dict[str, str]:
        raw = self._invoke_project_model(messages=build_docs_classification_messages(context=context))
        if not raw:
            raise ProjectPayloadError("docs inference returned empty output")
        return normalize_docs_inference(load_json_payload(raw))

    def _invoke_snippets_inference(self, *, context: dict[str, Any]) -> dict[str, str]:
        raw = self._invoke_project_model(messages=build_snippets_classification_messages(context=context))
        if not raw:
            raise ProjectPayloadError("snippets inference returned empty output")
        return normalize_snippets_inference(load_json_payload(raw))

    @staticmethod
    def _invoke_project_model(*, messages: list) -> str:
        try:
            model_manager = ModelManager()
            model_instance = model_manager.get_planner_model_instance() or model_manager.get_default_model_instance(
                "llm"
            )
        except Exception as exc:
            logger.warning("project inference model unavailable: %s", exc)
            return ""
        if model_instance is None:
            return ""

        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=messages,
            temperature=0.0,
            stream=False,
        )
        try:
            response = model_instance.invoke_llm_sync(prompt_messages=request, user=None)
        except Exception as exc:
            logger.warning("project inference model invocation failed: %s", exc)
            return ""
        return str(response.message.content or "").strip()

    @staticmethod
    def _is_under_project_root(target_path: str, *, scope: ProjectMemoryScope) -> bool:
        normalized = str(target_path or "").strip("/")
        root = str(scope.root_path or "").strip("/")
        return normalized == root or normalized.startswith(root + "/")

    @staticmethod
    def _preview_content_from_item(item: dict[str, Any]) -> str:
        parts = item.get("content_parts") or []
        texts = [
            str(part.get("text") or "").strip()
            for part in parts
            if isinstance(part, dict) and str(part.get("type") or "").strip() == "text"
        ]
        title = str(item.get("title") or "").strip()
        return "\n\n".join(part for part in [title, *texts] if part).strip()

    def _preview_content_from_plan(self, plan: ProjectDocumentPlan) -> str:
        if plan.op == "write":
            return plan.markdown_body
        scoped_path = self._to_scoped_path(plan.target_path)
        previous_content = storage_manager.read_text(scoped_path) if self._storage_exists(scoped_path) else ""
        _metadata, previous_body = parse_markdown_document(previous_content)
        return apply_line_operations_to_body(previous_body, plan.line_operations).strip()

    def _build_project_document_plan(
        self,
        *,
        title: str,
        target_family: str,
        target_path: str,
        source_payload: dict[str, Any],
        inference_notes: dict[str, Any],
        reasoning: str,
        topic: str | None = None,
        category: str | None = None,
        domain: str | None = None,
        implementation: str | None = None,
    ) -> ProjectDocumentPlan:
        scoped_path = self._to_scoped_path(target_path)
        file_exists = self._storage_exists(scoped_path)
        previous_content = storage_manager.read_text(scoped_path) if file_exists else ""
        _metadata, previous_body = parse_markdown_document(previous_content)
        markdown_body = ""
        line_operations: list[MemoryLineOperation] = []
        if file_exists:
            line_operations = (
                self._build_snippet_line_operations(
                    title=title,
                    implementation=str(implementation or "general"),
                    source_payload=source_payload,
                    previous_body=previous_body,
                )
                if target_family == "snippets"
                else self._build_docs_line_operations(
                    title=title,
                    source_payload=source_payload,
                    previous_body=previous_body,
                )
            )
            op = "edit"
            based_on_existing = True
            expected_body_sha256 = compute_content_sha256(previous_body)
        else:
            markdown_body = (
                self._build_snippet_markdown_body(
                    title=title,
                    implementation=str(implementation or "general"),
                    source_payload=source_payload,
                )
                if target_family == "snippets"
                else self._build_docs_markdown_body(
                    title=title,
                    source_payload=source_payload,
                )
            )
            op = "write"
            based_on_existing = False
            expected_body_sha256 = None
        return ProjectDocumentPlan(
            target_family=target_family,  # type: ignore[arg-type]
            op=op,
            target_path=target_path,
            title=title,
            based_on_existing=based_on_existing,
            topic=topic,
            category=category,
            domain=domain,
            implementation=implementation,
            markdown_body=markdown_body,
            line_operations=line_operations,
            expected_body_sha256=expected_body_sha256,
            source_payload=source_payload,
            reasoning=reasoning,
            inference_notes=inference_notes,
        )

    @staticmethod
    def _build_docs_markdown_body(*, title: str, source_payload: dict[str, Any]) -> str:
        content = ProjectMemoryManager._source_payload_text(source_payload)
        body = "\n\n".join(part for part in [f"# {title}", f"## {title}", content] if part).strip()
        return body + "\n"

    @staticmethod
    def _build_snippet_markdown_body(*, title: str, implementation: str, source_payload: dict[str, Any]) -> str:
        content = ProjectMemoryManager._source_payload_text(source_payload)
        body = "\n\n".join(part for part in [f"# {title}", f"## {implementation}", content] if part).strip()
        return body + "\n"

    @staticmethod
    def _build_docs_line_operations(
        *,
        title: str,
        source_payload: dict[str, Any],
        previous_body: str,
    ) -> list[MemoryLineOperation]:
        return ProjectMemoryManager._build_section_line_operations(
            section_title=title,
            content=ProjectMemoryManager._source_payload_text(source_payload),
            previous_body=previous_body,
        )

    @staticmethod
    def _build_snippet_line_operations(
        *,
        title: str,
        implementation: str,
        source_payload: dict[str, Any],
        previous_body: str,
    ) -> list[MemoryLineOperation]:
        return ProjectMemoryManager._build_section_line_operations(
            section_title=implementation,
            content=ProjectMemoryManager._source_payload_text(source_payload),
            previous_body=previous_body,
        )

    @staticmethod
    def _build_section_line_operations(
        *,
        section_title: str,
        content: str,
        previous_body: str,
    ) -> list[MemoryLineOperation]:
        section_heading = f"## {section_title}".strip()
        lines = str(previous_body or "").splitlines()
        start_index = None
        end_index = None
        for index, line in enumerate(lines):
            if line.strip() == section_heading:
                start_index = index
                end_index = index
                scan = index + 1
                while scan < len(lines) and not lines[scan].strip().startswith("## "):
                    end_index = scan
                    scan += 1
                break

        new_text = "\n\n".join(part for part in [section_heading, content] if part).strip()
        if start_index is None:
            return [
                MemoryLineOperation(
                    kind="append_eof",
                    new_text=new_text,
                    reasoning="append new section to existing category file",
                )
            ]
        return [
            MemoryLineOperation(
                kind="replace_range",
                start_line=start_index + 1,
                end_line=(end_index or start_index) + 1,
                new_text=new_text,
                reasoning="replace existing section with updated content",
            )
        ]

    @staticmethod
    def _source_payload_text(item: dict[str, Any]) -> str:
        parts = item.get("content_parts") or []
        texts = [
            str(part.get("text") or "").strip()
            for part in parts
            if isinstance(part, dict) and str(part.get("type") or "").strip() == "text"
        ]
        return "\n\n".join(text for text in texts if text).strip()

    @staticmethod
    def _to_scoped_path(relative_path: str) -> str:
        return "/".join(part for part in [config.MEMORY_TREE_ROOT_DIR, relative_path] if part)

    @staticmethod
    def _storage_exists(path: str) -> bool:
        try:
            return storage_manager.exists(path)
        except RuntimeError:
            return False
