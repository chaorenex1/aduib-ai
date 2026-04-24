from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from runtime.memory.write_pipeline import run_memory_write_task_phase
from service.memory.base.contracts import (
    L0L1SummaryResult,
    MemoryChangePlanItem,
    MemorySourceRef,
    MemoryWriteTaskView,
    OrchestratorAction,
    OrchestratorStateDelta,
    PlannerToolRequest,
    PlannerToolUseResult,
)
from service.memory.base.enums import MemoryTaskPhase, MemoryTriggerType, OrchestratorStep


def _build_task_view(*, task_id: str) -> MemoryWriteTaskView:
    return MemoryWriteTaskView(
        task_id=task_id,
        trace_id="trace-extract",
        trigger_type=MemoryTriggerType.MEMORY_API,
        user_id="u1",
        agent_id="a1",
        project_id="proj-1",
        status=None,
        phase=MemoryTaskPhase.EXTRACT_OPERATIONS,
        source_ref=MemorySourceRef(
            type="memory_api", conversation_id=task_id, path=f"memory_pipeline/users/u1/sources/{task_id}.json"
        ),
        archive_ref=None,
    )


def _build_prepare_result() -> dict:
    return {
        "task_id": "task-extract",
        "phase": "prepare_extract_context",
        "source_kind": "memory_api",
        "source_hash": "sha-1",
        "source_ref": {"type": "memory_api", "conversation_id": "task-extract"},
        "user_id": "u1",
        "agent_id": "a1",
        "project_id": "proj-1",
        "messages": [{"role": "user", "content": "User prefers concise Python code and direct implementation."}],
        "text_blocks": ["User prefers concise Python code and direct implementation."],
        "prefetched_context": {
            "directory_views": [
                {"path": "users/u1/memories/preference", "entries": ["overview.md", "summary.md", "python-style.md"]}
            ],
            "file_reads": [
                {
                    "path": "users/u1/memories/preference/summary.md",
                    "content": "Prefers concise code and clear implementation patterns.",
                }
            ],
            "search_results": [
                {
                    "path": "users/u1/memories/preference/python-style.md",
                    "snippet": "Prefers clear, concise Python code.",
                }
            ],
            "already_read_paths": ["users/u1/memories/preference/summary.md"],
        },
        "schema_bundle": [
            {"memory_type": "preference", "path": "runtime/memory/schema/preference.yaml"},
            {"memory_type": "profile", "path": "runtime/memory/schema/profile.yaml"},
        ],
        "stats": {"message_count": 1, "text_block_count": 1},
    }


def test_extract_operations_runs_memory_react_orchestrator(monkeypatch: pytest.MonkeyPatch) -> None:
    identified_memories = [
        {
            "memory_type": "preference",
            "target_branch": "users/u1/memories/preference",
            "title_hint": "python-code-style",
            "confidence": 0.93,
            "reasoning": "Stable coding preference explicitly stated.",
            "evidence": ["User prefers concise Python code."],
        }
    ]
    change_plan = [
        {
            "memory_type": "preference",
            "intent": "write",
            "target_branch": "users/u1/memories/preference",
            "title_hint": "python-code-style",
            "reasoning": "Material new preference for future coding tasks.",
            "requires_existing_read": False,
            "evidence": ["User prefers concise Python code."],
        }
    ]
    operations = [
        {
            "op": "write",
            "memory_type": "preference",
            "fields": {"topic": "Python code style"},
            "content": "User prefers concise Python code and direct implementation.",
            "confidence": 0.91,
            "evidence": [
                {
                    "kind": "message",
                    "content": "User prefers concise Python code and direct implementation.",
                }
            ],
        }
    ]
    summary_result = L0L1SummaryResult(
        branch_path="users/u1/memories/preference",
        overview_md="# Preference Overview\n\nThe user consistently prefers concise Python code.",
        summary_md="Prefers concise Python code and direct implementation.",
    )

    def _fake_request_step_action(self, *, step, working_state, branch_path=None):
        if step == OrchestratorStep.CHANGE_PLAN:
            return OrchestratorAction(
                action="update_state",
                step=OrchestratorStep.CHANGE_PLAN,
                state_delta=OrchestratorStateDelta(
                    identified_memories=identified_memories,
                    change_plan=change_plan,
                ),
            )
        if step == OrchestratorStep.OPERATIONS:
            return OrchestratorAction(
                action="update_state",
                step=OrchestratorStep.OPERATIONS,
                state_delta=OrchestratorStateDelta(operations=operations),
            )
        return OrchestratorAction(
            action="update_state",
            step=OrchestratorStep.SUMMARY,
            state_delta=OrchestratorStateDelta(summary_plan=[summary_result]),
        )

    monkeypatch.setattr("runtime.memory.extract.planner.LLMPlanner._request_step_action", _fake_request_step_action)

    result = run_memory_write_task_phase(
        task_id="task-extract",
        phase=MemoryTaskPhase.EXTRACT_OPERATIONS,
        task=_build_task_view(task_id="task-extract"),
        phase_results={"prepare_extract_context": _build_prepare_result()},
    )

    assert result["phase"] == "extract_operations"
    assert result["planner_status"] == "planned"
    assert result["identified_memories"][0]["memory_type"] == "preference"
    assert result["change_plan"][0]["intent"] == "write"
    assert result["structured_operations"][0]["memory_type"] == "preference"
    assert result["structured_operations"][0]["fields"] == {"topic": "Python code style"}
    assert result["summary_plan"][0]["branch_path"] == "users/u1/memories/preference"
    assert "concise Python code" in result["summary_plan"][0]["summary_md"]
    assert result["tools_available"] == ["ls", "read", "find"]


