from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from runtime.memory.extract.tools import SUPPORTED_PLANNER_TOOLS
from service.memory.base.contracts import (
    ChangePlanStepResult,
    ExtractedMemoryOperation,
    ExtractOperationsPhaseResult,
    L0L1SummaryResult,
    MemoryChangePlanItem,
    MemoryChangePlanResult,
    MemoryOperationGenerationResult,
    OrchestratorAction,
    OrchestratorWorkingState,
    PlannerToolRequest,
    PlannerToolUseResult,
    ReasoningTraceStep,
)


def test_memory_change_plan_result_validates_and_exports_json_schema() -> None:
    result = MemoryChangePlanResult(
        identified_memories=[
            {
                "memory_type": "preference",
                "target_branch": "users/u1/memories/preference",
                "title_hint": "python-style",
                "confidence": 0.92,
                "reasoning": "Stable coding preference mentioned repeatedly.",
                "evidence": ["I prefer concise Python code."],
            }
        ],
        change_plan=[
            MemoryChangePlanItem(
                memory_type="preference",
                intent="write",
                target_branch="users/u1/memories/preference",
                title_hint="python-style",
                reasoning="New stable preference not present in fetched context.",
                requires_existing_read=False,
                evidence=["I prefer concise Python code."],
            )
        ],
    )

    payload = result.model_dump(mode="python")
    assert payload["identified_memories"][0]["memory_type"] == "preference"
    assert payload["change_plan"][0]["intent"] == "write"

    schema = json.loads(MemoryChangePlanResult.json_schema())
    assert "identified_memories" in schema["properties"]
    assert "change_plan" in schema["properties"]


def test_memory_operation_generation_result_wraps_structured_operations() -> None:
    result = MemoryOperationGenerationResult(
        operations=[
            ExtractedMemoryOperation(
                op="write",
                memory_type="task",
                fields={"task_name": "refactor-memory-pipeline"},
                content="Refactor the memory pipeline to use a ReAct orchestrator.",
                evidence=[{"kind": "message", "content": "Refactor the memory pipeline."}],
                confidence=0.88,
            )
        ]
    )

    payload = result.model_dump(mode="python")
    assert payload["operations"][0]["op"] == "write"
    assert payload["operations"][0]["fields"]["task_name"] == "refactor-memory-pipeline"

    schema = json.loads(MemoryOperationGenerationResult.json_schema())
    assert "operations" in schema["properties"]


def test_l0_l1_summary_result_requires_branch_path_and_documents() -> None:
    result = L0L1SummaryResult(
        branch_path="users/u1/memories/preference",
        overview_md="# Preference Overview\n\nThe user consistently prefers concise Python code.",
        summary_md="Prefers concise Python code and direct implementation.",
    )

    assert result.branch_path == "users/u1/memories/preference"
    assert "Preference Overview" in result.overview_md
    assert "concise Python code" in result.summary_md

    schema = json.loads(L0L1SummaryResult.json_schema())
    assert sorted(schema["required"]) == ["branch_path", "overview_md", "summary_md"]


def test_memory_change_plan_item_rejects_invalid_intent() -> None:
    with pytest.raises(ValidationError):
        MemoryChangePlanItem(
            memory_type="preference",
            intent="merge",
            target_branch="users/u1/memories/preference",
            title_hint="python-style",
            reasoning="invalid",
            requires_existing_read=False,
            evidence=["evidence"],
        )


def test_change_plan_step_result_requires_exactly_one_branch() -> None:
    with pytest.raises(ValidationError):
        ChangePlanStepResult()

    step = ChangePlanStepResult(
        tool_requests=[PlannerToolRequest(tool="read", args={"path": "users/u1/memories/preference/summary.md"})]
    )
    assert step.change_plan is None
    assert step.tool_requests[0].tool == "read"


def test_extract_operations_phase_result_wraps_typed_outputs() -> None:
    result = ExtractOperationsPhaseResult(
        task_id="task-1",
        planner_status="planned",
        identified_memories=[
            {
                "memory_type": "preference",
                "target_branch": "users/u1/memories/preference",
                "title_hint": "python-style",
                "confidence": 0.9,
                "reasoning": "stable preference",
                "evidence": ["prefers concise Python"],
            }
        ],
        change_plan=[
            {
                "memory_type": "preference",
                "intent": "write",
                "target_branch": "users/u1/memories/preference",
                "title_hint": "python-style",
                "reasoning": "new stable memory",
                "requires_existing_read": False,
                "evidence": ["prefers concise Python"],
            }
        ],
        structured_operations=[
            {
                "op": "write",
                "memory_type": "preference",
                "fields": {"topic": "Python style"},
                "content": "User prefers concise Python code.",
                "evidence": [{"kind": "message", "content": "prefers concise Python"}],
                "confidence": 0.88,
            }
        ],
        summary_plan=[
            {
                "branch_path": "users/u1/memories/preference",
                "overview_md": "# Overview",
                "summary_md": "Summary",
            }
        ],
        tools_available=["ls", "read", "find"],
        tools_used=[
            PlannerToolUseResult(
                tool="read",
                args={"path": "users/u1/memories/preference/python-style.md"},
                result={"content": "existing"},
            )
        ],
        reasoning_trace=[ReasoningTraceStep(step="change_plan", metadata={"planned_change_count": 1})],
    )

    payload = result.model_dump(mode="python")
    assert payload["tools_used"][0]["tool"] == "read"
    assert payload["reasoning_trace"][0]["step"] == "change_plan"


def test_planner_tool_request_exports_supported_read_tools() -> None:
    request = PlannerToolRequest(tool="find", args={"query": "python code style", "path": "users/u1/memories"})
    assert request.tool == "find"
    assert SUPPORTED_PLANNER_TOOLS == ("ls", "read", "find")


def test_orchestrator_action_requires_payload_for_update_actions() -> None:
    with pytest.raises(ValidationError):
        OrchestratorAction(action="update_change_plan")

    action = OrchestratorAction(
        action="request_tools",
        tool_requests=[PlannerToolRequest(tool="read", args={"path": "users/u1/memories/preference/summary.md"})],
    )
    assert action.action == "request_tools"
    assert action.tool_requests[0].tool == "read"


def test_orchestrator_working_state_tracks_pending_summary_branches() -> None:
    state = OrchestratorWorkingState(
        change_plan=[
            {
                "memory_type": "preference",
                "intent": "write",
                "target_branch": "users/u1/memories/preference",
                "title_hint": "python-style",
                "reasoning": "stable preference",
                "requires_existing_read": False,
                "evidence": ["prefers concise Python"],
            },
            {
                "memory_type": "task",
                "intent": "ignore",
                "target_branch": "users/u1/memories/task",
                "title_hint": "ignore-task",
                "reasoning": "ephemeral",
                "requires_existing_read": False,
                "evidence": ["ephemeral task"],
            },
        ]
    )
    assert state.pending_summary_branches() == ["users/u1/memories/preference"]

    state.summary_plan.append(
        L0L1SummaryResult(
            branch_path="users/u1/memories/preference",
            overview_md="# Overview",
            summary_md="Summary",
        )
    )
    assert state.pending_summary_branches() == []
