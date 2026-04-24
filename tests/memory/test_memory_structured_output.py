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


def test_parse_step_action_accepts_explicit_orchestrator_action_payload() -> None:
    payload = (
        '{"action":"update_state","step":"change_plan","state_delta":'
        '{"identified_memories":[{"memory_type":"preference","target_branch":"users/u1/memories/preference",'
        '"title_hint":"python-style","confidence":0.9,"reasoning":"stable","evidence":["prefers concise Python"]}],'
        '"change_plan":[{"memory_type":"preference","intent":"edit","target_branch":"users/u1/memories/preference",'
        '"title_hint":"python-style","reasoning":"revised","requires_existing_read":true,'
        '"evidence":["prefers concise Python"]}]}}'
    )
    action = parse_step_action(
        step=OrchestratorStep.OPERATIONS,
        raw_text=payload,
    )

    assert action.action == "update_state"
    assert action.step == OrchestratorStep.CHANGE_PLAN
    assert action.state_delta is not None
    assert action.state_delta.change_plan is not None
    assert action.state_delta.change_plan[0].intent == "edit"


def test_parse_step_action_converts_empty_explicit_change_plan_update_to_stop_noop() -> None:
    action = parse_step_action(
        step=OrchestratorStep.CHANGE_PLAN,
        raw_text='{"action":"update_state","step":"change_plan","state_delta":{}}',
    )

    assert action.action == "stop_noop"


def test_parse_step_action_normalizes_explicit_operation_payload() -> None:
    payload = (
        '{"action":"update_state","step":"operations","state_delta":{"operations":['
        '{"op":"write","memory_type":"preference","fields":{"topic":"Python style","bogus":"drop-me"},'
        '"content":"User prefers concise Python code.","confidence":0.9,'
        '"evidence":[{"kind":"message","content":"prefers concise Python"}]}]}}'
    )
    action = parse_step_action(
        step=OrchestratorStep.OPERATIONS,
        raw_text=payload,
    )

    assert action.action == "update_state"
    assert action.state_delta is not None
    assert action.state_delta.operations is not None
    assert action.state_delta.operations[0].fields == {"topic": "Python style"}
