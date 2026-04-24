from __future__ import annotations

import json

from runtime.entities import PromptMessageRole, SystemPromptMessage, UserPromptMessage
from service.memory.base.contracts import (
    MemoryChangePlanResult,
    MemoryOperationGenerationResult,
    OrchestratorWorkingState,
    PlannerToolUseResult,
    PreparedExtractContext,
)

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
PRIMARY RESPONSIBILITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You must determine:
1. What memory-worthy items exist in the source material
2. Which memory type each item belongs to
3. Which target branch each item belongs to
4. What the intended change should be:
   - write
   - edit
   - delete
   - ignore
5. Whether additional reading is required before a safe plan can be made

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DECISION RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- One conversation may yield multiple memory items.
- Use only supported memory types and supported target branches.
- If a memory is weak, duplicated, ephemeral, or not useful for future retrieval, mark it as `ignore`.
- Use `edit` only when existing memory context is relevant
  and the evidence suggests refinement rather than a brand-new memory file.
- If existing branch/file context is needed, request tools instead of guessing.
- Stay faithful to the source material and prefetched context.
- Never invent facts, entities, decisions, or preferences not grounded in evidence.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOOL USAGE RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You may request only built-in read-only tools.

Use tools when:
- existing memory content may need to be edited
- current context is insufficient to decide between write/edit/delete/ignore
- branch state or nearby files matter for a safe planning decision

Do not request tools when:
- the conversation already gives sufficient evidence
- the plan is obvious and low-risk
- you are only trying to confirm something speculative without clear benefit

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Output ONLY valid JSON.
No markdown.
No code fences.
No explanation outside the JSON object.

You must output EXACTLY ONE of the following shapes:

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
Messages:
{messages_json}

Text Blocks:
{text_blocks_json}

Pre-fetched Context
===================
{prefetched_context_json}

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

You must output EXACTLY ONE of the following shapes:

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

You must output EXACTLY ONE of the following shapes:

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

    def build_change_plan_messages(
        self,
        *,
        working_state: OrchestratorWorkingState | None = None,
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
                    messages_json=self._dump_json(self.prepared.messages),
                    text_blocks_json=self._dump_json(self.prepared.text_blocks),
                    prefetched_context_json=self._dump_json(self.prepared.prefetched_context),
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

    def build_operation_generation_messages(
        self,
        *,
        working_state: OrchestratorWorkingState,
        tool_results: list[PlannerToolUseResult] | None = None,
    ) -> list:
        change_plan = MemoryChangePlanResult(
            identified_memories=working_state.identified_memories,
            change_plan=working_state.change_plan,
        )
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

    def build_l0_l1_summary_messages(
        self,
        *,
        working_state: OrchestratorWorkingState,
        branch_path: str,
        tool_results: list[PlannerToolUseResult] | None = None,
    ) -> list:
        change_plan = MemoryChangePlanResult(
            identified_memories=working_state.identified_memories,
            change_plan=working_state.change_plan,
        )
        operations = MemoryOperationGenerationResult(operations=working_state.operations)
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
        responsibilities = {
            "ls": "Inspect branch or directory structure",
            "read": "Read a specific file",
            "find": "Find likely relevant memory file paths by name/path semantics",
        }
        return [
            {"name": tool_name, "responsibility": responsibilities[tool_name]}
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
