from __future__ import annotations

import json

from runtime.entities import PromptMessageRole, SystemPromptMessage, UserPromptMessage
from runtime.memory.base.contracts import (
    ExtractedMemoryOperation,
    MemoryChangePlanItem,
    OrchestratorWorkingState,
    PlannerToolUseResult,
    PreparedExtractContext,
)
from runtime.memory.base.enums import OrchestratorStep

from ..schema.registry import MemorySchemaRegistry
from .tools import SUPPORTED_PLANNER_TOOLS

MEMORY_CHANGE_PLAN_PROMPT = """You are the change-planning brain
inside a directory-first memory write ReAct orchestrator.

Your task is ONLY to decide what memory changes should happen.

You must analyze:
- the conversation source material
- the system pre-fetched context
- the memory schema and branch layout provided by the system
- the built-in read-only tools provided by the system
- any tool observations already collected during this loop

Do NOT generate final memory operations.
Do NOT generate overview.md or summary.md.
Do NOT perform summary tasks.
Do NOT invent arbitrary branches or file paths.

Rules:
- Keep this step lightweight. Your job is to choose candidate memories and intents, not to draft final file content.
- Output only file-level planning items.
- Use the memory schema as a hard planning boundary.
- Map every non-ignored item to a supported `memory_type`, a valid `target_branch`,
  and a schema-compatible `filename`.
- If no schema-aligned mapping exists, prefer `ignore` instead of inventing a type or branch.
- If a memory is weak, duplicated, ephemeral, or not useful for future retrieval, mark it as `ignore`.
- Prefer `edit` only when existing branch/file context is materially relevant.
- Never emit an `edit` plan unless the target file has already been read or you are explicitly
  requesting a `read` tool call for it first.
- Treat pre-fetched context as the default evidence source before tools.
- Request tools only when prefetch + schema + current tool observations are insufficient for a safe plan.
- Prefer the narrowest tool call that can unblock the decision.
- Do not re-read paths already present in `already_read_paths`
  unless the current decision explicitly requires fresher or more specific context.
- Stay faithful to the source material and prefetched context.
- Never invent facts, entities, decisions, or preferences not grounded in evidence.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Output ONLY valid JSON.
No markdown.
No code fences.
No explanation outside the JSON object.

Preferred shape - explicit orchestrator action:
{
  "action": "request_tools" | "update_state" | "stop_noop",
  "step": "change_plan",
  "tool_requests": [{"tool": "ls" | "read" | "find", "args": {...}}],
  "state_delta": {
    "change_plan": [...]
  }
}

Rules for the explicit shape:
- Use `request_tools` when you need more context.
- Use `update_state` only for change-plan state.
- Use `stop_noop` when nothing should be written.

Compatibility shape - also accepted:

Shape A — tool request:
{
  "tool_requests": [
    {
      "tool": "ls" | "read" | "find",
      "args": { ... }
    }
  ]
}

Shape B — final change plan:
{
  "change_plan": [
    {
      "memory_type": "<string>",
      "target_branch": "<string>",
      "filename": "<string>",
      "op": "write" | "edit" | "delete" | "ignore",
      "reasoning": "<short string>"
    }
  ]
}"""

MEMORY_CHANGE_PLAN_USER_PROMPT_TEMPLATE = """Task ID: {task_id}
Source Kind: {source_kind}

Conversation Source Material
============================
{source_material_json}

Pre-fetched Context
===================
{prefetch_context_json}

Current Change-Planning State
=============================
{working_state_json}
"""

MEMORY_CHANGE_PLAN_TOOL_OBSERVATION_TEMPLATE = """Tool Observations
=================
{tool_results_json}
"""