def test_extract_operations_marks_planner_failed_when_change_plan_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "runtime.memory.extract.planner.LLMPlanner._request_step_action",
        lambda self, step, working_state, branch_path=None: (_ for _ in ()).throw(ValueError("not json")),
    )

    result = run_memory_write_task_phase(
        task_id="task-extract",
        phase=MemoryTaskPhase.EXTRACT_OPERATIONS,
        task=_build_task_view(task_id="task-extract"),
        phase_results={"prepare_extract_context": _build_prepare_result()},
    )

    assert result["phase"] == "extract_operations"
    assert result["planner_status"] == "planner_failed"
    assert result["identified_memories"] == []
    assert result["change_plan"] == []
    assert result["structured_operations"] == []
    assert result["summary_plan"] == []
    assert result["planner_error"]
    assert result["tools_available"] == ["ls", "read", "find"]


def test_extract_operations_executes_request_tools_before_final_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    change_plan_responses = iter(
        [
            OrchestratorAction(
                action="request_tools",
                step=OrchestratorStep.CHANGE_PLAN,
                tool_requests=[
                    PlannerToolRequest(
                        tool="read",
                        args={"path": "users/u1/memories/preference/python-style.md", "max_chars": 500},
                    )
                ],
            ),
            OrchestratorAction(
                action="update_state",
                step=OrchestratorStep.CHANGE_PLAN,
                state_delta=OrchestratorStateDelta(
                    identified_memories=[
                        {
                            "memory_type": "preference",
                            "target_branch": "users/u1/memories/preference",
                            "title_hint": "python-code-style",
                            "confidence": 0.95,
                            "reasoning": "Conversation and fetched file agree on a stable preference.",
                            "evidence": ["User prefers concise Python code."],
                        }
                    ],
                    change_plan=[
                        MemoryChangePlanItem(
                            memory_type="preference",
                            intent="edit",
                            target_branch="users/u1/memories/preference",
                            title_hint="python-code-style",
                            reasoning="Existing preference file should be updated rather than rewritten elsewhere.",
                            requires_existing_read=True,
                            evidence=["User prefers concise Python code."],
                        )
                    ],
                ),
            ),
        ]
    )
    operation_result = [
        {
            "op": "edit",
            "memory_type": "preference",
            "fields": {"topic": "Python code style"},
            "content": "User prefers concise Python code, direct implementation, and minimal ceremony.",
            "confidence": 0.9,
            "evidence": [
                {
                    "kind": "read",
                    "content": "Existing file says concise Python code.",
                    "path": "users/u1/memories/preference/python-style.md",
                }
            ],
        }
    ]
    summary_result = L0L1SummaryResult(
        branch_path="users/u1/memories/preference",
        overview_md="# Preference Overview\n\nThe branch captures stable coding style preferences.",
        summary_md="Prefers concise Python code and direct implementation.",
    )

    def _fake_request_step_action(self, *, step, working_state, branch_path=None):
        if step == OrchestratorStep.CHANGE_PLAN:
            return next(change_plan_responses)
        if step == OrchestratorStep.OPERATIONS:
            return OrchestratorAction(
                action="update_state",
                step=OrchestratorStep.OPERATIONS,
                state_delta=OrchestratorStateDelta(operations=operation_result),
            )
        return OrchestratorAction(
            action="update_state",
            step=OrchestratorStep.SUMMARY,
            state_delta=OrchestratorStateDelta(summary_plan=[summary_result]),
        )

    monkeypatch.setattr("runtime.memory.extract.planner.LLMPlanner._request_step_action", _fake_request_step_action)
    monkeypatch.setattr(
        "runtime.memory.extract.tools.PlannerToolExecutor.execute_sync",
        lambda self, request, message_id=None: PlannerToolUseResult(
            tool=request.tool,
            args=request.args,
            result={
                "path": request.args["path"],
                "content": "Existing file says concise Python code.",
                "line_start": 1,
                "line_end": 3,
            },
        ),
    )

    result = run_memory_write_task_phase(
        task_id="task-extract",
        phase=MemoryTaskPhase.EXTRACT_OPERATIONS,
        task=_build_task_view(task_id="task-extract"),
        phase_results={"prepare_extract_context": _build_prepare_result()},
    )

    assert result["planner_status"] == "planned"
    assert result["change_plan"][0]["intent"] == "edit"
    assert result["structured_operations"][0]["op"] == "edit"
    assert result["tools_used"] == [
        {
            "tool": "read",
            "args": {"path": "users/u1/memories/preference/python-style.md", "max_chars": 500},
            "result": {
                "path": "users/u1/memories/preference/python-style.md",
                "content": "Existing file says concise Python code.",
                "line_start": 1,
                "line_end": 3,
            },
        }
    ]
    assert result["tools_available"] == ["ls", "read", "find"]


