import asyncio
import importlib.util
import sys
import types
from pathlib import Path

from runtime.memory.types import MemorySignalType

_MODULE_PATH = Path(__file__).resolve().parents[1] / "service" / "learning_signal_service.py"
_SPEC = importlib.util.spec_from_file_location("learning_signal_service_module", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
LearningSignalService = _MODULE.LearningSignalService


class _FakeEmitter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def emit_async(self, event: str, **payload) -> None:
        self.calls.append((event, payload))


class _FakeContext:
    def __init__(self, emitter: _FakeEmitter) -> None:
        self._emitter = emitter

    def get(self) -> _FakeEmitter:
        return self._emitter


def _load_module(module_name: str, relative_path: str):
    module_path = Path(__file__).resolve().parents[1] / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_emit_batch_normalizes_signal_payload(monkeypatch) -> None:
    emitter = _FakeEmitter()
    fake_event_manager = types.ModuleType("event.event_manager")
    fake_event_manager.event_manager_context = _FakeContext(emitter)
    monkeypatch.setitem(sys.modules, "event.event_manager", fake_event_manager)

    asyncio.run(
        LearningSignalService.emit_batch(
            [
                {
                    "user_id": "user-1",
                    "signal_type": MemorySignalType.MEMORY_EXPOSED,
                    "source_id": "memory-1",
                    "value": "0.75",
                }
            ]
        )
    )

    assert len(emitter.calls) == 1
    event_name, payload = emitter.calls[0]
    assert event_name == "learning_signal_persist_batch"
    assert payload["signals"] == [
        {
            "user_id": "user-1",
            "agent_id": "",
            "signal_type": MemorySignalType.MEMORY_EXPOSED.value,
            "source_id": "memory-1",
            "value": 0.75,
            "context": {},
        }
    ]


def test_emit_memory_signals_builds_batch(monkeypatch) -> None:
    captured: list[dict] = []

    async def _fake_emit_batch(cls, signals: list[dict]) -> None:
        captured.extend(signals)

    monkeypatch.setattr(LearningSignalService, "emit_batch", classmethod(_fake_emit_batch))

    asyncio.run(
        LearningSignalService.emit_memory_signals(
            user_id="user-1",
            signal_type=MemorySignalType.MEMORY_EXPOSED,
            memory_ids=["memory-1", "", "memory-2"],
            agent_id="agent-1",
            context={"query_hash": "abc123"},
            value=0.1,
            value_by_source={"memory-1": 0.8},
        )
    )

    assert captured == [
        {
            "user_id": "user-1",
            "agent_id": "agent-1",
            "signal_type": MemorySignalType.MEMORY_EXPOSED,
            "source_id": "memory-1",
            "value": 0.8,
            "context": {"query_hash": "abc123"},
        },
        {
            "user_id": "user-1",
            "agent_id": "agent-1",
            "signal_type": MemorySignalType.MEMORY_EXPOSED,
            "source_id": "memory-2",
            "value": 0.1,
            "context": {"query_hash": "abc123"},
        },
    ]


def test_long_term_memory_returns_structured_results(monkeypatch) -> None:
    from runtime.memory.types import MemoryRetrieveResult

    fake_manager_module = types.ModuleType("runtime.memory.manager")

    class _FakeMemoryManager:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def retrieve_memories(self, retrieve):
            return [
                MemoryRetrieveResult(memory_id="memory-1", content="alpha", score=0.8),
                MemoryRetrieveResult(memory_id="memory-2", content="beta", score=0.4),
            ]

    fake_manager_module.MemoryManager = _FakeMemoryManager
    monkeypatch.setitem(sys.modules, "runtime.memory.manager", fake_manager_module)

    embeddings_memory_module = _load_module(
        "embeddings_memory_test_module",
        "runtime/agent/memory/embeddings_memory.py",
    )
    long_term_memory = embeddings_memory_module.LongTermEmbeddingsMemory(
        user_id="user-1",
        agent_id="agent-1",
        top_k=2,
        score_threshold=0.5,
    )

    results = asyncio.run(long_term_memory.get_long_term_memory("where did we leave off"))

    assert [(item.memory_id, item.content, item.score) for item in results] == [
        ("memory-1", "alpha", 0.8),
        ("memory-2", "beta", 0.4),
    ]


def test_prompt_markup_builds_and_extracts_memory_tags() -> None:
    from runtime.memory.types import MemoryRetrieveResult

    prompt_markup_module = _load_module(
        "prompt_markup_test_module",
        "runtime/agent/memory/prompt_markup.py",
    )

    block = prompt_markup_module.build_memory_prompt_block(
        [
            MemoryRetrieveResult(memory_id="memory-1", content="alpha", score=0.8),
            MemoryRetrieveResult(memory_id="memory-2", content="beta", score=0.4),
        ]
    )
    assert 'memory id="memory-1"' in block
    assert "<memory_used_ids>comma-separated-memory-ids</memory_used_ids>" in block

    cleaned, used_ids = prompt_markup_module.extract_used_memory_ids(
        "answer body\n<memory_used_ids>memory-1,memory-2</memory_used_ids>"
    )
    assert cleaned == "answer body"
    assert used_ids == ["memory-1", "memory-2"]

    sanitized = prompt_markup_module.sanitize_memory_markup(
        f"user ask\n{block}\nassistant\n<memory_used_ids>memory-1</memory_used_ids>"
    )
    assert sanitized == "user ask\nassistant"
