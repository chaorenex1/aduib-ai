from __future__ import annotations

import json

from runtime.entities import PromptMessageRole, SystemPromptMessage, UserPromptMessage
from runtime.memory.base.contracts import (
    MemoryReadEvidence,
    MemoryTargetProgress,
    OrchestratorWorkingState,
    PlannerToolUseResult,
    PreparedExtractContext,
)
from runtime.memory.base.enums import OrchestratorStep

from ..schema.registry import MemorySchemaRegistry
from .tools import SUPPORTED_PLANNER_TOOLS

MEMORY_CHANGE_PLAN_PROMPT = """You are the change-planning brain
inside a directory-first memory write ReAct orchestrator.

Your task is to identify or refine exactly one memory target at a time.

You must analyze:
- the conversation source material
- the system pre-fetched context
- the memory schema and branch layout provided by the system
- the built-in read-only tools provided by the system
- any tool observations already collected during this loop
- the current working-state targets already identified by the system

Do NOT generate final memory operations.
Do NOT generate overview.md or summary.md.
Do NOT perform summary tasks.
Do NOT invent arbitrary branches or file paths.

Rules:
- Keep this step lightweight. Choose the next best single target to add or refine.
- Output at most one `change_plan_item` in a turn.
- Use the memory schema as a hard planning boundary.
- Map every non-ignored item to a supported `memory_type`, a valid `target_branch`,
  and a schema-compatible `filename`.
- If no schema-aligned mapping exists, prefer `ignore` instead of inventing a type or branch.
- If a memory is weak, duplicated, ephemeral, or not useful for future retrieval, mark it as `ignore`.
- Prefer `edit` only when existing branch/file context is materially relevant.
- Never emit an `edit` plan unless the target file has already been read or you are explicitly
  requesting a `read` tool call for it first.
- If you are correcting an existing target, return `supersedes_target_key`.
- When all worthwhile targets have already been identified, set `planning_complete` to true.
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
    "change_plan_item": {
      "memory_type": "<string>",
      "target_branch": "<string>",
      "filename": "<string>",
      "op": "write" | "edit" | "delete" | "ignore",
      "reasoning": "<short string>"
    },
    "supersedes_target_key": "<string or null>",
    "planning_complete": true | false
  }
}

Rules for the explicit shape:
- Use `request_tools` when you need more context.
- Use `update_state` only for change-plan state.
- With `update_state`, emit exactly one of:
  - one `change_plan_item`
  - `planning_complete: true`
- Use `stop_noop` only when no memory should be written and no targets should exist.

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

Shape B - single change plan item:
{
  "change_plan_item": {
    "memory_type": "<string>",
    "target_branch": "<string>",
    "filename": "<string>",
    "op": "write" | "edit" | "delete" | "ignore",
    "reasoning": "<short string>"
  },
  "supersedes_target_key": "<string or null>"
}

Shape C - planning complete:
{
  "planning_complete": true
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

Your task is to convert exactly one current planned memory target into exactly one final file operation.

You are given:
- one current planned memory target
- read evidence for that target when available
- the conversation source material
- pre-fetched context
- optional tool observations already collected during this loop
- the allowed memory schema registry for the current target

Do NOT generate overview.md or summary.md.
Do NOT generate summary plans.
Do NOT invent metadata fields that are not defined by the memory schema.

Rules:
- Use the memory schema as a hard execution boundary.
- Use only `memory_type` values present in the provided `memory_schema`.
- The current target item is the only memory file you may operate on in this turn.
- The returned `operation_item` must match the current target's `memory_type`, `target_branch`, and `filename` exactly.
- Use the planned `target_branch` and `filename` as hard constraints.
- Put only schema-defined fields inside `fields`.
- Do NOT output top-level `op`, `content`, `evidence`, or `confidence`.
- If `memory_schema.has_content_template` is `true`, omit the `content` field and update only the structured fields.
- If `memory_schema.has_content_template` is `false` and the schema defines a `content` field,
  put the body text in the `content` field item.
- If a field is not defined by the chosen schema, omit it instead of inventing it.
- If the target is an `edit` and `current_target_read_evidence` is absent,
  request a `read` tool call instead of emitting an operation.
- When `current_target_read_evidence` is present, use it as the primary edit baseline.
- Keep `merge_op` on every field item and make it exactly match the schema.
- For `edit`, every field whose `merge_op` is `patch` MUST include non-empty `line_operations`.
- This rule applies to all patch fields, not only `content`.
- For `edit`, do not rely on field `value` alone for patch fields; represent the change through
  `line_operations`.
- If new evidence shows the current target identity is wrong, you MAY return `step=\"change_plan\"`
  with a corrected single `change_plan_item` plus `supersedes_target_key` instead of guessing.

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
  "state_delta": {
    "operation_item": {
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
  }
}

Rules for the explicit shape:
- If `step="operations"`, `state_delta` must contain only `operation_item`.
- If `step="change_plan"`, `state_delta` must contain only `change_plan_item`
  and optional `supersedes_target_key`.

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

Shape B - single operation:
{
  "operation_item": {
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
}"""