def test_extract_operations_can_request_tools_during_operation_and_summary_steps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operation_actions = iter(
        [
            OrchestratorAction(
                action="request_tools",
                step=OrchestratorStep.OPERATIONS,
                tool_requests=[
                    PlannerToolRequest(
                        tool="read",
                        args={"path": "users/u1/memories/preference/python-style.md", "max_chars": 400},
                    )
                ],
            ),
            OrchestratorAction(
                action="update_state",
                step=OrchestratorStep.OPERATIONS,
                state_delta=OrchestratorStateDelta(
                    operations=[
                        {
                            "op": "edit",
                            "memory_type": "preference",
                            "fields": {"topic": "Python code style"},
                            "content": "User prefers concise Python code and direct implementation.",
                            "confidence": 0.9,
                            "evidence": [
                                {
                                    "kind": "read",
                                    "content": "Existing file confirms the preference.",
                                    "path": "users/u1/memories/preference/python-style.md",
                                }
                            ],
                        }
                    ],
                ),
            ),
        ]
    )
    summary_actions = iter(
        [
            OrchestratorAction(
                action="request_tools",
                step=OrchestratorStep.SUMMARY,
                tool_requests=[
                    PlannerToolRequest(
                        tool="ls",
                        args={"path": "users/u1/memories/preference", "include_files": True},
                    )
                ],
            ),
            OrchestratorAction(
                action="update_state",
                step=OrchestratorStep.SUMMARY,
                state_delta=OrchestratorStateDelta(
                    summary_plan=[
                        L0L1SummaryResult(
                            branch_path="users/u1/memories/preference",
                            overview_md="# Overview\n\nUpdated from tool-assisted summary step.",
                            summary_md="Preference branch summary after extra reads.",
                        )
                    ],
                ),
            ),
        ]
    )

    def _fake_request_step_action(self, *, step, working_state, branch_path=None):
        if step == OrchestratorStep.CHANGE_PLAN:
            return OrchestratorAction(
                action="update_state",
                step=OrchestratorStep.CHANGE_PLAN,
                state_delta=OrchestratorStateDelta(
                    identified_memories=[
                        {
                            "memory_type": "preference",
                            "target_branch": "users/u1/memories/preference",
                            "title_hint": "python-code-style",
                            "confidence": 0.95,
                            "reasoning": "Stable coding preference.",
                            "evidence": ["User prefers concise Python code."],
                        }
                    ],
                    change_plan=[
                        {
                            "memory_type": "preference",
                            "intent": "edit",
                            "target_branch": "users/u1/memories/preference",
                            "title_hint": "python-code-style",
                            "reasoning": "Existing file should be refined.",
                            "requires_existing_read": True,
                            "evidence": ["User prefers concise Python code."],
                        }
                    ],
                ),
            )
        if step == OrchestratorStep.OPERATIONS:
            return next(operation_actions)
        return next(summary_actions)

    monkeypatch.setattr("runtime.memory.extract.planner.LLMPlanner._request_step_action", _fake_request_step_action)
    monkeypatch.setattr(
        "runtime.memory.extract.tools.PlannerToolExecutor.execute_sync",
        lambda self, request, message_id=None: PlannerToolUseResult(
            tool=request.tool,
            args=request.args,
            result={"path": request.args["path"], "content": "tool-result"},
        ),
    )

    result = run_memory_write_task_phase(
        task_id="task-extract",
        phase=MemoryTaskPhase.EXTRACT_OPERATIONS,
        task=_build_task_view(task_id="task-extract"),
        phase_results={"prepare_extract_context": _build_prepare_result()},
    )

    assert result["planner_status"] == "planned"
    assert [item["tool"] for item in result["tools_used"]] == ["read", "ls"]
    assert result["structured_operations"][0]["op"] == "edit"
    assert result["summary_plan"][0]["summary_md"] == "Preference branch summary after extra reads."


