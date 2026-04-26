from __future__ import annotations

import json
from pathlib import Path
from string import Formatter
from typing import Any

from component.storage.base_storage import storage_manager
from configs import config
from runtime.memory.apply.patch import compute_content_sha256, parse_markdown_document
from runtime.memory.apply.patch_handler import PatchHandler
from runtime.memory.base.contracts import (
    ExtractedMemoryFieldPlan,
    ExtractedMemoryOperation,
    MemoryChangePlanItem,
    MemoryCommittedResult,
    MemoryUpdateContext,
    NavigationDocumentPlan,
    NavigationManagerResult,
    NavigationSummaryResult,
    PatchApplyResult,
    PatchPlanResult,
    PlannerToolUseResult,
    PreparedExtractContext,
    ResolvedMemoryFieldPlan,
    ResolvedMemoryOperation,
    ResolvedNavigationOperation,
    ResolveNavigationOperationsResult,
    ResolveOperationsResult,
)
from runtime.memory.base.enums import MemoryTaskPhase
from runtime.memory.navigation.navigation_manager import NavigationManager
from runtime.memory.schema.registry import MemorySchemaDefinition, MemorySchemaRegistry
from service.memory.base.paths import normalize_path_segment


class MemoryUpdater:
    def __init__(
        self,
        update_ctx: MemoryUpdateContext,
        *,
        patch_handler: PatchHandler | None = None,
        navigation_manager: NavigationManager | None = None,
    ) -> None:
        self.update_ctx = update_ctx
        self.patch_handler = patch_handler or PatchHandler()
        self.navigation_manager = navigation_manager or NavigationManager()

    def resolve_operations(self) -> ResolveOperationsResult:
        return self.resolve_operations_from_inputs(
            task_id=self.update_ctx.task_id,
            prepared_context=self.update_ctx.prepared_context,
            change_plan=self.update_ctx.extract_result.change_plan,
            extracted_operations=self.update_ctx.extract_result.structured_operations,
            tools_used=[
                item.model_dump(mode="python", exclude_none=True) for item in self.update_ctx.extract_result.tools_used
            ],
        )

    def resolve_navigation_operations(
        self,
        *,
        patch_plan_result: PatchPlanResult,
        navigation_summary_result: NavigationSummaryResult,
    ) -> ResolveNavigationOperationsResult:
        return self.resolve_navigation_operations_from_inputs(
            task_id=self.update_ctx.task_id,
            patch_plan_result=patch_plan_result,
            navigation_summary_result=navigation_summary_result,
        )

    @classmethod
    def resolve_operations_from_inputs(
        cls,
        *,
        task_id: str,
        prepared_context: PreparedExtractContext,
        change_plan: list[MemoryChangePlanItem],
        extracted_operations: list[ExtractedMemoryOperation],
        tools_used: list[dict[str, Any]],
    ) -> ResolveOperationsResult:
        planned_operations = cls._validate_operations_match_change_plan(
            change_plan=change_plan,
            operations=extracted_operations,
        )
        registry = MemorySchemaRegistry.load()
        resolved_operations = cls._resolve_all_operations(
            operations=extracted_operations,
            planned_operations=planned_operations,
            registry=registry,
            prepared=prepared_context,
        )
        cls._validate_edit_operations_have_prior_reads(
            resolved_operations=resolved_operations,
            prepared=prepared_context,
            tools_used=tools_used,
        )
        cls._validate_edit_patch_field_plans(
            resolved_operations=resolved_operations,
        )
        navigation_scopes = sorted(
            {str(Path(item.target_path).parent).replace("\\", "/") for item in resolved_operations}
        )
        metadata_scopes = sorted(
            {
                item.target_path.split("/", 3)[0] + "/" + item.target_path.split("/", 3)[1]
                for item in resolved_operations
                if "/" in item.target_path
            }
        )
        return ResolveOperationsResult(
            task_id=task_id,
            resolved_operations=resolved_operations,
            navigation_scopes=navigation_scopes,
            metadata_scopes=metadata_scopes,
        )

    @classmethod
    def resolve_navigation_operations_from_inputs(
        cls,
        *,
        task_id: str,
        patch_plan_result: PatchPlanResult,
        navigation_summary_result: NavigationSummaryResult,
    ) -> ResolveNavigationOperationsResult:
        resolved_navigation_operations: list[ResolvedNavigationOperation] = []
        allowed_paths = {
            target.overview_path
            for target in patch_plan_result.navigation_targets
        } | {
            target.summary_path
            for target in patch_plan_result.navigation_targets
        }
        for branch_plan in navigation_summary_result.navigation_mutations:
            resolved_navigation_operations.extend(
                item
                for item in (
                    cls._resolve_single_navigation_document(
                        branch_path=branch_plan.branch_path,
                        document_kind="overview",
                        document_plan=branch_plan.overview,
                        allowed_paths=allowed_paths,
                    ),
                    cls._resolve_single_navigation_document(
                        branch_path=branch_plan.branch_path,
                        document_kind="summary",
                        document_plan=branch_plan.summary,
                        allowed_paths=allowed_paths,
                    ),
                )
                if item is not None
            )
        return ResolveNavigationOperationsResult(
            task_id=task_id,
            resolved_navigation_operations=resolved_navigation_operations,
        )

    def commit(
        self,
        *,
        resolve_result: ResolveOperationsResult,
        patch_plan_result: PatchPlanResult,
        patch_apply_result: PatchApplyResult,
        navigation_result: NavigationManagerResult,
    ) -> MemoryCommittedResult:
        return MemoryCommittedResult(
            task_id=self.update_ctx.task_id,
            extract_result=self.update_ctx.extract_result,
            resolve_result=resolve_result,
            patch_plan_result=patch_plan_result,
            patch_apply_result=patch_apply_result,
            navigation_result=navigation_result,
            journal_ref=patch_apply_result.journal_ref,
            rollback_metadata=patch_apply_result.rollback_metadata,
            final_stage="committed",
        )

    @staticmethod
    def _resolve_single_navigation_document(
        *,
        branch_path: str,
        document_kind: str,
        document_plan: NavigationDocumentPlan,
        allowed_paths: set[str],
    ) -> ResolvedNavigationOperation | None:
        if document_plan.op == "noop":
            return None

        expected_path = f"{branch_path}/{document_kind}.md"
        if document_plan.path != expected_path:
            raise ValueError(f"navigation document path mismatch: {document_plan.path} != {expected_path}")
        if allowed_paths and document_plan.path not in allowed_paths:
            raise ValueError(f"navigation document path not present in patch plan targets: {document_plan.path}")

        scoped_path = "/".join(part for part in [config.MEMORY_TREE_ROOT_DIR, document_plan.path] if part)
        file_exists = storage_manager.exists(scoped_path)
        previous_content = storage_manager.read_text(scoped_path) if file_exists else None
        previous_metadata, previous_body = parse_markdown_document(previous_content or "")

        MemoryUpdater._validate_navigation_document_plan(
            document_kind=document_kind,
            document_plan=document_plan,
            file_exists=file_exists,
            previous_body=previous_body,
        )

        return ResolvedNavigationOperation(
            document_kind=document_kind,
            op=document_plan.op,
            target_path=document_plan.path,
            branch_path=branch_path,
            file_exists=file_exists,
            based_on_existing=document_plan.based_on_existing,
            previous_content=previous_content,
            previous_metadata=previous_metadata,
            previous_body=previous_body,
            markdown_body=document_plan.markdown_body or None,
            line_operations=list(document_plan.line_operations),
            expected_body_sha256=document_plan.expected_body_sha256,
        )

    @staticmethod
    def _validate_navigation_document_plan(
        *,
        document_kind: str,
        document_plan: NavigationDocumentPlan,
        file_exists: bool,
        previous_body: str,
    ) -> None:
        if document_plan.op == "write":
            if file_exists:
                raise ValueError(f"{document_kind} write cannot target an existing document")
            if document_plan.based_on_existing:
                raise ValueError(f"{document_kind} write cannot be based_on_existing")
            if not document_plan.markdown_body.strip():
                raise ValueError(f"{document_kind} write requires markdown_body")
            if document_plan.line_operations:
                raise ValueError(f"{document_kind} write must not include line_operations")
            return

        if not file_exists:
            raise ValueError(f"{document_kind} edit requires an existing document")
        if not document_plan.based_on_existing:
            raise ValueError(f"{document_kind} edit must declare based_on_existing")
        if document_plan.markdown_body.strip():
            raise ValueError(f"{document_kind} edit must not include markdown_body")
        if not document_plan.line_operations:
            raise ValueError(f"{document_kind} edit requires line_operations")
        if not document_plan.expected_body_sha256:
            raise ValueError(f"{document_kind} edit requires expected_body_sha256")
        actual_body_sha256 = compute_content_sha256(previous_body)
        if document_plan.expected_body_sha256 != actual_body_sha256:
            raise ValueError(
                f"{document_kind} body sha256 mismatch: {document_plan.expected_body_sha256} != {actual_body_sha256}"
            )

    def run(self) -> MemoryCommittedResult:
        resolve_result = self.resolve_operations()
        patch_plan_result, patch_apply_result = self.patch_handler.run(
            update_ctx=self.update_ctx,
            resolve_result=resolve_result,
        )
        try:
            navigation_summary_result = self.navigation_manager.generate_navigation_summary(
                update_ctx=self.update_ctx,
                patch_plan=patch_plan_result,
                patch_apply=patch_apply_result,
            )
            resolve_navigation_result = self.resolve_navigation_operations(
                patch_plan_result=patch_plan_result,
                navigation_summary_result=navigation_summary_result,
            )
            navigation_patch_plan_result = self.patch_handler.build_navigation_staged_write_set(
                update_ctx=self.update_ctx,
                resolve_navigation_result=resolve_navigation_result,
            )
            navigation_refresh_result = self.patch_handler.apply_navigation_files(
                update_ctx=self.update_ctx,
                navigation_patch_plan=navigation_patch_plan_result,
            )
            metadata_result = self.navigation_manager.refresh_metadata(
                update_ctx=self.update_ctx,
                patch_plan=patch_plan_result,
            )
            navigation_result = NavigationManagerResult(
                summary_result=navigation_summary_result,
                resolve_result=resolve_navigation_result,
                patch_plan_result=navigation_patch_plan_result,
                refresh_result=navigation_refresh_result,
                metadata_result=metadata_result,
            )
        except Exception as exc:
            raise RuntimeError(
                json.dumps(
                    {
                        "phase": str(MemoryTaskPhase.MEMORY_UPDATER),
                        "journal_ref": patch_apply_result.journal_ref,
                        "rollback_metadata": patch_apply_result.rollback_metadata,
                        "error": str(exc),
                    },
                    ensure_ascii=False,
                )
            ) from exc
        return self.commit(
            resolve_result=resolve_result,
            patch_plan_result=patch_plan_result,
            patch_apply_result=patch_apply_result,
            navigation_result=navigation_result,
        )

    @classmethod
    def _resolve_all_operations(
        cls,
        *,
        operations: list[ExtractedMemoryOperation],
        planned_operations: dict[tuple[str, str, str], MemoryChangePlanItem],
        registry: MemorySchemaRegistry,
        prepared: PreparedExtractContext,
    ) -> list[ResolvedMemoryOperation]:
        grouped: dict[str, list[ResolvedMemoryOperation]] = {}
        for operation in operations:
            resolved = cls._resolve_single_operation(
                operation=operation,
                planned_item=planned_operations[(operation.memory_type, operation.target_branch, operation.filename)],
                registry=registry,
                prepared=prepared,
                validate_existence=False,
            )
            grouped.setdefault(resolved.target_path, []).append(resolved)

        merged: list[ResolvedMemoryOperation] = []
        for target_path, items in grouped.items():
            op_kinds = {item.op for item in items}
            if "delete" in op_kinds and len(op_kinds) > 1:
                raise ValueError(f"conflicting operations for target_path: {target_path}")
            merged_item = cls._merge_resolved_operations(items)
            cls._validate_resolved_existence(merged_item)
            merged.append(merged_item)
        return merged

    @staticmethod
    def _resolve_single_operation(
        *,
        operation: ExtractedMemoryOperation,
        planned_item: MemoryChangePlanItem,
        registry: MemorySchemaRegistry,
        prepared: PreparedExtractContext,
        validate_existence: bool = True,
    ) -> ResolvedMemoryOperation:
        definition = registry.require(operation.memory_type)
        format_values = MemoryUpdater._schema_format_values(prepared=prepared, field_plans=operation.fields)
        target_dir = MemoryUpdater._render_template(definition.directory, format_values, sanitize=False)
        target_name = MemoryUpdater._normalize_filename(operation.filename)
        if target_dir != operation.target_branch:
            raise ValueError(
                "operation target_branch does not match schema directory: "
                f"{operation.memory_type} {operation.target_branch}"
            )
        expected_filename = MemoryUpdater._render_filename(definition, format_values)
        if expected_filename != target_name:
            raise ValueError(
                f"operation filename does not match schema template: {operation.memory_type} {operation.filename}"
            )
        target_path = "/".join(part for part in [target_dir, target_name] if part)
        scoped_path = "/".join(part for part in [config.MEMORY_TREE_ROOT_DIR, target_path] if part)
        file_exists = storage_manager.exists(scoped_path)

        merge_strategy = (
            "delete" if planned_item.op == "delete" else ("template_fields" if definition.content_template else "patch")
        )
        resolved = ResolvedMemoryOperation(
            op=planned_item.op,
            memory_type=definition.memory_type,
            target_path=target_path,
            target_name=target_name,
            file_exists=file_exists,
            merge_strategy=merge_strategy,
            field_plans=MemoryUpdater._build_resolved_field_plans(
                extracted_field_plans=operation.fields,
                content_template=definition.content_template,
            ),
            schema_path=definition.path,
        )
        if validate_existence:
            MemoryUpdater._validate_resolved_existence(resolved)
        return resolved

    @staticmethod
    def _merge_resolved_operations(items: list[ResolvedMemoryOperation]) -> ResolvedMemoryOperation:
        if len(items) == 1:
            return items[0]

        first = items[0]
        if all(item.op == "delete" for item in items):
            return first

        file_exists = any(item.file_exists for item in items)
        merged_op = "edit" if file_exists or any(item.op == "edit" for item in items) else "write"
        return ResolvedMemoryOperation(
            op=merged_op,
            memory_type=first.memory_type,
            target_path=first.target_path,
            target_name=first.target_name,
            file_exists=file_exists,
            merge_strategy=first.merge_strategy,
            field_plans=MemoryUpdater._merge_field_plans(items),
            schema_path=first.schema_path,
        )

    @staticmethod
    def _validate_resolved_existence(item: ResolvedMemoryOperation) -> None:
        if item.op in {"edit", "delete"} and not item.file_exists:
            raise ValueError(f"{item.op} requires existing target_path: {item.target_path}")

    @staticmethod
    def _validate_edit_operations_have_prior_reads(
        *,
        resolved_operations: list[ResolvedMemoryOperation],
        prepared: PreparedExtractContext,
        tools_used: list[dict[str, Any]],
    ) -> None:
        observed_read_paths = prepared.prefetched_read_paths()
        observed_read_paths.update(MemoryUpdater._tool_read_paths(tools_used))
        for operation in resolved_operations:
            if operation.op != "edit":
                continue
            if operation.target_path not in observed_read_paths:
                raise ValueError(f"edit requires prior read of target_path: {operation.target_path}")

    @staticmethod
    def _validate_edit_patch_field_plans(
        *,
        resolved_operations: list[ResolvedMemoryOperation],
    ) -> None:
        for operation in resolved_operations:
            if operation.op != "edit":
                continue
            missing_fields = sorted(
                {
                    field_plan.name
                    for field_plan in operation.field_plans
                    if field_plan.merge_op == "patch" and not field_plan.line_operations
                }
            )
            if missing_fields:
                raise ValueError(
                    "edit patch fields require line_operations for target_path: "
                    f"{operation.target_path}; fields={', '.join(missing_fields)}"
                )

    @staticmethod
    def _validate_operations_match_change_plan(
        *,
        change_plan: list[MemoryChangePlanItem],
        operations: list[ExtractedMemoryOperation],
    ) -> dict[tuple[str, str, str], MemoryChangePlanItem]:
        executable_plan = {
            (item.memory_type, item.target_branch, item.filename): item
            for item in change_plan
            if item.op in {"write", "edit", "delete"}
        }
        for operation in operations:
            key = (operation.memory_type, operation.target_branch, operation.filename)
            planned = executable_plan.get(key)
            if planned is None:
                target_path = f"{operation.target_branch}/{operation.filename}"
                raise ValueError(f"operation target does not match change_plan: {operation.memory_type} {target_path}")
        return executable_plan

    @staticmethod
    def _tool_read_paths(items: list[dict[str, Any]]) -> set[str]:
        read_paths: set[str] = set()
        for item in items:
            try:
                tool_result = PlannerToolUseResult.model_validate(item)
            except Exception:
                continue
            if tool_result.tool != "read":
                continue
            result_path = str((tool_result.result or {}).get("path") or "").strip()
            args_path = str((tool_result.args or {}).get("path") or "").strip()
            if result_path:
                read_paths.add(result_path)
            if args_path:
                read_paths.add(args_path)
        return read_paths

    @staticmethod
    def _render_filename(definition: MemorySchemaDefinition, values: dict[str, str]) -> str:
        raw_name = MemoryUpdater._render_template(definition.filename_template, values, sanitize=False)
        stem, suffix = Path(raw_name).stem, Path(raw_name).suffix or ".md"
        if raw_name == "profile.md":
            return raw_name
        return f"{normalize_path_segment(stem)}{suffix}"

    @staticmethod
    def _normalize_filename(filename: str) -> str:
        raw_name = str(filename or "").strip().replace("\\", "/")
        stem, suffix = Path(raw_name).stem, Path(raw_name).suffix or ".md"
        if raw_name == "profile.md":
            return raw_name
        return f"{normalize_path_segment(stem)}{suffix}"

    @staticmethod
    def _render_template(template: str, values: dict[str, str], *, sanitize: bool) -> str:
        required = [field_name for _, field_name, _, _ in Formatter().parse(template) if field_name]
        missing = [field_name for field_name in required if not str(values.get(field_name) or "").strip()]
        if missing:
            raise ValueError(f"missing fields for template rendering: {', '.join(missing)}")
        rendered = template.format(**values)
        return normalize_path_segment(rendered) if sanitize else rendered.replace("\\", "/")

    @staticmethod
    def _stringify_template_value(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _schema_format_values(
        *,
        prepared: PreparedExtractContext,
        field_plans: list[ExtractedMemoryFieldPlan],
    ) -> dict[str, str]:
        format_values = {
            "user_id": prepared.user_id or "",
            "agent_id": prepared.agent_id or "",
            "project_id": prepared.project_id or "",
        }
        format_values.update({plan.name: MemoryUpdater._stringify_template_value(plan.value) for plan in field_plans})
        return format_values

    @staticmethod
    def _build_resolved_field_plans(
        *,
        extracted_field_plans: list[ExtractedMemoryFieldPlan],
        content_template: str | None,
    ) -> list[ResolvedMemoryFieldPlan]:
        resolved = [
            ResolvedMemoryFieldPlan(
                name=plan.name,
                value=plan.value,
                merge_op=plan.merge_op,
                line_operations=list(plan.line_operations),
            )
            for plan in extracted_field_plans
        ]
        if content_template:
            resolved = [plan for plan in resolved if plan.name != "content"]
        return resolved

    @staticmethod
    def _merge_field_plans(items: list[ResolvedMemoryOperation]) -> list[ResolvedMemoryFieldPlan]:
        merged: dict[str, ResolvedMemoryFieldPlan] = {}
        ordered_names: list[str] = []
        for item in items:
            for field_plan in item.field_plans:
                existing = merged.get(field_plan.name)
                if existing is None:
                    merged[field_plan.name] = field_plan.model_copy(deep=True)
                    ordered_names.append(field_plan.name)
                    continue
                if existing.merge_op != field_plan.merge_op:
                    raise ValueError(
                        "conflicting merge_op for target field: "
                        f"{item.target_path} {field_plan.name} {existing.merge_op} != {field_plan.merge_op}"
                    )
                if field_plan.value is not None:
                    existing.value = field_plan.value
                if field_plan.line_operations:
                    existing.line_operations.extend(field_plan.line_operations)
        return [merged[name] for name in ordered_names]
