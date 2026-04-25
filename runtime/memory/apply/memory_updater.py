from __future__ import annotations

import json
from pathlib import Path
from string import Formatter
from typing import Any

from component.storage.base_storage import storage_manager
from configs import config
from runtime.memory.apply.patch_handler import PatchHandler
from runtime.memory.base.contracts import (
    ExtractedMemoryFieldPlan,
    ExtractedMemoryOperation,
    MemoryChangePlanItem,
    MemoryCommittedResult,
    MemoryUpdateContext,
    NavigationManagerResult,
    PatchApplyResult,
    PatchPlanResult,
    PlannerToolUseResult,
    PreparedExtractContext,
    ResolvedMemoryOperation,
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
                item.model_dump(mode="python", exclude_none=True)
                for item in self.update_ctx.extract_result.tools_used
            ],
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

    def run(self) -> MemoryCommittedResult:
        resolve_result = self.resolve_operations()
        patch_plan_result, patch_apply_result = self.patch_handler.run(
            update_ctx=self.update_ctx,
            resolve_result=resolve_result,
        )
        try:
            navigation_result = self.navigation_manager.run(
                update_ctx=self.update_ctx,
                patch_plan=patch_plan_result,
                patch_apply=patch_apply_result,
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
        field_values = MemoryUpdater._field_values_map(operation.fields)
        resolved = ResolvedMemoryOperation(
            op=planned_item.op,
            memory_type=definition.memory_type,
            target_path=target_path,
            target_name=target_name,
            file_exists=file_exists,
            merge_strategy=merge_strategy,
            fields={key: value for key, value in field_values.items() if key != "content"},
            field_merge_ops={key: value for key, value in definition.field_merge_ops.items() if key != "content"},
            field_plans=operation.fields,
            content=str(field_values.get("content") or ""),
            content_template=definition.content_template,
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

        merged_fields: dict[str, Any] = {}
        merged_field_plans: list[ExtractedMemoryFieldPlan] = []
        merged_content = ""
        file_exists = any(item.file_exists for item in items)
        for item in items:
            merged_fields.update(item.fields)
            merged_field_plans.extend(item.field_plans)
            if item.content:
                merged_content = item.content
        merged_op = "edit" if file_exists or any(item.op == "edit" for item in items) else "write"
        return ResolvedMemoryOperation(
            op=merged_op,
            memory_type=first.memory_type,
            target_path=first.target_path,
            target_name=first.target_name,
            file_exists=file_exists,
            merge_strategy=first.merge_strategy,
            memory_mode=first.memory_mode,
            fields=merged_fields,
            field_merge_ops=first.field_merge_ops,
            field_plans=merged_field_plans,
            content=merged_content,
            content_template=first.content_template,
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
    def _field_values_map(field_plans: list[ExtractedMemoryFieldPlan]) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for plan in field_plans:
            values[plan.name] = plan.value
        return values


MemoryUpdator = MemoryUpdater