def test_extract_operations_keeps_tool_failures_inside_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_request_step_action(self, *, step, working_state, branch_path=None):
        if step == OrchestratorStep.CHANGE_PLAN:
            if OrchestratorStep.CHANGE_PLAN not in working_state.completed_steps and not working_state.tool_results:
                return OrchestratorAction(
                    action="request_tools",
                    step=OrchestratorStep.CHANGE_PLAN,
                    tool_requests=[
                        PlannerToolRequest(
                            tool="read",
                            args={"path": "users/u1/memories/preference/missing.md"},
                        )
                    ],
                )
            return OrchestratorAction(
                action="update_state",
                step=OrchestratorStep.CHANGE_PLAN,
                state_delta=OrchestratorStateDelta(
                    identified_memories=[
                        {
                            "memory_type": "preference",
                            "target_branch": "users/u1/memories/preference",
                            "title_hint": "python-code-style",
                            "confidence": 0.82,
                            "reasoning": "Fallback to conversation evidence after failed read.",
                            "evidence": ["User prefers concise Python code."],
                        }
                    ],
                    change_plan=[
                        {
                            "memory_type": "preference",
                            "intent": "write",
                            "target_branch": "users/u1/memories/preference",
                            "title_hint": "python-code-style",
                            "reasoning": "Proceed despite failed read.",
                            "requires_existing_read": False,
                            "evidence": ["User prefers concise Python code."],
                        }
                    ],
                ),
            )
        if step == OrchestratorStep.OPERATIONS:
            return OrchestratorAction(
                action="update_state",
                step=OrchestratorStep.OPERATIONS,
                state_delta=OrchestratorStateDelta(
                    operations=[
                        {
                            "op": "write",
                            "memory_type": "preference",
                            "fields": {"topic": "Python code style"},
                            "content": "User prefers concise Python code.",
                            "confidence": 0.8,
                            "evidence": [{"kind": "message", "content": "User prefers concise Python code."}],
                        }
                    ],
                ),
            )
        return OrchestratorAction(
            action="update_state",
            step=OrchestratorStep.SUMMARY,
            state_delta=OrchestratorStateDelta(
                summary_plan=[
                    L0L1SummaryResult(
                        branch_path="users/u1/memories/preference",
                        overview_md="# Overview\n\nGenerated after a failed tool call.",
                        summary_md="Summary generated after a failed tool call.",
                    )
                ],
            ),
        )

    monkeypatch.setattr("runtime.memory.extract.planner.LLMPlanner._request_step_action", _fake_request_step_action)
    monkeypatch.setattr(
        "runtime.memory.extract.tools.PlannerToolExecutor.execute_sync",
        lambda self, request, message_id=None: PlannerToolUseResult(
            tool=request.tool,
            args=request.args,
            result={"error": "file not found", "builtin_tool": "mem-read"},
        ),
    )

    result = run_memory_write_task_phase(
        task_id="task-extract",
        phase=MemoryTaskPhase.EXTRACT_OPERATIONS,
        task=_build_task_view(task_id="task-extract"),
        phase_results={"prepare_extract_context": _build_prepare_result()},
    )

    assert result["planner_status"] == "planned"
    assert result["tools_used"][0]["result"]["error"] == "file not found"
    assert result["change_plan"][0]["intent"] == "write"
    assert result["summary_plan"][0]["branch_path"] == "users/u1/memories/preference"


