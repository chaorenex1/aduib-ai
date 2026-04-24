from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from runtime.memory.extract.planner import LLMPlanner
from runtime.memory.schema.registry import MemorySchemaRegistry
from service.memory.base.contracts import (
    L0L1SummaryResult,
    MemoryChangePlanItem,
    OrchestratorAction,
    OrchestratorStateDelta,
    OrchestratorWorkingState,
    PreparedExtractContext,
)
from service.memory.base.enums import OrchestratorStep


def _build_prepared() -> PreparedExtractContext:
    return PreparedExtractContext(
        task_id="task-1",
        source_kind="memory_api",
        source_hash="sha-1",
        source_ref={"type": "memory_api", "conversation_id": "task-1"},
        user_id="u1",
        agent_id="a1",
        project_id="p1",
        messages=[{"role": "user", "content": "User prefers concise Python code."}],
        text_blocks=["User prefers concise Python code."],
        prefetched_context={
            "directory_views": [],
            "file_reads": [],
            "search_results": [],
            "already_read_paths": [],
        },
    )


def test_next_action_delegates_change_plan_to_unified_step_request(monkeypatch) -> None:
    planner = LLMPlanner(prepared=_build_prepared(), registry=MemorySchemaRegistry.load())
    captured: dict[str, object] = {}

    def _fake_request_step_action(self, *, step, working_state, branch_path=None):
        captured["step"] = step
        captured["branch_path"] = branch_path
        return OrchestratorAction(action="stop_noop")

    monkeypatch.setattr(LLMPlanner, "_request_step_action", _fake_request_step_action)

    action = planner.next_action(working_state=OrchestratorWorkingState())

    assert action.action == "stop_noop"
    assert captured == {"step": OrchestratorStep.CHANGE_PLAN, "branch_path": None}


def test_next_action_delegates_operations_to_unified_step_request(monkeypatch) -> None:
    planner = LLMPlanner(prepared=_build_prepared(), registry=MemorySchemaRegistry.load())
    captured: dict[str, object] = {}

    def _fake_request_step_action(self, *, step, working_state, branch_path=None):
        captured["step"] = step
        captured["branch_path"] = branch_path
        return OrchestratorAction(action="finalize")

    monkeypatch.setattr(LLMPlanner, "_request_step_action", _fake_request_step_action)

    action = planner.next_action(
        working_state=OrchestratorWorkingState(
            completed_steps=[OrchestratorStep.CHANGE_PLAN],
            change_plan=[
                MemoryChangePlanItem(
                    memory_type="preference",
                    intent="write",
                    target_branch="users/u1/memories/preference",
                    title_hint="python-style",
                    reasoning="Stable preference.",
                    evidence=["User prefers concise Python code."],
                )
            ],
        )
    )

    assert action.action == "finalize"
    assert captured == {"step": OrchestratorStep.OPERATIONS, "branch_path": None}


def test_next_action_delegates_summary_to_unified_step_request(monkeypatch) -> None:
    planner = LLMPlanner(prepared=_build_prepared(), registry=MemorySchemaRegistry.load())
    captured: dict[str, object] = {}

    def _fake_request_step_action(self, *, step, working_state, branch_path=None):
        captured["step"] = step
        captured["branch_path"] = branch_path
        return OrchestratorAction(
            action="update_state",
            step=OrchestratorStep.SUMMARY,
            state_delta=OrchestratorStateDelta(
                summary_plan=[
                    L0L1SummaryResult(
                        branch_path=str(branch_path),
                        overview_md="# Overview",
                        summary_md="Summary",
                    )
                ]
            ),
        )

    monkeypatch.setattr(LLMPlanner, "_request_step_action", _fake_request_step_action)

    action = planner.next_action(
        working_state=OrchestratorWorkingState(
            completed_steps=[OrchestratorStep.CHANGE_PLAN, OrchestratorStep.OPERATIONS],
            change_plan=[
                MemoryChangePlanItem(
                    memory_type="preference",
                    intent="write",
                    target_branch="users/u1/memories/preference",
                    title_hint="python-style",
                    reasoning="Stable preference.",
                    evidence=["User prefers concise Python code."],
                )
            ],
        )
    )

    assert action.action == "update_state"
    assert captured == {"step": OrchestratorStep.SUMMARY, "branch_path": "users/u1/memories/preference"}


def test_next_action_finalizes_when_no_pending_steps(monkeypatch) -> None:
    planner = LLMPlanner(prepared=_build_prepared(), registry=MemorySchemaRegistry.load())

    def _unexpected_request_step_action(self, *, step, working_state, branch_path=None):
        raise AssertionError("should not request another planner step")

    monkeypatch.setattr(LLMPlanner, "_request_step_action", _unexpected_request_step_action)

    action = planner.next_action(
        working_state=OrchestratorWorkingState(
            completed_steps=[OrchestratorStep.CHANGE_PLAN, OrchestratorStep.OPERATIONS],
            change_plan=[
                MemoryChangePlanItem(
                    memory_type="preference",
                    intent="write",
                    target_branch="users/u1/memories/preference",
                    title_hint="python-style",
                    reasoning="Stable preference.",
                    evidence=["User prefers concise Python code."],
                )
            ],
            summary_plan=[
                L0L1SummaryResult(
                    branch_path="users/u1/memories/preference",
                    overview_md="# Overview",
                    summary_md="Summary",
                )
            ],
        )
    )

    assert action.action == "finalize"
