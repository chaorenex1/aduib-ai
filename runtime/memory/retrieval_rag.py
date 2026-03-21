from __future__ import annotations

import logging
from datetime import UTC, datetime
from difflib import SequenceMatcher

from runtime.memory.trace import RetrievalTrace
from runtime.memory.types import MemoryRetrieve, MemoryRetrieveResult

logger = logging.getLogger(__name__)


def _is_valid_uuid(value: str) -> bool:
    import uuid

    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


class MemoryRagRetrievalMixin:
    async def _retrieve_rag(self, retrieve: MemoryRetrieve) -> list[MemoryRetrieveResult]:
        """RAG 被动式检索：向量匹配 → MemoryRecord 反查 → 排序截断。"""
        import asyncio

        from models.document import KnowledgeBase
        from models.engine import get_db
        from models.memory import MemoryBase, MemoryRecord
        from service.knowledge_base_service import KnowledgeBaseService

        filters = dict(retrieve.filters or {})
        score_threshold: float = float(filters.get("score_threshold", retrieve.score_threshold or 0.0))
        retrieval_method = str(filters.get("retrieval_method") or "semantics").strip().lower()
        retrieval_kwargs: dict[str, object] = {"retrieval_method": retrieval_method}
        if filters.get("weights"):
            retrieval_kwargs["weights"] = filters["weights"]
        if filters.get("reranking_mode"):
            retrieval_kwargs["reranking_mode"] = filters["reranking_mode"]

        with get_db() as session:
            q = session.query(MemoryBase).filter(MemoryBase.user_id == self.user_id, MemoryBase.deleted == 0)
            if filters.get("domain"):
                q = q.filter(MemoryBase.domain == filters["domain"])
            memory_bases = q.all()
            for mb in memory_bases:
                session.expunge(mb)

        if not memory_bases:
            return []

        kb_id_to_mb: dict[str, MemoryBase] = {mb.mem_kb_id: mb for mb in memory_bases}
        with get_db() as session:
            kbs = session.query(KnowledgeBase).filter(KnowledgeBase.id.in_(list(kb_id_to_mb.keys()))).all()
            for kb in kbs:
                session.expunge(kb)

        if not kbs:
            return []

        tasks = [
            KnowledgeBaseService.retrieve_from_kb(
                kb=kb,
                query=retrieve.query,
                top_k=retrieve.top_k * 2,
                score_threshold=score_threshold,
                **retrieval_kwargs,
            )
            for kb in kbs
        ]
        results_per_kb = await asyncio.gather(*tasks, return_exceptions=True)

        doc_score: dict[str, float] = {}
        doc_content: dict[str, str] = {}
        for result in results_per_kb:
            if isinstance(result, Exception):
                logger.warning("KB retrieve failed: %s", result)
                continue
            for doc in result:
                doc_id = str(doc.metadata.get("doc_id", ""))
                if not doc_id:
                    continue
                score = float(doc.metadata.get("score", 0.0))
                if doc_id not in doc_score or score > doc_score[doc_id]:
                    doc_score[doc_id] = score
                    doc_content[doc_id] = doc.page_content if hasattr(doc, "page_content") else doc.content

        if not doc_score:
            return []

        with get_db() as session:
            import uuid

            doc_uuids = [uuid.UUID(did) for did in doc_score if _is_valid_uuid(did)]
            q = session.query(MemoryRecord).filter(
                MemoryRecord.kb_doc_id.in_(doc_uuids),
                MemoryRecord.deleted == 0,
            )
            if filters.get("tags"):
                from sqlalchemy.dialects.postgresql import JSONB

                q = q.filter(MemoryRecord.tags.cast(JSONB).contains(filters["tags"]))
            records = q.all()
            for r in records:
                session.expunge(r)

        output: list[MemoryRetrieveResult] = []
        for record in records:
            doc_id_str = str(record.kb_doc_id) if record.kb_doc_id else ""
            score = doc_score.get(doc_id_str, 0.0)
            content = doc_content.get(doc_id_str, "")
            output.append(
                MemoryRetrieveResult(
                    memory_id=str(record.id),
                    content=content,
                    score=score,
                    metadata={
                        "domain": record.domain,
                        "type": record.type,
                        "source": record.source,
                        "topic": str(record.topic) if record.topic else None,
                        "tags": record.tags or [],
                        "access_count": record.access_count or 0,
                        "quality_score": record.quality_score,
                        "created_at": record.created_at.isoformat() if record.created_at else None,
                        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
                        "accessed_at": record.accessed_at.isoformat() if record.accessed_at else None,
                    },
                )
            )

        output.sort(key=lambda x: x.score or 0.0, reverse=True)
        if output:
            import uuid as _uuid

            hit_ids = [_uuid.UUID(r.memory_id) for r in output if _is_valid_uuid(r.memory_id)]
            if hit_ids:
                with get_db() as session:
                    session.query(MemoryRecord).filter(MemoryRecord.id.in_(hit_ids)).update(
                        {
                            MemoryRecord.access_count: MemoryRecord.access_count + 1,
                            MemoryRecord.accessed_at: datetime.now(UTC),
                        },
                        synchronize_session=False,
                    )
                    session.commit()
        return output[: retrieve.top_k]

    async def _graph_prefetch(self, query: str, threshold: float = 0.7) -> set[str]:
        """图谱预取：基于 topic 字符串相似度召回候选记忆。"""
        try:
            from sqlalchemy import func

            from models.engine import get_db
            from models.memory import MemoryBase, MemoryRecord

            normalized_query = self._normalize_topic(query)
            if not normalized_query:
                return set()

            with get_db() as session:
                topic_rows = (
                    session.query(
                        MemoryRecord.topic,
                        func.count().label("memory_count"),
                        func.max(MemoryRecord.updated_at).label("updated_at"),
                    )
                    .join(MemoryRecord.memory_base)
                    .filter(
                        MemoryBase.user_id == self.user_id,
                        MemoryRecord.deleted == 0,
                        MemoryRecord.topic.isnot(None),
                        MemoryRecord.topic != "",
                    )
                    .group_by(MemoryRecord.topic)
                    .all()
                )

                matched_topics: list[str] = []
                scored_topics: list[tuple[float, str]] = []
                for row in topic_rows:
                    topic = (row.topic or "").strip()
                    topic_key = self._normalize_topic(topic)
                    if not topic_key:
                        continue
                    similarity = (
                        1.0
                        if (topic_key in normalized_query or normalized_query in topic_key)
                        else SequenceMatcher(None, normalized_query, topic_key).ratio()
                    )
                    if similarity < threshold:
                        continue
                    scored_topics.append((similarity + min(row.memory_count or 0, 10) * 0.01, topic))

                if scored_topics:
                    matched_topics = [topic for _, topic in sorted(scored_topics, reverse=True)[:10]]
                if not matched_topics:
                    return set()

                memory_rows = (
                    session.query(MemoryRecord.id)
                    .join(MemoryRecord.memory_base)
                    .filter(
                        MemoryBase.user_id == self.user_id,
                        MemoryRecord.deleted == 0,
                        MemoryRecord.topic.in_(matched_topics),
                    )
                    .order_by(MemoryRecord.updated_at.desc())
                    .limit(50)
                    .all()
                )
                return {str(memory_id) for (memory_id,) in memory_rows}

        except Exception:
            logger.warning("Graph prefetch failed, skipping", exc_info=True)
            return set()

    async def _graph_expand_neighbors(
        self,
        memory_ids: list[str],
        existing_ids: set[str],
        retrieve: MemoryRetrieve,
        base_scores: dict[str, float],
        decay: float = 0.7,
    ) -> list[MemoryRetrieveResult]:
        """图谱邻居扩展：沿 SHARES_TOPIC/SHARES_TAG 边 1 跳，返回邻居记忆。失败时静默返回空列表。"""
        from component.graph.base_graph import GraphManager
        from runtime.memory.graph.knowledge_graph import KnowledgeGraphLayer

        if not memory_ids:
            return []
        try:
            graph_store = GraphManager(graph_name=f"{self.user_id}_memory_graph")
            kg = KnowledgeGraphLayer(graph_store=graph_store)
            rows = await kg.get_neighbor_memory_refs(
                memory_ids=memory_ids,
                exclude_ids=existing_ids,
                user_id=self.user_id,
                limit=retrieve.top_k * 3,
            )
        except Exception:
            logger.warning("Graph neighbor expansion failed, skipping", exc_info=True)
            return []
        if not rows:
            return []
        max_rag_score = max(base_scores.values(), default=0.5)
        n = max(len(memory_ids), 1)
        results: list[MemoryRetrieveResult] = []
        for row in rows:
            mid = row.get("id", "")
            if not mid:
                continue
            hop_count = float(row.get("hop_count", 1))
            normalized = min(hop_count / n, 1.0)
            avg_edge_weight = float(row.get("avg_edge_weight") or 1.0)
            score = max_rag_score * decay * avg_edge_weight * (0.5 + 0.5 * normalized)
            results.append(
                MemoryRetrieveResult(
                    memory_id=mid,
                    content=row.get("summary", ""),
                    score=score,
                    metadata={
                        "domain": row.get("memory_domain", ""),
                        "type": row.get("memory_type", ""),
                        "source": "graph_expansion",
                    },
                )
            )
        return results

    async def _retrieve_rag_with_graph(
        self, retrieve: MemoryRetrieve, prefetch_threshold: float = 0.7
    ) -> tuple[list[MemoryRetrieveResult], dict[str, int]]:
        """Graph-RAG Hybrid：并行预取 + RAG 加权 + 邻居扩展。"""
        import asyncio

        stats: dict[str, int] = {
            "graph_prefetch_count": 0,
            "graph_boost_count": 0,
            "graph_expansion_count": 0,
            "candidate_total_raw": 0,
            "candidate_total_unique": 0,
            "candidate_count": 0,
        }

        rag_results, graph_candidate_ids = await asyncio.gather(
            self._retrieve_rag(retrieve),
            self._graph_prefetch(retrieve.query, threshold=prefetch_threshold),
            return_exceptions=True,
        )

        if isinstance(rag_results, Exception):
            logger.error("RAG retrieval failed: %s", rag_results)
            return [], stats
        if isinstance(graph_candidate_ids, Exception):
            graph_candidate_ids = set()

        stats["graph_prefetch_count"] = len(graph_candidate_ids)

        base_scores: dict[str, float] = {}
        boosted: list[MemoryRetrieveResult] = []
        for result in rag_results:
            score = result.score or 0.0
            if result.memory_id in graph_candidate_ids:
                score = min(1.0, score * 1.2)
                stats["graph_boost_count"] += 1
            base_scores[result.memory_id] = score
            boosted.append(result.model_copy(update={"score": score}))

        neighbor_results = await self._graph_expand_neighbors(
            memory_ids=[result.memory_id for result in boosted],
            existing_ids={result.memory_id for result in boosted},
            retrieve=retrieve,
            base_scores=base_scores,
        )

        stats["graph_expansion_count"] = len(neighbor_results)

        merged: dict[str, MemoryRetrieveResult] = {result.memory_id: result for result in boosted}
        for result in neighbor_results:
            if result.memory_id not in merged:
                merged[result.memory_id] = result
        stats["candidate_total_raw"] = len(boosted) + len(neighbor_results)
        stats["candidate_total_unique"] = len(merged)
        results = sorted(merged.values(), key=lambda x: x.score or 0.0, reverse=True)[: retrieve.top_k]
        stats["candidate_count"] = len(results)
        return results, stats

    def _build_rag_trace(
        self,
        retrieve: MemoryRetrieve,
        results: list[MemoryRetrieveResult],
        stats: dict[str, int],
        query_hash: str,
        latency_total_ms: int,
    ) -> RetrievalTrace:
        from collections import Counter

        from runtime.memory.trace import ResultDetail

        trace = RetrievalTrace(
            user_id=self.user_id,
            agent_id=retrieve.agent_id or None,
            project_id=retrieve.project_id or None,
            retrieve_type="rag",
            top_k=retrieve.top_k,
            query_hash=query_hash,
            react_enabled=False,
        )
        trace.latency_step2_ms = latency_total_ms
        trace.candidate_total_raw = int(stats.get("candidate_total_raw", len(results)))
        trace.candidate_total_unique = int(stats.get("candidate_total_unique", len(results)))
        trace.final_count = len(results)

        if results:
            scores = sorted(result.score or 0.0 for result in results)
            trace.final_score_avg = sum(scores) / len(scores)
            trace.final_score_p50 = scores[len(scores) // 2]
            trace.final_score_p10 = scores[max(0, len(scores) // 10)]
            trace.domain_dist = dict(Counter(result.metadata.get("domain", "") for result in results))
            trace.source_dist = dict(Counter(result.metadata.get("source", "rag") for result in results))
            trace.type_dist = dict(Counter(result.metadata.get("type", "") for result in results))

        for rank, result in enumerate(results):
            retrieval_source = "graph_expansion" if result.metadata.get("source") == "graph_expansion" else "rag"
            trace.result_details.append(
                ResultDetail(
                    memory_id=result.memory_id,
                    hit_count=1,
                    evidence_count=1,
                    rag_score=result.score or 0.0,
                    from_expansion=retrieval_source == "graph_expansion",
                    final_score=result.score,
                    final_rank=rank,
                    memory_domain=result.metadata.get("domain", ""),
                    memory_type=result.metadata.get("type", ""),
                    memory_source=result.metadata.get("source", ""),
                    retrieval_sources=[retrieval_source],
                )
            )

        trace.latency_total_ms = latency_total_ms
        return trace