def test_extract_operations_runs_unified_next_action_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    actions = iter(
        [
            OrchestratorAction(
                action="request_tools",
                step=OrchestratorStep.CHANGE_PLAN,
                tool_requests=[
                    PlannerToolRequest(
                        tool="read",
                        args={"path": "users/u1/memories/preference/python-style.md", "max_chars": 500},
                    )
                ],
            ),
            OrchestratorAction(
                action="update_state",
                step=OrchestratorStep.CHANGE_PLAN,
                state_delta=OrchestratorStateDelta(
                    identified_memories=[
                        {
                            "memory_type": "preference",
                            "target_branch": "users/u1/memories/preference",
                            "title_hint": "python-code-style",
                            "confidence": 0.95,
                            "reasoning": "Stable preference.",
                            "evidence": ["User prefers concise Python code."],
                        }
                    ],
                    change_plan=[
                        MemoryChangePlanItem(
                            memory_type="preference",
                            intent="write",
                            target_branch="users/u1/memories/preference",
                            title_hint="python-code-style",
                            reasoning="New stable preference.",
                            requires_existing_read=False,
                            evidence=["User prefers concise Python code."],
                        )
                    ],
                ),
            ),
            OrchestratorAction(
                action="update_state",
                step=OrchestratorStep.OPERATIONS,
                state_delta=OrchestratorStateDelta(
                    operations=[
                        {
                            "op": "write",
                            "memory_type": "preference",
                            "fields": {"topic": "Python code style"},
                            "content": "User prefers concise Python code and direct implementation.",
                            "confidence": 0.9,
                            "evidence": [{"kind": "message", "content": "User prefers concise Python code."}],
                        }
                    ],
                ),
            ),
            OrchestratorAction(
                action="update_state",
                step=OrchestratorStep.SUMMARY,
                state_delta=OrchestratorStateDelta(
                    summary_plan=[
                        L0L1SummaryResult(
                            branch_path="users/u1/memories/preference",
                            overview_md="# Overview\n\nPreference overview.",
                            summary_md="Preference summary.",
                        )
                    ],
                ),
            ),
            OrchestratorAction(action="finalize"),
        ]
    )

    monkeypatch.setattr(
        "runtime.memory.extract.planner.LLMPlanner.next_action",
        lambda self, working_state: next(actions),
    )
    monkeypatch.setattr(
        "runtime.memory.extract.tools.PlannerToolExecutor.execute_sync",
        lambda self, request, message_id=None: PlannerToolUseResult(
            tool=request.tool,
            args=request.args,
            result={"path": request.args["path"], "content": "Existing file says concise Python code."},
        ),
    )

    result = run_memory_write_task_phase(
        task_id="task-extract",
        phase=MemoryTaskPhase.EXTRACT_OPERATIONS,
        task=_build_task_view(task_id="task-extract"),
        phase_results={"prepare_extract_context": _build_prepare_result()},
    )

    assert result["planner_status"] == "planned"
    assert result["identified_memories"][0]["memory_type"] == "preference"
    assert result["structured_operations"][0]["op"] == "write"
    assert result["summary_plan"][0]["branch_path"] == "users/u1/memories/preference"
    assert result["tools_used"][0]["tool"] == "read"
