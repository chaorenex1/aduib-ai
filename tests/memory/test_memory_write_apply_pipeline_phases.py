from __future__ import annotations

import sys
from collections.abc import Generator
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from component.storage.base_storage import BaseStorage, StorageEntry, storage_manager
from runtime.memory.write_pipeline import run_memory_write_task_phase
from service.memory.base.contracts import MemorySourceRef, MemoryWriteTaskView
from service.memory.base.enums import MemoryTaskPhase, MemoryTriggerType


class _InMemoryStorage(BaseStorage):
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def save(self, filename: str, data: bytes):
        self.files[self._normalize(filename)] = data

    def load(self, filename: str) -> bytes:
        return self.files[self._normalize(filename)]

    def load_stream(self, filename: str) -> Generator[bytes, None, None]:
        yield self.load(filename)

    def delete(self, filename: str):
        normalized = self._normalize(filename)
        prefix = f"{normalized}/"
        for key in [key for key in self.files if key == normalized or key.startswith(prefix)]:
            self.files.pop(key, None)

    def exists(self, filename: str) -> bool:
        normalized = self._normalize(filename)
        prefix = f"{normalized}/"
        return normalized in self.files or any(key.startswith(prefix) for key in self.files)

    def download(self, filename: str, target_file_path: str):
        Path(target_file_path).write_bytes(self.load(filename))

    def size(self, filename: str) -> int:
        return len(self.load(filename))

    def list_dir(self, path: str, recursive: bool = False) -> list[StorageEntry]:
        normalized = self._normalize(path)
        prefix = f"{normalized}/" if normalized else ""
        files = sorted(key for key in self.files if key.startswith(prefix))
        entries: dict[str, StorageEntry] = {}

        for key in files:
            relative = key[len(prefix) :]
            parts = relative.split("/")
            if recursive:
                for index in range(len(parts) - 1):
                    dir_path = "/".join(part for part in [normalized, *parts[: index + 1]] if part)
                    entries[dir_path] = StorageEntry(path=dir_path, is_file=False, is_dir=True, size=None)
                entries[key] = StorageEntry(path=key, is_file=True, is_dir=False, size=len(self.files[key]))
                continue

            if len(parts) == 1:
                entries[key] = StorageEntry(path=key, is_file=True, is_dir=False, size=len(self.files[key]))
            else:
                dir_path = "/".join(part for part in [normalized, parts[0]] if part)
                entries[dir_path] = StorageEntry(path=dir_path, is_file=False, is_dir=True, size=None)

        return sorted(entries.values(), key=lambda entry: entry.path)

    @staticmethod
    def _normalize(path: str) -> str:
        return path.replace("\\", "/").strip("/")


def _build_task_view(*, task_id: str) -> MemoryWriteTaskView:
    return MemoryWriteTaskView(
        task_id=task_id,
        trace_id="trace-apply",
        trigger_type=MemoryTriggerType.MEMORY_API,
        user_id="u1",
        agent_id="a1",
        project_id="proj-1",
        status=None,
        phase=MemoryTaskPhase.BUILD_STAGED_WRITE_SET,
        source_ref=MemorySourceRef(
            type="memory_api", conversation_id=task_id, path=f"memory_pipeline/users/u1/sources/{task_id}.json"
        ),
        archive_ref=None,
    )


