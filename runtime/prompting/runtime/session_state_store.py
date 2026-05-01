from __future__ import annotations

import copy


class PromptSessionStateStore:
    _store: dict[str, dict[str, object]] = {}

    def load(self, session_id: str | int) -> dict[str, object]:
        key = str(session_id)
        return copy.deepcopy(self._store.get(key, {}))

    def save(self, session_id: str | int, state: dict[str, object]) -> None:
        self._store[str(session_id)] = copy.deepcopy(state)
