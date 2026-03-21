from __future__ import annotations

import logging

from runtime.memory.trace import RetrievalTrace

logger = logging.getLogger(__name__)


class MemoryTraceMixin:
    def _emit_trace(self, trace: RetrievalTrace) -> None:
        """异步派发检索统计，失败时静默（不影响主流程）。"""
        try:
            from app_factory import event_manager

            event_manager.emit("memory_retrieval_logged", trace=trace.to_dict())
        except Exception:
            logger.debug("Failed to emit retrieval trace", exc_info=True)