def _build_resolved_phase_results() -> dict[str, dict]:
    return {
        "prepare_extract_context": {
            "task_id": "task-apply",
            "phase": "prepare_extract_context",
            "source_kind": "memory_api",
            "source_hash": "sha-3",
            "source_ref": {"type": "memory_api", "conversation_id": "task-apply"},
            "user_id": "u1",
            "agent_id": "a1",
            "project_id": "proj-1",
            "messages": [],
            "text_blocks": [],
            "prefetched_context": {
                "directory_views": [],
                "file_reads": [],
                "search_results": [],
                "already_read_paths": [],
            },
            "schema_bundle": [],
            "stats": {"message_count": 0, "text_block_count": 0},
        },
        "resolve_operations": {
            "task_id": "task-apply",
            "phase": "resolve_operations",
            "resolved_operations": [
                {
                    "op": "edit",
                    "memory_type": "preference",
                    "target_path": "users/u1/memories/preference/Python-code-style.md",
                    "target_name": "Python-code-style.md",
                    "file_exists": True,
                    "merge_strategy": "patch",
                    "memory_mode": "simple",
                    "fields": {"topic": "Python code style"},
                    "field_merge_ops": {"topic": "immutable", "content": "patch"},
                    "content": "Prefer concise Python code.",
                    "confidence": 0.8,
                    "evidence": [{"kind": "message", "content": "Prefer concise Python code."}],
                    "schema_path": "runtime/memory/schema/preference.yaml",
                },
                {
                    "op": "write",
                    "memory_type": "tool",
                    "target_path": "agent/a1/memories/tool/read-file.md",
                    "target_name": "read-file.md",
                    "file_exists": False,
                    "merge_strategy": "template_fields",
                    "memory_mode": "template",
                    "fields": {
                        "tool_name": "read file",
                        "static_desc": "Read a file from storage.",
                        "total_calls": 3,
                        "success_count": 3,
                        "fail_count": 0,
                        "total_time_ms": 120,
                        "total_tokens": 45,
                        "best_for": "Inspecting a single file.",
                        "optimal_params": "Use precise paths.",
                        "common_failures": "Missing files.",
                        "recommendation": "Read before editing.",
                        "guidelines": "## Guidelines\n### Good Cases\n- Debugging\n### Bad Cases\n- Guessing",
                    },
                    "field_merge_ops": {
                        "tool_name": "immutable",
                        "static_desc": "replace",
                        "total_calls": "sum",
                        "success_count": "sum",
                        "fail_count": "sum",
                        "total_time_ms": "sum",
                        "total_tokens": "sum",
                        "best_for": "patch",
                        "optimal_params": "patch",
                        "common_failures": "patch",
                        "recommendation": "patch",
                        "guidelines": "patch",
                    },
                    "content": "",
                    "confidence": 0.9,
                    "evidence": [{"kind": "message", "content": "Use read_file before editing."}],
                    "content_template": (
                        "Tool: {tool_name}\n\n"
                        'Static Description:\n"{static_desc}"\n\n'
                        "Tool Memory Context:\n"
                        "Based on {total_calls} historical calls:\n"
                        "- Success rate: {success_rate}% "
                        "({success_count} successful, {fail_count} failed)\n"
                        "- Avg time: {avg_time}, Avg tokens: {avg_tokens}\n"
                        "- Best for: {best_for}\n"
                        "- Optimal params: {optimal_params}\n"
                        "- Common failures: {common_failures}\n"
                        "- Recommendation: {recommendation}\n\n"
                        "{guidelines}\n"
                    ),
                    "schema_path": "runtime/memory/schema/tool.yaml",
                },
            ],
            "navigation_scopes": ["agent/a1/memories/tool", "users/u1/memories/preference"],
            "metadata_scopes": ["agent/a1", "users/u1"],
        },
        "extract_operations": {
            "task_id": "task-apply",
            "phase": "extract_operations",
            "planner_status": "planned",
            "summary_plan": [
                {
                    "branch_path": "users/u1/memories/preference",
                    "overview_md": "# Preference Overview\n\nPlanner-authored branch overview.",
                    "summary_md": "Planner-authored branch summary.",
                }
            ],
        },
    }