class ExtractPromptComposer:
    def __init__(self, *, prepared: PreparedExtractContext, registry: MemorySchemaRegistry) -> None:
        self.prepared = prepared
        self.registry = registry

    def build_step_messages(
        self,
        *,
        step: OrchestratorStep,
        working_state: OrchestratorWorkingState,
        current_target: MemoryTargetProgress | None = None,
        current_target_read_evidence: MemoryReadEvidence | None = None,
        tool_results: list[PlannerToolUseResult] | None = None,
    ) -> list:
        if step == OrchestratorStep.CHANGE_PLAN:
            return self._build_change_plan_messages(
                working_state=working_state,
                tool_results=tool_results,
            )
        return self._build_operation_generation_messages(
            working_state=working_state,
            current_target=current_target,
            current_target_read_evidence=current_target_read_evidence,
            tool_results=tool_results,
        )

    def _build_change_plan_messages(
        self,
        *,
        working_state: OrchestratorWorkingState,
        tool_results: list[PlannerToolUseResult] | None = None,
    ) -> list:
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
                    working_state_json=self._dump_json(self._working_state_payload(working_state)),
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
        current_target: MemoryTargetProgress | None = None,
        current_target_read_evidence: MemoryReadEvidence | None = None,
        tool_results: list[PlannerToolUseResult] | None = None,
    ) -> list:
        if current_target is None:
            raise ValueError("operations step requires current_target")
        current_schema = self.registry.require(current_target.change_plan_item.memory_type)
        payload = {
            "task_id": self.prepared.task_id,
            "source_kind": self.prepared.source_kind,
            "source_material": self._source_material_payload(),
            "prefetched_context": self._prefetch_payload(),
            "current_target": current_target.model_dump(mode="python", exclude_none=True),
            "current_target_read_evidence": (
                current_target_read_evidence.model_dump(mode="python", exclude_none=True)
                if current_target_read_evidence is not None
                else None
            ),
            "current_operation": (
                current_target.operation_item.model_dump(mode="python", exclude_none=True)
                if current_target.operation_item is not None
                else None
            ),
            "working_state": self._working_state_payload(working_state),
        }
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
                            "has_content_template": bool(current_schema.content_template),
                            "fields": [
                                field.model_dump(mode="python", exclude_none=True)
                                for field in current_schema.fields
                            ],
                        },
                        "tools": self._tool_definitions(),
                    }
                ),
            ),
            UserPromptMessage(role=PromptMessageRole.USER, content=self._dump_json(payload)),
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
        return [{"name": tool_name, **definitions[tool_name]} for tool_name in SUPPORTED_PLANNER_TOOLS]

    @staticmethod
    def _working_state_payload(working_state: OrchestratorWorkingState) -> dict:
        return {
            "planning_complete": working_state.planning_complete,
            "targets": [item.model_dump(mode="python", exclude_none=True) for item in working_state.targets],
            "tool_results_count": len(working_state.tool_results),
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