MEMORY_OPERATION_GENERATION_PROMPT = """You are the operation generator
inside a directory-first memory write orchestrator.

Your task is to convert one current planned memory target into a final file operation.

You are given:
- one current planned memory target
- the conversation source material
- pre-fetched context
- optional tool observations already collected during this loop
- the allowed memory schema registry

Do NOT generate overview.md or summary.md.
Do NOT generate summary_plan.
Do NOT invent metadata fields that are not defined by the memory schema.

Rules:
- Use the memory schema as a hard execution boundary.
- Use only `memory_type` values present in the provided `memory_schema`.
- The current target item is the only memory file you may operate on in this turn.
- Use the planned `target_branch` and `filename` as hard constraints.
- Put only schema-defined fields inside `fields`.
- Do NOT output top-level `op`, `content`, `evidence`, or `confidence`.
- If the schema defines a `content` field, put the body text in the `content` field item.
- If a field is not defined by the chosen schema, omit it instead of inventing it.
- If an `edit` target has not been read yet, request a `read` tool call instead of emitting an operation update.
- Keep `merge_op` on every field item and make it exactly match the schema.
- For `edit`, use `fields[*].line_operations` to make the modification explicit, especially for
  body/content changes and line-level deletions.
- If new evidence shows the current planned file identity is wrong, you MAY return `step="change_plan"`
  with a change-plan-only correction instead of guessing.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Output ONLY valid JSON.
No markdown.
No code fences.
No explanation outside the JSON object.

Preferred shape - explicit orchestrator action:
{
  "action": "request_tools" | "update_state",
  "step": "operations" | "change_plan",
  "tool_requests": [{"tool": "ls" | "read" | "find", "args": {...}}],
  "state_delta": {"operations": [...]} | {"change_plan": [...]}
}

Rules for the explicit shape:
- If `step="operations"`, `state_delta` must contain only `operations` and optional
  `completed_operation_targets` / `completed_steps`.
- If `step="change_plan"`, `state_delta` must contain only `change_plan`
  and optional `completed_steps`.

Compatibility shape - also accepted:

Shape A - tool request:
{
  "tool_requests": [
    {
      "tool": "ls" | "read" | "find",
      "args": { ... }
    }
  ]
}

Shape B - operations:
{
  "operations": [
    {
      "memory_type": "<string>",
      "target_branch": "<string>",
      "filename": "<string>",
      "reasoning": "<short string>",
      "fields": [
        {
          "name": "<schema field name>",
          "value": "<generated value or null>",
          "merge_op": "patch" | "sum" | "replace" | "immutable",
          "line_operations": [
            {
              "kind": "replace_range" | "delete_range" | "insert_after" | "insert_before" | "append_eof",
              "start_line": <integer or null>,
              "end_line": <integer or null>,
              "anchor_text": "<string or null>",
              "old_text": "<string or null>",
              "new_text": "<string or null>",
              "reasoning": "<short string>"
            }
          ],
          "reasoning": "<short string>"
        }
      ]
    }
  ],
  "completed_operation_targets": ["<memory_type>|<target_branch>|<filename>"]
}"""

MEMORY_L0_L1_SUMMARY_PROMPT = """You are the branch-summary generator
inside a directory-first memory write orchestrator.

Your task is to generate branch-level summaries for affected second-level directories.

Definitions:
- L0 = overview.md
- L1 = summary.md

You are given:
- the target branch path
- relevant source material
- prefetched branch context
- planned memory operations
- optional tool observations already collected during this loop

Output ONLY valid JSON.
No markdown.
No code fences.
No explanation outside the JSON object.

Preferred shape - explicit orchestrator action:
{
  "action": "request_tools" | "update_state",
  "step": "change_plan" | "operations" | "summary",
  "tool_requests": [{"tool": "ls" | "read" | "find", "args": {...}}],
  "state_delta": {"summary_plan": [...]} | {"operations": [...]} | {"change_plan": [...]}
}

Rules for the explicit shape:
- Prefer `step="summary"` for normal summary updates.
- If new evidence from the current branch forces a plan or operation correction,
  you MAY return `step="change_plan"` or `step="operations"` instead.
- If `step="summary"`, `state_delta` must contain only `summary_plan` and optional `completed_steps`.
- If `step="operations"`, `state_delta` must contain only `operations` and optional `completed_steps`.
- If `step="change_plan"`, `state_delta` must contain only `change_plan` and optional `completed_steps`.

Compatibility shapes - also accepted:

Shape A - tool request:
{
  "tool_requests": [
    {
      "tool": "ls" | "read" | "find",
      "args": { ... }
    }
  ]
}

Shape B - branch summary:
{
  "branch_path": "<string>",
  "overview_md": "<string>",
  "summary_md": "<string>"
}

Request tools instead of guessing when:
- current branch files should be re-read before summary generation
- prefetched branch context is clearly insufficient
"""