def test_build_staged_write_set_generates_manifest_and_rollback(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr(storage_manager, "storage_instance", storage)
    storage.write_text_atomic(
        "memory_pipeline/users/u1/memories/preference/Python-code-style.md",
        "---\nmemory_id: mem_existing\nkind: preference\ntopic: Python code style\n---\n\nExisting preference body.\n",
    )

    result = run_memory_write_task_phase(
        task_id="task-apply",
        phase=MemoryTaskPhase.BUILD_STAGED_WRITE_SET,
        task=_build_task_view(task_id="task-apply"),
        phase_results=_build_resolved_phase_results(),
    )

    assert result["phase"] == "build_staged_write_set"
    assert [item["target_path"] for item in result["memory_mutations"]] == [
        "users/u1/memories/preference/Python-code-style.md",
        "agent/a1/memories/tool/read-file.md",
    ]
    assert result["memory_mutations"][0]["desired_content"].startswith("---\n")
    assert "Prefer concise Python code." in result["memory_mutations"][0]["desired_content"]
    assert result["memory_mutations"][1]["desired_content"].startswith("---\n")
    assert "Tool: read file" in result["memory_mutations"][1]["desired_content"]
    assert [item["directory_path"] for item in result["navigation_mutations"]] == ["users/u1/memories/preference"]
    assert (
        result["navigation_mutations"][0]["desired_overview_md"]
        == "# Preference Overview\n\nPlanner-authored branch overview."
    )
    assert result["navigation_mutations"][0]["desired_summary_md"] == "Planner-authored branch summary."
    assert result["metadata_mutations"] == [{"scope_path": "agent/a1"}, {"scope_path": "users/u1"}]
    assert (
        result["rollback_plan"]["snapshot"]["roots"][0]["path"]
        == "memory_pipeline/users/u1/memories/preference/Python-code-style.md"
    )


def test_apply_memory_files_writes_files_and_journal(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr(storage_manager, "storage_instance", storage)
    storage.write_text_atomic(
        "memory_pipeline/users/u1/memories/preference/Python-code-style.md",
        "---\nmemory_id: mem_existing\nkind: preference\ntopic: Python code style\n---\n\nExisting preference body.\n",
    )

    stage_result = run_memory_write_task_phase(
        task_id="task-apply",
        phase=MemoryTaskPhase.BUILD_STAGED_WRITE_SET,
        task=_build_task_view(task_id="task-apply"),
        phase_results=_build_resolved_phase_results(),
    )
    phase_results = {**_build_resolved_phase_results(), "build_staged_write_set": stage_result}

    result = run_memory_write_task_phase(
        task_id="task-apply",
        phase=MemoryTaskPhase.APPLY_MEMORY_FILES,
        task=_build_task_view(task_id="task-apply"),
        phase_results=phase_results,
    )

    preference_doc = storage.read_text("memory_pipeline/users/u1/memories/preference/Python-code-style.md")
    tool_doc = storage.read_text("memory_pipeline/agent/a1/memories/tool/read-file.md")

    assert result["phase"] == "apply_memory_files"
    assert result["journal_ref"].endswith("task-apply-apply-memory-files.json")
    assert result["applied_memory_files"] == [
        "users/u1/memories/preference/Python-code-style.md",
        "agent/a1/memories/tool/read-file.md",
    ]
    assert "Existing preference body." in preference_doc
    assert "Prefer concise Python code." in preference_doc
    assert "memory_id: mem_existing" in preference_doc
    assert "Tool: read file" in tool_doc
    assert "Success rate: 100" in tool_doc


def test_refresh_navigation_writes_only_supported_navigation_dirs(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr(storage_manager, "storage_instance", storage)
    storage.write_text_atomic(
        "memory_pipeline/users/u1/memories/preference/Python-code-style.md",
        "---\nmemory_id: mem_existing\nkind: preference\ntitle: Python code style\n---\n\nExisting preference body.\n",
    )
    storage.write_text_atomic(
        "memory_pipeline/agent/a1/memories/tool/read-file.md",
        "---\nmemory_id: mem_tool\nkind: tool\ntitle: read file\n---\n\nTool doc.\n",
    )

    navigation_input = {
        **_build_resolved_phase_results(),
        "build_staged_write_set": {
            "navigation_mutations": [
                {
                    "directory_path": "users/u1/memories/preference",
                    "overview_path": "users/u1/memories/preference/overview.md",
                    "summary_path": "users/u1/memories/preference/summary.md",
                },
                {
                    "directory_path": "agent/a1/memories/tool",
                    "overview_path": "agent/a1/memories/tool/overview.md",
                    "summary_path": "agent/a1/memories/tool/summary.md",
                },
            ]
        },
    }

    result = run_memory_write_task_phase(
        task_id="task-apply",
        phase=MemoryTaskPhase.REFRESH_NAVIGATION,
        task=_build_task_view(task_id="task-apply"),
        phase_results=navigation_input,
    )

    assert result["navigation_files"] == [
        "users/u1/memories/preference/overview.md",
        "users/u1/memories/preference/summary.md",
    ]
    assert storage.exists("memory_pipeline/users/u1/memories/preference/overview.md") is True
    assert storage.exists("memory_pipeline/users/u1/memories/preference/summary.md") is True
    assert storage.exists("memory_pipeline/agent/a1/memories/tool/overview.md") is False


def test_refresh_navigation_prefers_summary_plan_content_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr(storage_manager, "storage_instance", storage)
    storage.write_text_atomic(
        "memory_pipeline/users/u1/memories/preference/Python-code-style.md",
        "---\nmemory_id: mem_existing\nkind: preference\ntitle: Python code style\n---\n\nExisting preference body.\n",
    )

    navigation_input = {
        **_build_resolved_phase_results(),
        "build_staged_write_set": {
            "navigation_mutations": [
                {
                    "directory_path": "users/u1/memories/preference",
                    "overview_path": "users/u1/memories/preference/overview.md",
                    "summary_path": "users/u1/memories/preference/summary.md",
                    "desired_overview_md": "# Planner Overview\n\nGenerated by the ReAct summary step.",
                    "desired_summary_md": "Planner summary for the preference branch.",
                }
            ]
        },
    }

    result = run_memory_write_task_phase(
        task_id="task-apply",
        phase=MemoryTaskPhase.REFRESH_NAVIGATION,
        task=_build_task_view(task_id="task-apply"),
        phase_results=navigation_input,
    )

    overview_doc = storage.read_text("memory_pipeline/users/u1/memories/preference/overview.md")
    summary_doc = storage.read_text("memory_pipeline/users/u1/memories/preference/summary.md")

    assert result["navigation_files"] == [
        "users/u1/memories/preference/overview.md",
        "users/u1/memories/preference/summary.md",
    ]
    assert "Planner Overview" in overview_doc
    assert "Generated by the ReAct summary step." in overview_doc
    assert "planner_summary" in overview_doc
    assert "Planner summary for the preference branch." in summary_doc


def test_refresh_metadata_builds_projection_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr(storage_manager, "storage_instance", storage)
    storage.write_text_atomic(
        "memory_pipeline/users/u1/memories/preference/Python-code-style.md",
        (
            "---\n"
            "memory_id: mem_existing\n"
            "kind: preference\n"
            "title: Python code style\n"
            "topic: Python code style\n"
            "tags:\n"
            "  - preference\n"
            "created_at: '2026-04-23T00:00:00+00:00'\n"
            "updated_at: '2026-04-23T00:00:00+00:00'\n"
            "visibility: internal\n"
            "status: active\n"
            "---\n\n"
            "Existing preference body.\n"
        ),
    )
    storage.write_text_atomic(
        "memory_pipeline/agent/a1/memories/tool/read-file.md",
        (
            "---\n"
            "memory_id: mem_tool\n"
            "kind: tool\n"
            "title: read file\n"
            "tool_name: read file\n"
            "tags:\n"
            "  - tool\n"
            "created_at: '2026-04-23T00:00:00+00:00'\n"
            "updated_at: '2026-04-23T00:00:00+00:00'\n"
            "visibility: internal\n"
            "status: active\n"
            "---\n\n"
            "Tool doc.\n"
        ),
    )
    storage.write_text_atomic(
        "memory_pipeline/users/u1/memories/preference/overview.md",
        "---\nkind: overview\ntitle: Preference Overview\nscope_path: users/u1/memories/preference\n---\n\nOverview.\n",
    )
    storage.write_text_atomic(
        "memory_pipeline/users/u1/memories/preference/summary.md",
        "---\nkind: summary\ntitle: Preference Summary\nscope_path: users/u1/memories/preference\n---\n\nSummary.\n",
    )
    captured: dict[str, object] = {}

    def _fake_persist(*, task_id: str, projection: dict) -> None:
        captured["task_id"] = task_id
        captured["projection"] = projection

    monkeypatch.setattr("runtime.memory.apply.metadata_refresh._persist_metadata_projection", _fake_persist)

    result = run_memory_write_task_phase(
        task_id="task-apply",
        phase=MemoryTaskPhase.REFRESH_METADATA,
        task=_build_task_view(task_id="task-apply"),
        phase_results={
            **_build_resolved_phase_results(),
            "build_staged_write_set": {"metadata_mutations": [{"scope_path": "agent/a1"}, {"scope_path": "users/u1"}]},
        },
    )

    assert result["phase"] == "refresh_metadata"
    assert result["metadata_scopes"] == ["agent/a1", "users/u1"]
    assert result["record_counts"]["memory_index"] == 2
    assert result["record_counts"]["memory_directory_index"] >= 2
    assert captured["task_id"] == "task-apply"
    projection = captured["projection"]
    assert len(projection["memory_index"]) == 2
    assert projection["memory_index"][0]["memory_id"] in {"mem_existing", "mem_tool"}
