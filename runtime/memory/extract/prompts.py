from __future__ import annotations

import json

from runtime.entities import PromptMessageRole, SystemPromptMessage, UserPromptMessage
from service.memory.base.contracts import (
    OrchestratorWorkingState,
    PlannerToolUseResult,
    PreparedExtractContext,
)
from service.memory.base.enums import OrchestratorStep

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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PLANNING PROTOCOL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You must follow this workflow in order:

1. Consume pre-fetched context before requesting any tools.
   - Read directory views to understand branch structure.
   - Read pre-fetched L0/L1 files and other already-read files before deciding more reads are needed.
   - Use search hints and already-read paths as planning evidence.

2. Use the memory schema as a hard planning boundary.
   - Map each candidate memory to an allowed `memory_type`.
   - Map each candidate memory to an allowed `target_branch`.
   - Use schema field expectations and directory conventions to judge whether a safe plan is possible.
   - If no schema-aligned mapping exists, prefer `ignore` instead of inventing a type or branch.

3. Decide the minimum safe change plan.
   - Identify memory-worthy items from the conversation plus prefetch evidence.
   - Decide whether each item should be `write`, `edit`, `delete`, or `ignore`.
   - Prefer `edit` only when existing branch/file context is materially relevant.
   - Mark `requires_existing_read=true` when an edit decision still depends on more file context.

4. Request tools only as a fallback.
   - Request tools only when prefetch + schema + current tool observations are insufficient for a safe plan.
   - Prefer the narrowest tool call that can unblock the decision.
   - Do not re-read paths already present in `already_read_paths`
     unless the current decision explicitly requires fresher or more specific context.

5. Output only change-plan state.
   - You are planning memory changes, not generating operations or summaries.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DECISION RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- One conversation may yield multiple memory items.
- Use only supported memory types and supported target branches.
- If a memory is weak, duplicated, ephemeral, or not useful for future retrieval, mark it as `ignore`.
- Use `edit` only when existing memory context is relevant
  and the evidence suggests refinement rather than a brand-new memory file.
- Treat pre-fetched context as the default evidence source before tools.
- If schema constraints and prefetch evidence are enough, do not request tools.
- If existing branch/file context is needed beyond prefetch, request tools instead of guessing.
- Stay faithful to the source material and prefetched context.
- Never invent facts, entities, decisions, or preferences not grounded in evidence.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOOL USAGE RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You may request only built-in read-only tools.

Use tools when:
- existing memory content may need to be edited and the needed file is not already covered by prefetch
- current context is insufficient to decide between write/edit/delete/ignore after consuming prefetch and schema
- branch state or nearby files matter for a safe planning decision and prefetch did not already answer the question

Do not request tools when:
- the conversation + prefetch + schema already give sufficient evidence
- the plan is already obvious and low-risk
- you are only trying to confirm something speculative without clear benefit
- you would only repeat information already present in `already_read_paths`
  or prior tool observations

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
  "step": "change_plan" | "operations" | "summary",
  "tool_requests": [{"tool": "ls" | "read" | "find", "args": {...}}],
  "state_delta": {
    "identified_memories": [...],
    "change_plan": [...],
    "operations": [...],
    "summary_plan": [...]
  }
}

Rules for the explicit shape:
- Use `request_tools` when you need more context.
- Use `update_state` when you are updating any orchestrator state.
- Use `stop_noop` when nothing should be written.
- You MAY emit `step="change_plan"` even if the current focus later in the loop
  is operations or summary when new evidence forces a plan revision.

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
  "identified_memories": [
    {
      "memory_type": "<string>",
      "target_branch": "<string>",
      "title_hint": "<string>",
      "confidence": <number>,
      "reasoning": "<short string>",
      "evidence": ["<short excerpt>", "..."]
    }
  ],
  "change_plan": [
    {
      "memory_type": "<string>",
      "intent": "write" | "edit" | "delete" | "ignore",
      "target_branch": "<string>",
      "title_hint": "<string>",
      "reasoning": "<short string>",
      "requires_existing_read": <true|false>,
      "evidence": ["<short excerpt>", "..."]
    }
  ]
}

Confidence must be a number in [0, 1].
Keep reasoning concise and audit-friendly.
"""

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

You are given:
- a validated memory change plan
- the conversation source material
- pre-fetched context
- optional tool observations already collected during this loop
- the allowed memory schema registry

Your task is to convert the accepted change plan into final memory operations.

Output ONLY valid JSON.
No markdown.
No code fences.
No explanation outside the JSON object.

Preferred shape - explicit orchestrator action:
{
  "action": "request_tools" | "update_state",
  "step": "change_plan" | "operations" | "summary",
  "tool_requests": [{"tool": "ls" | "read" | "find", "args": {...}}],
  "state_delta": {
    "identified_memories": [...],
    "change_plan": [...],
    "operations": [...],
    "summary_plan": [...]
  }
}

Rules for the explicit shape:
- Prefer `step="operations"` for normal operation updates.
- If new evidence forces a change-plan correction, you MAY return `step="change_plan"` instead of guessing.

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

Shape B - operations:
{
  "operations": [
    {
      "op": "write" | "edit" | "delete",
      "memory_type": "<string>",
      "fields": {"<field_name>": "<value>"},
      "content": "<string>",
      "evidence": [
        {
          "kind": "message" | "read" | "search",
          "content": "<short excerpt>",
          "path": "<optional path>"
        }
      ],
      "confidence": <number>
    }
  ]
}

Request tools instead of guessing when:
- an `edit` depends on confirming the current file contents
- nearby file names or branch structure are needed to choose safe fields/content
- the prefetched context is insufficient to emit a safe final operation
"""

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
  "state_delta": {
    "identified_memories": [...],
    "change_plan": [...],
    "operations": [...],
    "summary_plan": [...]
  }
}

Rules for the explicit shape:
- Prefer `step="summary"` for normal summary updates.
- If new evidence from the current branch forces a plan or operation correction,
  you MAY return `step="change_plan"` or `step="operations"` instead.

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
        tool_results: list[PlannerToolUseResult] | None = None,
    ) -> list:
        messages = [
            SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=MEMORY_OPERATION_GENERATION_PROMPT),
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
                        "source_kind": self.prepared.source_kind,
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
            "identified_memories": [
                item.model_dump(mode="python", exclude_none=True) for item in working_state.identified_memories
            ],
            "change_plan": [item.model_dump(mode="python", exclude_none=True) for item in working_state.change_plan],
            "operations": [item.model_dump(mode="python", exclude_none=True) for item in working_state.operations],
            "summary_plan": [item.model_dump(mode="python", exclude_none=True) for item in working_state.summary_plan],
            "completed_steps": list(working_state.completed_steps),
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