class ExtractPromptComposer:
    def __init__(self, *, prepared: PreparedExtractContext, registry: MemorySchemaRegistry) -> None:
        self.prepared = prepared
        self.registry = registry

    def build_step_messages(
        self,
        *,
        step: OrchestratorStep,
        working_state: OrchestratorWorkingState,
        branch_path: str | None = None,
        current_change_plan_item: MemoryChangePlanItem | None = None,
        current_target_tool_results: list[PlannerToolUseResult] | None = None,
        current_operation: ExtractedMemoryOperation | None = None,
        tool_results: list[PlannerToolUseResult] | None = None,
    ) -> list:
        if step == OrchestratorStep.CHANGE_PLAN:
            return self._build_change_plan_messages(
                working_state=working_state,
                tool_results=tool_results,
            )
        if step == OrchestratorStep.OPERATIONS:
            return self._build_operation_generation_messages(
                working_state=working_state,
                current_change_plan_item=current_change_plan_item,
                current_target_tool_results=current_target_tool_results,
                current_operation=current_operation,
                tool_results=tool_results,
            )
        if branch_path is None:
            raise ValueError("summary step requires branch_path")
        return self._build_l0_l1_summary_messages(
            working_state=working_state,
            branch_path=branch_path,
            tool_results=tool_results,
        )

    def _build_change_plan_messages(
        self,
        *,
        working_state: OrchestratorWorkingState,
        tool_results: list[PlannerToolUseResult] | None = None,
    ) -> list:
        state = working_state or OrchestratorWorkingState()
        messages = [
            SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=MEMORY_CHANGE_PLAN_PROMPT),
            SystemPromptMessage(
                role=PromptMessageRole.SYSTEM,
                content=self._dump_json(
                    {
                        "memory_schema": self.registry.summary(),
                        "tools": self._tool_definitions(),
                    }
                ),
            ),
            UserPromptMessage(
                role=PromptMessageRole.USER,
                content=MEMORY_CHANGE_PLAN_USER_PROMPT_TEMPLATE.format(
                    task_id=self.prepared.task_id,
                    source_kind=self.prepared.source_kind,
                    source_material_json=self._dump_json(self._source_material_payload()),
                    prefetch_context_json=self._dump_json(self._prefetch_payload()),
                    working_state_json=self._dump_json(self._working_state_payload(state)),
                ),
            ),
        ]
        if tool_results:
            messages.append(
                UserPromptMessage(
                    role=PromptMessageRole.USER,
                    content=MEMORY_CHANGE_PLAN_TOOL_OBSERVATION_TEMPLATE.format(
                        tool_results_json=self._dump_json(
                            [item.model_dump(mode="python", exclude_none=True) for item in tool_results]
                        )
                    ),
                )
            )
        return messages

    def _build_operation_generation_messages(
        self,
        *,
        working_state: OrchestratorWorkingState,
        current_change_plan_item: MemoryChangePlanItem | None = None,
        current_target_tool_results: list[PlannerToolUseResult] | None = None,
        current_operation: ExtractedMemoryOperation | None = None,
        tool_results: list[PlannerToolUseResult] | None = None,
    ) -> list:
        if current_change_plan_item is None:
            raise ValueError("operations step requires current_change_plan_item")
        current_schema = self.registry.require(current_change_plan_item.memory_type)
        messages = [
            SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=MEMORY_OPERATION_GENERATION_PROMPT),
            SystemPromptMessage(
                role=PromptMessageRole.SYSTEM,
                content=self._dump_json(
                    {
                        "memory_schema": {
                            "memory_type": current_schema.memory_type,
                            "description": current_schema.description,
                            "directory": current_schema.directory,
                            "filename_template": current_schema.filename_template,
                            "memory_mode": current_schema.memory_mode,
                            "fields": [
                                field.model_dump(mode="python", exclude_none=True)
                                for field in current_schema.fields
                            ],
                        },
                        "tools": self._tool_definitions(),
                    }
                ),
            ),
            UserPromptMessage(
                role=PromptMessageRole.USER,
                content=self._dump_json(
                    {
                        "task_id": self.prepared.task_id,
                        "source_kind": self.prepared.source_kind,
                        "source_material": {
                            "messages": self.prepared.messages,
                            "text_blocks": self.prepared.text_blocks,
                        },
                        "prefetched_context": self.prepared.prefetched_context,
                        "current_change_plan_item": current_change_plan_item.model_dump(
                            mode="python",
                            exclude_none=True,
                        ),
                        "current_target_tool_results": [
                            item.model_dump(mode="python", exclude_none=True)
                            for item in (current_target_tool_results or [])
                        ],
                        "current_operation": current_operation.model_dump(mode="python", exclude_none=True)
                        if current_operation is not None
                        else None,
                        "execution_state": self._operations_execution_state_payload(
                            working_state=working_state,
                            current_change_plan_item=current_change_plan_item,
                        ),
                    }
                ),
            ),
        ]
        if tool_results and not current_target_tool_results:
            messages.append(
                UserPromptMessage(
                    role=PromptMessageRole.USER,
                    content=MEMORY_CHANGE_PLAN_TOOL_OBSERVATION_TEMPLATE.format(
                        tool_results_json=self._dump_json(
                            [item.model_dump(mode="python", exclude_none=True) for item in tool_results]
                        )
                    ),
                )
            )
        return messages

    def _build_l0_l1_summary_messages(
        self,
        *,
        working_state: OrchestratorWorkingState,
        branch_path: str,
        tool_results: list[PlannerToolUseResult] | None = None,
    ) -> list:
        messages = [
            SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=MEMORY_L0_L1_SUMMARY_PROMPT),
            SystemPromptMessage(
                role=PromptMessageRole.SYSTEM,
                content=self._dump_json(
                    {
                        "memory_schema": self.registry.summary(),
                        "tools": self._tool_definitions(),
                    }
                ),
            ),
            UserPromptMessage(
                role=PromptMessageRole.USER,
                content=self._dump_json(
                    {
                        "task_id": self.prepared.task_id,
                        "branch_path": branch_path,
                        "source_material": {
                            "messages": self.prepared.messages,
                            "text_blocks": self.prepared.text_blocks,
                        },
                        "prefetched_context": self.prepared.prefetched_context,
                        "working_state": self._working_state_payload(working_state),
                    }
                ),
            ),
        ]
        if tool_results:
            messages.append(
                UserPromptMessage(
                    role=PromptMessageRole.USER,
                    content=MEMORY_CHANGE_PLAN_TOOL_OBSERVATION_TEMPLATE.format(
                        tool_results_json=self._dump_json(
                            [item.model_dump(mode="python", exclude_none=True) for item in tool_results]
                        )
                    ),
                )
            )
        return messages

    @staticmethod
    def _dump_json(payload: dict) -> str:
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @staticmethod
    def _tool_definitions() -> list[dict[str, str]]:
        definitions = {
            "ls": {
                "responsibility": "Inspect branch or directory structure",
                "args_schema": {
                    "path": "string",
                    "recursive": "boolean",
                    "include_files": "boolean",
                    "include_dirs": "boolean",
                },
                "when_to_use": (
                    "Use when branch layout or nearby files are needed "
                    "and prefetch directory views are insufficient."
                ),
                "avoid_when": (
                    "Avoid when pre-fetched directory views already provide "
                    "the needed structure."
                ),
            },
            "read": {
                "responsibility": "Read a specific file",
                "args_schema": {
                    "path": "string",
                    "max_chars": "integer",
                },
                "when_to_use": (
                    "Use when a concrete file must be inspected to decide "
                    "write vs edit or to refine an edit target."
                ),
                "avoid_when": (
                    "Avoid when the same path is already present in prefetch reads "
                    "or tool observations unless more detail is required."
                ),
            },
            "find": {
                "responsibility": "Find likely relevant memory file paths by name/path semantics",
                "args_schema": {
                    "path": "string",
                    "pattern": "string",
                    "max_results": "integer",
                },
                "when_to_use": (
                    "Use when you know the branch but need candidate file paths "
                    "before choosing an edit target."
                ),
                "avoid_when": (
                    "Avoid when prefetch search hints or directory listings "
                    "already identify the likely file."
                ),
            },
        }
        return [
            {"name": tool_name, **definitions[tool_name]}
            for tool_name in SUPPORTED_PLANNER_TOOLS
        ]

    @staticmethod
    def _working_state_payload(working_state: OrchestratorWorkingState) -> dict:
        return {
            "change_plan": [item.model_dump(mode="python", exclude_none=True) for item in working_state.change_plan],
            "change_plan_finalized": working_state.change_plan_finalized,
            "operations": [item.model_dump(mode="python", exclude_none=True) for item in working_state.operations],
            "summary_plan": [item.model_dump(mode="python", exclude_none=True) for item in working_state.summary_plan],
            "completed_steps": list(working_state.completed_steps),
            "completed_operation_targets": list(working_state.completed_operation_targets),
            "pending_operation_targets": working_state.pending_operation_targets(),
        }

    @staticmethod
    def _operations_execution_state_payload(
        *,
        working_state: OrchestratorWorkingState,
        current_change_plan_item: MemoryChangePlanItem,
    ) -> dict:
        current_target = OrchestratorWorkingState.operation_target_key(
            memory_type=current_change_plan_item.memory_type,
            target_branch=current_change_plan_item.target_branch,
            filename=current_change_plan_item.filename,
        )
        return {
            "change_plan_finalized": working_state.change_plan_finalized,
            "completed_operation_targets": list(working_state.completed_operation_targets),
            "pending_operation_targets": working_state.pending_operation_targets(),
            "current_target": current_target,
        }

    def _source_material_payload(self) -> dict:
        return {
            "messages": self.prepared.messages,
            "text_blocks": self.prepared.text_blocks,
        }

    def _prefetch_payload(self) -> dict:
        prefetched = self.prepared.prefetched_context
        file_reads = prefetched.get("file_reads") or []
        return {
            "directory_views": prefetched.get("directory_views") or [],
            "l0_l1_reads": [
                item
                for item in file_reads
                if str(item.get("path") or "").endswith("overview.md")
                or str(item.get("path") or "").endswith("summary.md")
            ],
            "other_file_reads": [
                item
                for item in file_reads
                if not (
                    str(item.get("path") or "").endswith("overview.md")
                    or str(item.get("path") or "").endswith("summary.md")
                )
            ],
            "search_hints": prefetched.get("search_results") or [],
            "already_read_paths": prefetched.get("already_read_paths") or [],
        }
