from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from runtime.memory.extract.structured_output import parse_step_action
from service.memory.base.enums import OrchestratorStep


def test_parse_step_action_returns_stop_noop_for_empty_change_plan() -> None:
    action = parse_step_action(
        step=OrchestratorStep.CHANGE_PLAN,
        raw_text='{"identified_memories": [], "change_plan": []}',
    )

    assert action.action == "stop_noop"


def test_parse_step_action_returns_request_tools_for_operation_step() -> None:
    action = parse_step_action(
        step=OrchestratorStep.OPERATIONS,
        raw_text='{"tool_requests":[{"tool":"read","args":{"path":"users/u1/memories/preference/summary.md"}}]}',
    )

    assert action.action == "request_tools"
    assert action.step == OrchestratorStep.OPERATIONS
    assert action.tool_requests[0].tool == "read"


def test_parse_step_action_returns_update_summary_for_summary_step() -> None:
    action = parse_step_action(
        step=OrchestratorStep.SUMMARY,
        raw_text=(
            '{"branch_path":"users/u1/memories/preference",'
            '"overview_md":"# Overview","summary_md":"Summary"}'
        ),
    )

    assert action.action == "update_state"
    assert action.step == OrchestratorStep.SUMMARY
    assert action.state_delta is not None
    assert action.state_delta.summary_plan is not None
    assert action.state_delta.summary_plan[0].branch_path == "users/u1/memories/preference"
