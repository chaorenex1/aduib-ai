from __future__ import annotations

from runtime.prompting.contracts.trace import PromptTrace


class PromptTraceStore:
    _store: dict[str, PromptTrace] = {}

    def save(self, trace: PromptTrace) -> None:
        self._store[trace.trace_id] = trace.model_copy(deep=True)

    def get(self, trace_id: str) -> PromptTrace | None:
        trace = self._store.get(trace_id)
        return trace.model_copy(deep=True) if trace else None
