from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from runtime.entities import PromptMessageRole
from runtime.memory.extract.prompts import ExtractPromptComposer
from runtime.memory.schema.registry import MemorySchemaRegistry
from service.memory.base.contracts import PlannerToolUseResult, PreparedExtractContext


def _build_prepared() -> PreparedExtractContext:
    return PreparedExtractContext(
        task_id="task-1",
        source_kind="conversation",
        source_hash="sha-1",
        source_ref={"type": "conversation", "conversation_id": "codex:sess-1"},
        user_id="u1",
        agent_id="a1",
        project_id="p1",
        messages=[{"role": "user", "content": "User prefers concise Python code."}],
        text_blocks=["User prefers concise Python code."],
        prefetched_context={
            "directory_views": [{"path": "users/u1/memories/preference", "entries": ["overview.md", "summary.md"]}],
            "file_reads": [{"path": "users/u1/memories/preference/summary.md", "content": "Existing summary"}],
            "search_results": [{"path": "users/u1/memories/preference/python-style.md", "score": 0.92}],
            "already_read_paths": ["users/u1/memories/preference/summary.md"],
        },
    )


def test_change_plan_prompt_composer_separates_runtime_context_and_task_input() -> None:
    composer = ExtractPromptComposer(prepared=_build_prepared(), registry=MemorySchemaRegistry.load())

    messages = composer.build_change_plan_messages()

    assert len(messages) == 3
    assert messages[0].role == PromptMessageRole.SYSTEM
    assert messages[1].role == PromptMessageRole.SYSTEM
    assert messages[2].role == PromptMessageRole.USER

    import json

    runtime_context = json.loads(messages[1].content)
    assert "memory_schema" in runtime_context
    assert "tools" in runtime_context
    assert "tool_observations" not in runtime_context

    task_input = messages[2].content
    assert "Conversation Source Material" in task_input
    assert "Pre-fetched Context" in task_input
    assert "Current Change-Planning State" in task_input
    assert "memory_schema" not in task_input
    assert '"tools"' not in task_input


def test_change_plan_prompt_composer_puts_tool_results_in_observation_message() -> None:
    composer = ExtractPromptComposer(prepared=_build_prepared(), registry=MemorySchemaRegistry.load())

    messages = composer.build_change_plan_messages(
        tool_results=[
            PlannerToolUseResult(
                tool="read",
                args={"path": "users/u1/memories/preference/python-style.md"},
                result={"content": "Existing file says concise Python code."},
            )
        ]
    )

    assert len(messages) == 4
    observation = messages[3].content
    assert "Tool Observations" in observation
    assert '"tool": "read"' in observation
    assert "memory_schema" not in observation
    assert '"tools"' not in observation
