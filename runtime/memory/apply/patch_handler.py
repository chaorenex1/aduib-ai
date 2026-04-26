from __future__ import annotations

import json

from component.storage.base_storage import storage_manager
from configs import config
from runtime.memory.base.contracts import (
    MemoryMutationPlan,
    MemoryUpdateContext,
    MetadataTarget,
    NavigationMutationPlan,
    NavigationPatchPlanResult,
    NavigationRefreshResult,
    NavigationTarget,
    PatchApplyResult,
    PatchPlanResult,
    PreparedExtractContext,
    ResolvedMemoryOperation,
    ResolvedNavigationOperation,
    ResolveNavigationOperationsResult,
    ResolveOperationsResult,
    RollbackPlan,
)
from runtime.memory.schema.registry import MemorySchemaRegistry

from .patch import (
    apply_line_operations_to_body,
    build_desired_document,
    build_navigation_document,
    build_templated_content_field_plan,
)
from .rollback import deserialize_snapshot, serialize_snapshot


class PatchHandler:
    def build_staged_write_set(
        self,
        *,
        update_ctx: MemoryUpdateContext,
        resolve_result: ResolveOperationsResult,
    ) -> PatchPlanResult:
        return self.build_staged_write_set_from_inputs(
            task_id=update_ctx.task_id,
            prepared_context=update_ctx.prepared_context,
            resolve_result=resolve_result,
        )

    @classmethod
    def build_staged_write_set_from_inputs(
        cls,
        *,
        task_id: str,
        prepared_context: PreparedExtractContext,
        resolve_result: ResolveOperationsResult,
    ) -> PatchPlanResult:
        registry = MemorySchemaRegistry.load()
        memory_mutations: list[MemoryMutationPlan] = []
        snapshot_targets: list[str] = []
        for operation in resolve_result.resolved_operations:
            snapshot_targets.append(cls._to_scoped_path(operation.target_path))
            current_content = (
                storage_manager.read_text(cls._to_scoped_path(operation.target_path)) if operation.file_exists else None
            )
            definition = registry.require(operation.memory_type)
            materialized_operation = cls._materialize_operation(
                operation=operation,
                current_content=current_content,
                content_template=definition.content_template,
            )
            desired_content = None
            if operation.op != "delete":
                desired_content = build_desired_document(
                    task_id=task_id,
                    prepared=prepared_context,
                    operation=materialized_operation,
                    current_content=current_content,
                )
            memory_mutations.append(
                MemoryMutationPlan(
                    op=operation.op,
                    memory_type=operation.memory_type,
                    target_path=operation.target_path,
                    target_name=operation.target_name,
                    desired_content=desired_content,
                    previous_content=current_content,
                    file_exists=operation.file_exists,
                    memory_mode="template" if definition.content_template else "patch",
                    merge_strategy=operation.merge_strategy,
                )
            )

        navigation_targets = [
            NavigationTarget(
                branch_path=directory_path,
                overview_path=f"{directory_path}/overview.md",
                summary_path=f"{directory_path}/summary.md",
            )
            for directory_path in resolve_result.navigation_scopes
        ]
        snapshot_targets.extend(cls._to_scoped_path(item.overview_path) for item in navigation_targets)
        snapshot_targets.extend(cls._to_scoped_path(item.summary_path) for item in navigation_targets)
        snapshot = storage_manager.snapshot(snapshot_targets)
        rollback_plan = RollbackPlan(
            snapshot=serialize_snapshot(snapshot),
            target_paths=[item.target_path for item in memory_mutations],
        )
        metadata_targets = [
            MetadataTarget(scope_path=scope_path) for scope_path in sorted(set(resolve_result.metadata_scopes))
        ]
        journal_entries = [
            {"action": item.op, "target_path": item.target_path, "memory_type": item.memory_type}
            for item in memory_mutations
        ]
        return PatchPlanResult(
            task_id=task_id,
            memory_mutations=memory_mutations,
            navigation_targets=navigation_targets,
            metadata_targets=metadata_targets,
            rollback_plan=rollback_plan,
            journal_entries=journal_entries,
            staging_manifest={
                "memory_mutation_count": len(memory_mutations),
                "navigation_target_count": len(navigation_targets),
                "metadata_mutation_count": len(metadata_targets),
            },
        )

    def build_navigation_staged_write_set(
        self,
        *,
        update_ctx: MemoryUpdateContext,
        resolve_navigation_result: ResolveNavigationOperationsResult,
    ) -> NavigationPatchPlanResult:
        return self.build_navigation_staged_write_set_from_inputs(
            task_id=update_ctx.task_id,
            resolve_navigation_result=resolve_navigation_result,
        )

    @classmethod
    def build_navigation_staged_write_set_from_inputs(
        cls,
        *,
        task_id: str,
        resolve_navigation_result: ResolveNavigationOperationsResult,
    ) -> NavigationPatchPlanResult:
        navigation_mutations: list[NavigationMutationPlan] = []
        for operation in resolve_navigation_result.resolved_navigation_operations:
            navigable_entries = cls._list_navigable_entries_for_branch(operation.branch_path)
            desired_content = cls._build_navigation_desired_content(
                operation=operation,
                navigable_entries=navigable_entries,
            )
            navigation_mutations.append(
                NavigationMutationPlan(
                    document_kind=operation.document_kind,
                    op=operation.op,
                    target_path=operation.target_path,
                    branch_path=operation.branch_path,
                    file_exists=operation.file_exists,
                    based_on_existing=operation.based_on_existing,
                    previous_content=operation.previous_content,
                    previous_metadata=operation.previous_metadata,
                    previous_body=operation.previous_body,
                    markdown_body=operation.markdown_body,
                    line_operations=list(operation.line_operations),
                    expected_body_sha256=operation.expected_body_sha256,
                    desired_content=desired_content,
                )
            )
        return NavigationPatchPlanResult(task_id=task_id, navigation_mutations=navigation_mutations)

    def apply_memory_files(
        self,
        *,
        update_ctx: MemoryUpdateContext,
        patch_plan: PatchPlanResult,
    ) -> PatchApplyResult:
        return self.apply_memory_files_from_inputs(task_id=update_ctx.task_id, patch_plan=patch_plan)

    @classmethod
    def apply_memory_files_from_inputs(
        cls,
        *,
        task_id: str,
        patch_plan: PatchPlanResult,
    ) -> PatchApplyResult:
        journal_ref = cls._journal_path(task_id)
        applied_paths: list[str] = []
        try:
            for mutation in patch_plan.memory_mutations:
                scoped_path = cls._to_scoped_path(mutation.target_path)
                if mutation.op == "delete":
                    storage_manager.delete(scoped_path)
                else:
                    storage_manager.write_text_atomic(scoped_path, mutation.desired_content)
                    storage_manager.read_text(scoped_path)
                applied_paths.append(mutation.target_path)
            journal_payload = {
                "task_id": task_id,
                "phase": "apply_memory_files",
                "applied_paths": applied_paths,
                "journal_entries": patch_plan.journal_entries,
            }
            storage_manager.write_text_atomic(journal_ref, json.dumps(journal_payload, ensure_ascii=False, indent=2))
            return PatchApplyResult(
                task_id=task_id,
                applied_memory_files=applied_paths,
                journal_ref=journal_ref.replace(f"{config.MEMORY_TREE_ROOT_DIR}/", "", 1),
                rollback_metadata={
                    "applied_paths": applied_paths,
                    "rolled_back_paths": [],
                    "rollback_failed_paths": [],
                },
            )
        except Exception:
            rollback_metadata = {"applied_paths": applied_paths, "rolled_back_paths": [], "rollback_failed_paths": []}
            try:
                snapshot = deserialize_snapshot(patch_plan.rollback_plan.snapshot)
                storage_manager.restore(snapshot)
                rollback_metadata["rolled_back_paths"] = patch_plan.rollback_plan.target_paths
            except Exception:
                rollback_metadata["rollback_failed_paths"] = patch_plan.rollback_plan.target_paths
            raise RuntimeError(json.dumps({"phase": "apply_memory_files", "rollback_metadata": rollback_metadata}))

    def apply_navigation_files(
        self,
        *,
        update_ctx: MemoryUpdateContext,
        navigation_patch_plan: NavigationPatchPlanResult,
    ) -> NavigationRefreshResult:
        return self.apply_navigation_files_from_inputs(
            task_id=update_ctx.task_id,
            navigation_patch_plan=navigation_patch_plan,
        )

    @classmethod
    def apply_navigation_files_from_inputs(
        cls,
        *,
        task_id: str,
        navigation_patch_plan: NavigationPatchPlanResult,
    ) -> NavigationRefreshResult:
        navigation_files: list[str] = []
        for mutation in navigation_patch_plan.navigation_mutations:
            scoped_path = cls._to_scoped_path(mutation.target_path)
            storage_manager.write_text_atomic(scoped_path, mutation.desired_content)
            storage_manager.read_text(scoped_path)
            navigation_files.append(mutation.target_path)
        return NavigationRefreshResult(task_id=task_id, navigation_files=navigation_files)

    def run(
        self,
        *,
        update_ctx: MemoryUpdateContext,
        resolve_result: ResolveOperationsResult,
    ) -> tuple[PatchPlanResult, PatchApplyResult]:
        patch_plan = self.build_staged_write_set(update_ctx=update_ctx, resolve_result=resolve_result)
        patch_apply = self.apply_memory_files(update_ctx=update_ctx, patch_plan=patch_plan)
        return patch_plan, patch_apply

    @staticmethod
    def _journal_path(task_id: str) -> str:
        return f"{config.MEMORY_TREE_ROOT_DIR}/.system/memory-write-journals/{task_id}-apply-memory-files.json"

    @staticmethod
    def _to_scoped_path(relative_path: str) -> str:
        return "/".join(part for part in [config.MEMORY_TREE_ROOT_DIR, relative_path] if part)

    @staticmethod
    def _materialize_operation(
        *,
        operation: ResolvedMemoryOperation,
        current_content: str | None,
        content_template: str | None,
    ) -> ResolvedMemoryOperation:
        if operation.op == "delete" or not content_template:
            return operation
        materialized_operation = operation.model_copy(deep=True)
        rendered_content_plan = build_templated_content_field_plan(
            operation=materialized_operation,
            current_content=current_content,
            content_template=content_template,
        )
        materialized_operation.field_plans = [
            plan for plan in materialized_operation.field_plans if plan.name != "content"
        ]
        materialized_operation.field_plans.append(rendered_content_plan)
        return materialized_operation

    @staticmethod
    def _list_navigable_entries_for_branch(branch_path: str) -> list[dict]:
        from runtime.memory.navigation.common import list_branch_navigable_entries

        return list_branch_navigable_entries(branch_path)

    @staticmethod
    def _build_navigation_desired_content(
        *,
        operation: ResolvedNavigationOperation,
        navigable_entries: list[dict],
    ) -> str:
        if operation.op == "write":
            next_body = str(operation.markdown_body or "").strip()
        else:
            next_body = apply_line_operations_to_body(
                str(operation.previous_body or ""),
                operation.line_operations,
            ).strip()
        return build_navigation_document(
            kind=operation.document_kind,
            scope_path=operation.branch_path,
            navigable_entries=navigable_entries,
            body=next_body,
            previous_metadata=operation.previous_metadata,
        )
