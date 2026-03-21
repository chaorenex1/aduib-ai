from __future__ import annotations

import asyncio as _aio_rm

from runtime.memory.retrieval_rag import MemoryRagRetrievalMixin
from runtime.memory.retrieval_react import MemoryReactRetrievalMixin
from runtime.memory.retrieval_trace import MemoryTraceMixin
from runtime.memory.trace import RetrievalTrace
from runtime.memory.types import MemoryRetrieve, MemoryRetrieveResult, MemoryRetrieveType, MemorySignalType


class MemoryRetrievalMixin(MemoryReactRetrievalMixin, MemoryRagRetrievalMixin, MemoryTraceMixin):
    async def retrieve_memories(self, retrieve: MemoryRetrieve) -> list[MemoryRetrieveResult]:
        import time

        retrieve_type = "llm" if retrieve.retrieve_type == MemoryRetrieveType.LLM else "rag"
        if retrieve.retrieve_type == MemoryRetrieveType.LLM:
            results = await self._retrieve_llm_react(retrieve)
            query_hash = RetrievalTrace.hash_query(retrieve.query or "")
        else:
            started_at = time.monotonic()
            results, stats = await self._retrieve_rag_with_graph(retrieve)
            latency_total_ms = int((time.monotonic() - started_at) * 1000)
            query_hash = RetrievalTrace.hash_query(retrieve.query or "")
            trace = self._build_rag_trace(
                retrieve=retrieve,
                results=results,
                stats=stats,
                query_hash=query_hash,
                latency_total_ms=latency_total_ms,
            )
            self._emit_trace(trace)

        try:
            if results:
                from service.learning_signal_service import LearningSignalService

                memory_ids = [str(r.memory_id) for r in results if getattr(r, "memory_id", None)]
                value_by_source = {
                    str(r.memory_id): float(r.score or 0.0) for r in results if getattr(r, "memory_id", None)
                }
                if memory_ids:
                    _aio_rm.ensure_future(
                        LearningSignalService.emit_memory_signals(
                            user_id=self.user_id,
                            signal_type=MemorySignalType.MEMORY_EXPOSED,
                            memory_ids=memory_ids,
                            value_by_source=value_by_source,
                            context={"query_hash": query_hash, "retrieve_type": retrieve_type},
                        )
                    )
        except Exception:
            pass

        return results
