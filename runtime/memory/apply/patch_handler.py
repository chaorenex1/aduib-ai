from __future__ import annotations

import json

from component.storage.base_storage import storage_manager
from configs import config
from runtime.memory.base.contracts import (
    DocumentMutationPlan,
    MemoryUpdateContext,
    MetadataTarget,
    NavigationTarget,
    PatchApplyResult,
    PatchPlanResult,
    PreparedExtractContext,
    ResolvedDocumentOperation,
    ResolveDocumentOperationsResult,
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
        resolve_result: ResolveDocumentOperationsResult,
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
        resolve_result: ResolveDocumentOperationsResult,
    ) -> PatchPlanResult:
        document_mutations = cls._build_document_mutations(
            task_id=task_id,
            prepared_context=prepared_context,
            operations=resolve_result.document_operations,
        )
        snapshot_targets = [cls._to_scoped_path(item.target_path) for item in document_mutations]
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
            target_paths=[item.target_path for item in document_mutations],
        )
        metadata_targets = [
            MetadataTarget(scope_path=scope_path) for scope_path in sorted(set(resolve_result.metadata_scopes))
        ]
        journal_entries = [
            {
                "action": item.op,
                "target_path": item.target_path,
                "document_family": item.document_family,
                "document_kind": item.document_kind,
            }
            for item in document_mutations
        ]
        return PatchPlanResult(
            task_id=task_id,
            document_mutations=document_mutations,
            navigation_targets=navigation_targets,
            metadata_targets=metadata_targets,
            rollback_plan=rollback_plan,
            journal_entries=journal_entries,
            staging_manifest={
                "document_mutation_count": len(document_mutations),
                "navigation_target_count": len(navigation_targets),
                "metadata_mutation_count": len(metadata_targets),
            },
        )

    def apply_files(
        self,
        *,
        update_ctx: MemoryUpdateContext,
        patch_plan: PatchPlanResult,
    ) -> PatchApplyResult:
        return self.apply_files_from_inputs(task_id=update_ctx.task_id, patch_plan=patch_plan)

    @classmethod
    def apply_files_from_inputs(
        cls,
        *,
        task_id: str,
        patch_plan: PatchPlanResult,
    ) -> PatchApplyResult:
        journal_ref = cls._journal_path(task_id)
        applied_paths: list[str] = []
        try:
            for mutation in patch_plan.document_mutations:
                scoped_path = cls._to_scoped_path(mutation.target_path)
                if mutation.op == "delete":
                    storage_manager.delete(scoped_path)
                else:
                    storage_manager.write_text_atomic(scoped_path, mutation.desired_content)
                    storage_manager.read_text(scoped_path)
                applied_paths.append(mutation.target_path)
            journal_payload = {
                "task_id": task_id,
                "phase": "apply_files",
                "applied_paths": applied_paths,
                "journal_entries": patch_plan.journal_entries,
            }
            storage_manager.write_text_atomic(journal_ref, json.dumps(journal_payload, ensure_ascii=False, indent=2))
            return PatchApplyResult(
                task_id=task_id,
                applied_files=applied_paths,
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
            raise RuntimeError(json.dumps({"phase": "apply_files", "rollback_metadata": rollback_metadata}))

    def run(
        self,
        *,
        update_ctx: MemoryUpdateContext,
        resolve_result: ResolveDocumentOperationsResult,
    ) -> tuple[PatchPlanResult, PatchApplyResult]:
        patch_plan = self.build_staged_write_set(update_ctx=update_ctx, resolve_result=resolve_result)
        patch_apply = self.apply_files(update_ctx=update_ctx, patch_plan=patch_plan)
        return patch_plan, patch_apply

    @staticmethod
    def _journal_path(task_id: str) -> str:
        return f"{config.MEMORY_TREE_ROOT_DIR}/.system/memory-write-journals/{task_id}-apply-memory-files.json"

    @staticmethod
    def _to_scoped_path(relative_path: str) -> str:
        return "/".join(part for part in [config.MEMORY_TREE_ROOT_DIR, relative_path] if part)

    @staticmethod
    def _materialize_memory_operation(
        *,
        operation: ResolvedDocumentOperation,
        current_content: str | None,
        content_template: str | None,
    ) -> ResolvedDocumentOperation:
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

    @classmethod
    def _build_document_mutations(
        cls,
        *,
        task_id: str,
        prepared_context: PreparedExtractContext,
        operations: list[ResolvedDocumentOperation],
    ) -> list[DocumentMutationPlan]:
        registry = MemorySchemaRegistry.load()
        document_mutations: list[DocumentMutationPlan] = []
        for operation in operations:
            if operation.document_family == "memory":
                current_content = (
                    storage_manager.read_text(cls._to_scoped_path(operation.target_path))
                    if operation.file_exists
                    else None
                )
                definition = registry.require(str(operation.memory_type))
                materialized_operation = cls._materialize_memory_operation(
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
                document_mutations.append(
                    DocumentMutationPlan(
                        document_family="memory",
                        document_kind=str(operation.memory_type),
                        op=operation.op,
                        target_path=operation.target_path,
                        file_exists=operation.file_exists,
                        previous_content=current_content,
                        desired_content=desired_content,
                        metadata={
                            "memory_type": operation.memory_type,
                            "target_name": operation.target_name,
                            "merge_strategy": operation.merge_strategy,
                        },
                    )
                )
                continue

            if operation.document_family == "project":
                if operation.content_mode == "line_operations":
                    desired_content = apply_line_operations_to_body(
                        str(operation.previous_body or ""),
                        operation.line_operations,
                    ).strip()
                else:
                    desired_content = str(operation.full_body or "")
                document_mutations.append(
                    DocumentMutationPlan(
                        document_family="project",
                        document_kind=operation.document_kind,
                        op=operation.op,
                        target_path=operation.target_path,
                        file_exists=operation.file_exists,
                        previous_content=operation.previous_content,
                        desired_content=desired_content,
                        metadata={
                            "branch_path": operation.branch_path,
                        },
                    )
                )
                continue

            navigable_entries = cls._list_navigable_entries_for_branch(str(operation.branch_path))
            desired_content = cls._build_navigation_desired_content(
                operation=operation,
                navigable_entries=navigable_entries,
            )
            document_mutations.append(
                DocumentMutationPlan(
                    document_family="navigation",
                    document_kind=operation.document_kind,
                    op=operation.op,
                    target_path=operation.target_path,
                    file_exists=operation.file_exists,
                    previous_content=operation.previous_content,
                    desired_content=desired_content,
                    metadata={
                        "branch_path": operation.branch_path,
                        "based_on_existing": operation.based_on_existing,
                        "expected_body_sha256": operation.expected_body_sha256,
                    },
                )
            )
        return document_mutations

    @staticmethod
    def _list_navigable_entries_for_branch(branch_path: str) -> list[dict]:
        from runtime.memory.navigation.common import list_branch_navigable_entries

        return list_branch_navigable_entries(branch_path)

    @staticmethod
    def _build_navigation_desired_content(
        *,
        operation: ResolvedDocumentOperation,
        navigable_entries: list[dict],
    ) -> str:
        if operation.op == "write":
            next_body = str(operation.full_body or "").strip()
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
