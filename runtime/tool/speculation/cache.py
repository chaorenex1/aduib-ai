import hashlib
import json
import logging
from typing import Optional

from runtime.tool.entities.tool_entities import ToolInvokeResult

logger = logging.getLogger(__name__)


class SpeculativeToolCache:
    """Per-request cache for speculative tool execution results.

    Lifetime: single request. Keyed by (tool_name, params) -> SHA-256.
    """

    def __init__(self, max_size: int = 50):
        self._store: dict[str, ToolInvokeResult] = {}
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    @staticmethod
    def make_key(tool_name: str, params: dict) -> str:
        raw = json.dumps({"name": tool_name, "params": params}, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, tool_name: str, params: dict) -> Optional[ToolInvokeResult]:
        key = self.make_key(tool_name, params)
        result = self._store.get(key)
        if result is not None:
            self._hits += 1
        else:
            self._misses += 1
        return result

    def put(self, tool_name: str, params: dict, result: ToolInvokeResult) -> None:
        if len(self._store) >= self._max_size:
            logger.debug("Speculative cache full (%d), skipping put for %s", self._max_size, tool_name)
            return
        key = self.make_key(tool_name, params)
        self._store[key] = result

    def has(self, tool_name: str, params: dict) -> bool:
        return self.make_key(tool_name, params) in self._store

    @property
    def stats(self) -> dict:
        return {"size": len(self._store), "hits": self._hits, "misses": self._misses}

    def clear(self) -> None:
        self._store.clear()
        self._hits = 0
        self._misses = 0
