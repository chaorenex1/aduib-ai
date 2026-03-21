from __future__ import annotations

import logging

from runtime.generator.generator import LLMGenerator
from runtime.memory.types import MemoryRetrieve, MemoryRetrieveResult

logger = logging.getLogger(__name__)


class MemoryReactRetrievalMixin:
    async def _load_memory_structure(self) -> tuple[dict | None, list[str], list[str]]:
        from sqlalchemy import func

        from models.engine import get_db
        from models.memory import MemoryBase as _MemoryBase
        from models.memory import MemoryRecord as _MemoryRecord

        domains: list[str] = []
        topics: list[str] = []
        domain_topics: dict[str, list[str]] = {}
        with get_db() as session:
            domain_rows = (
                session.query(_MemoryBase.domain)
                .filter(_MemoryBase.user_id == self.user_id, _MemoryBase.deleted == 0)
                .distinct()
                .all()
            )
            domains = [r.domain for r in domain_rows if r.domain]

            import datetime as _dt

            topic_rows = (
                session.query(
                    _MemoryRecord.domain,
                    _MemoryRecord.topic,
                    func.count().label("memory_count"),
                    func.max(_MemoryRecord.updated_at).label("updated_at"),
                )
                .join(_MemoryRecord.memory_base)
                .filter(
                    _MemoryBase.user_id == self.user_id,
                    _MemoryRecord.deleted == 0,
                    _MemoryRecord.topic.isnot(None),
                    _MemoryRecord.topic != "",
                )
                .group_by(_MemoryRecord.domain, _MemoryRecord.topic)
                .all()
            )
            now = _dt.datetime.now(_dt.UTC).replace(tzinfo=None)
            domain_bucket: dict[str, list[tuple[float, str]]] = {}
            for row in topic_rows:
                if not row.topic:
                    continue
                dom = row.domain or "_default"
                days_old = max(0.0, (now - row.updated_at).total_seconds() / 86400) if row.updated_at else 0.0
                weight = (row.memory_count or 1) / (1 + days_old / 30)
                domain_bucket.setdefault(dom, []).append((weight, row.topic))
            domain_topics = {
                dom: [name for _, name in sorted(items, reverse=True)[:3]]
                for dom, items in domain_bucket.items()
                if items
            }
            topics = [name for names in domain_topics.values() for name in names]

        if domains or topics:
            return {"domains": domains, "topics": topics, "domain_topics": domain_topics}, domains, topics
        return None, domains, topics

    @staticmethod
    def _judge_content(result: MemoryRetrieveResult) -> str:
        if result.metadata.get("source") == "graph_expansion":
            return result.content
        lines = [
            line.strip()
            for line in result.content.splitlines()
            if line.strip() and not line.startswith("【") and "UTC" not in line
        ]
        return " ".join(lines)[:500]

    @staticmethod
    def _normalize_react_query(query: str) -> str:
        return " ".join((query or "").strip().lower().split())

    @staticmethod
    def _default_weights_for_method(retrieval_method: str) -> dict[str, float]:
        if retrieval_method == "full_text":
            return {"keyword_weight": 0.75, "vector_weight": 0.25}
        if retrieval_method == "vector":
            return {"keyword_weight": 0.05, "vector_weight": 0.95}
        return {"keyword_weight": 0.2, "vector_weight": 0.8}

    @staticmethod
    def _looks_like_exact_match_query(query: str) -> bool:
        query = (query or "").strip()
        if not query:
            return False
        exact_markers = ['"', "'", "/", ":", "#", "@", "."]
        if any(marker in query for marker in exact_markers):
            return True
        return sum(ch.isdigit() for ch in query) >= 2

    @classmethod
    def _clamp_score_threshold(cls, score_threshold: float | int | None) -> float:
        if score_threshold is None:
            return 0.0
        try:
            value = float(score_threshold)
        except (TypeError, ValueError):
            return 0.0
        return round(max(0.0, min(0.95, value)), 4)

    @classmethod
    def _resolve_react_score_threshold(
        cls,
        *,
        requested_score_threshold: float | int | None,
        retrieve_score_threshold: float | int | None,
        method: str,
        feedback: dict[str, object],
        min_new_candidates: int,
        top_k: int,
    ) -> tuple[float, str]:
        last_action = feedback.get("last_action") if isinstance(feedback, dict) else None
        threshold = cls._clamp_score_threshold(requested_score_threshold)
        threshold_reason = "planner_requested" if requested_score_threshold is not None else "request_default"
        if requested_score_threshold is None:
            threshold = cls._clamp_score_threshold(retrieve_score_threshold)
            if isinstance(last_action, dict):
                last_method = str(last_action.get("retrieval_method") or "").strip().lower()
                last_threshold = last_action.get("score_threshold")
                if (
                    str(last_action.get("action") or "") == "search"
                    and last_method == method
                    and last_threshold is not None
                ):
                    threshold = cls._clamp_score_threshold(last_threshold)
                    threshold_reason = "carried_forward"

        if not isinstance(last_action, dict):
            return threshold, threshold_reason

        last_method = str(last_action.get("retrieval_method") or "").strip().lower()
        last_action_type = str(last_action.get("action") or "")
        if last_action_type != "search" or last_method != method:
            return threshold, threshold_reason

        last_new_count = int(last_action.get("new_candidate_count") or 0)
        candidate_count = int(feedback.get("candidate_count") or 0)
        top_score = float(feedback.get("top_score") or 0.0)
        score_spread = float(feedback.get("score_spread") or 0.0)
        topic_diversity = int(feedback.get("topic_diversity") or 0)
        supported_top_k_count = int(feedback.get("supported_top_k_count") or 0)

        if last_new_count < min_new_candidates and candidate_count < max(top_k, 1):
            relax_step = 0.05 if method == "full_text" else 0.08
            relaxed = cls._clamp_score_threshold(threshold - relax_step)
            if relaxed < threshold:
                return relaxed, "auto_relaxed_low_yield"

        dense_candidates = candidate_count >= max(top_k, 1) and score_spread < 0.06 and top_score < 0.9
        if dense_candidates and (
            supported_top_k_count < min(max(top_k, 1), candidate_count) or topic_diversity > max(top_k, 1)
        ):
            tighten_step = 0.08 if method == "full_text" else 0.06
            tightened = cls._clamp_score_threshold(threshold + tighten_step)
            if tightened > threshold:
                return tightened, "auto_tightened_dense_candidates"

        crowded_low_confidence = candidate_count >= max(top_k * 2, top_k + 2) and top_score < 0.75
        if crowded_low_confidence:
            tightened = cls._clamp_score_threshold(threshold + 0.05)
            if tightened > threshold:
                return tightened, "auto_tightened_low_confidence_noise"

        return threshold, threshold_reason

    @classmethod
    def _adapt_weights_for_feedback(
        cls,
        *,
        method: str,
        weights: dict[str, float],
        feedback: dict[str, object],
        strategy_reason: str,
        min_new_candidates: int,
    ) -> tuple[dict[str, float], str]:
        last_action = feedback.get("last_action") if isinstance(feedback, dict) else None
        topic_diversity = int(feedback.get("topic_diversity") or 0) if isinstance(feedback, dict) else 0
        score_spread = float(feedback.get("score_spread") or 0.0) if isinstance(feedback, dict) else 0.0
        if not isinstance(last_action, dict):
            return weights, strategy_reason

        last_new_count = int(last_action.get("new_candidate_count") or 0)
        last_action_type = str(last_action.get("action") or "")
        if last_action_type != "search":
            return weights, strategy_reason

        if method == "semantics" and last_new_count < min_new_candidates and topic_diversity <= 1:
            return {"keyword_weight": 0.35, "vector_weight": 0.65}, strategy_reason or "semantic_bias_to_keyword"

        if method == "full_text" and last_new_count < min_new_candidates:
            return {"keyword_weight": 0.6, "vector_weight": 0.4}, strategy_reason or "full_text_broadened_with_vector"

        if method == "semantics" and score_spread < 0.08:
            return {"keyword_weight": 0.3, "vector_weight": 0.7}, strategy_reason or "semantic_tighten_disambiguation"

        return weights, strategy_reason

    @classmethod
    def _resolve_react_search_strategy(
        cls,
        *,
        query: str,
        requested_method: str,
        requested_weights: dict[str, float],
        feedback: dict[str, object],
        min_new_candidates: int,
    ) -> tuple[str, dict[str, float], str]:
        method = (requested_method or "").strip().lower()
        strategy_reason = "planner_requested"
        if not method:
            method = "full_text" if cls._looks_like_exact_match_query(query) else "semantics"
            strategy_reason = "default_inferred"
        if method not in {"semantics", "full_text", "vector"}:
            method = "semantics"
            strategy_reason = "normalized_invalid_method"

        normalized_query = cls._normalize_react_query(query)
        switched_method = False
        last_action = feedback.get("last_action") if isinstance(feedback, dict) else None
        if isinstance(last_action, dict):
            last_method = str(last_action.get("retrieval_method") or "").strip().lower()
            last_new_count = int(last_action.get("new_candidate_count") or 0)
            last_action_type = str(last_action.get("action") or "")
            last_normalized_query = cls._normalize_react_query(str(last_action.get("normalized_query") or ""))
            topic_diversity = int(feedback.get("topic_diversity") or 0) if isinstance(feedback, dict) else 0
            if (
                last_action_type == "search"
                and last_method
                and last_method == method
                and last_new_count < min_new_candidates
                and topic_diversity <= 1
                and normalized_query
                and normalized_query == last_normalized_query
            ):
                if method == "semantics":
                    method = "full_text"
                    strategy_reason = "auto_switch_low_yield_to_full_text"
                    switched_method = True
                elif method == "full_text":
                    method = "semantics"
                    strategy_reason = "auto_switch_low_yield_to_semantics"
                    switched_method = True

        weights = dict(requested_weights or {})
        if switched_method or not weights:
            weights = cls._default_weights_for_method(method)
        if not switched_method:
            weights, strategy_reason = cls._adapt_weights_for_feedback(
                method=method,
                weights=weights,
                feedback=feedback,
                strategy_reason=strategy_reason,
                min_new_candidates=min_new_candidates,
            )
        return method, weights, strategy_reason

    @staticmethod
    def _sigmoid_rank_score(rank: int, total: int) -> float:
        import math

        denom = max(total, 1)
        return 1.0 / (1.0 + math.exp(6.0 * (rank / denom - 0.5)))

    @staticmethod
    def _build_react_candidate_summary(
        candidate_map: dict[str, MemoryRetrieveResult],
        evidence_counts: dict[str, int],
        retrieval_sources: dict[str, set[str]],
        limit: int = 8,
    ) -> list[dict[str, object]]:
        ranked = sorted(candidate_map.values(), key=lambda x: x.score or 0.0, reverse=True)[:limit]
        return [
            {
                "id": result.memory_id,
                "topic": result.metadata.get("topic", ""),
                "domain": result.metadata.get("domain", ""),
                "type": result.metadata.get("type", ""),
                "score": round(float(result.score or 0.0), 4),
                "evidence_count": evidence_counts.get(result.memory_id, 1),
                "retrieval_sources": sorted(retrieval_sources.get(result.memory_id, set())),
            }
            for result in ranked
        ]

    @classmethod
    def _build_react_feedback_summary(
        cls,
        candidate_map: dict[str, MemoryRetrieveResult],
        action_history: list[dict[str, object]],
        evidence_counts: dict[str, int] | None = None,
        retrieval_sources: dict[str, set[str]] | None = None,
        top_k: int = 0,
    ) -> dict[str, object]:
        evidence_counts = evidence_counts or {}
        retrieval_sources = retrieval_sources or {}
        sorted_candidates = sorted(candidate_map.values(), key=lambda x: x.score or 0.0, reverse=True)
        scores = [float(result.score or 0.0) for result in sorted_candidates]
        topics: list[str] = []
        total_evidence = 0
        supported_candidate_count = 0
        target_top_k = min(max(top_k, 0), len(sorted_candidates)) if top_k else min(len(sorted_candidates), 3)
        supported_top_k_count = 0
        for index, result in enumerate(sorted_candidates):
            topic = str(result.metadata.get("topic") or "").strip()
            if topic:
                topics.append(topic)
            evidence = int(evidence_counts.get(result.memory_id, 1))
            total_evidence += evidence
            if cls._is_react_candidate_supported(result.memory_id, evidence_counts, retrieval_sources):
                supported_candidate_count += 1
                if index < target_top_k:
                    supported_top_k_count += 1
        unique_topics = list(dict.fromkeys(topics))
        return {
            "last_action": action_history[-1] if action_history else None,
            "top_score": scores[0] if scores else 0.0,
            "score_spread": (scores[0] - scores[min(len(scores) - 1, 2)])
            if len(scores) >= 3
            else (scores[0] if scores else 0.0),
            "candidate_count": len(candidate_map),
            "topic_diversity": len(set(unique_topics)),
            "top_topics": unique_topics[:5],
            "avg_evidence": (total_evidence / len(sorted_candidates)) if sorted_candidates else 0.0,
            "supported_candidate_count": supported_candidate_count,
            "supported_top_k_count": supported_top_k_count,
        }

    @staticmethod
    def _is_react_candidate_supported(
        memory_id: str,
        evidence_counts: dict[str, int],
        retrieval_sources: dict[str, set[str]],
    ) -> bool:
        return evidence_counts.get(memory_id, 1) >= 2 or len(retrieval_sources.get(memory_id, set())) >= 2

    @classmethod
    def _judge_candidate_priority(
        cls,
        result: MemoryRetrieveResult,
        evidence_counts: dict[str, int],
        retrieval_sources: dict[str, set[str]],
    ) -> float:
        memory_id = result.memory_id
        rag_score = float(result.score or 0.0)
        evidence_score = min(1.0, float(evidence_counts.get(memory_id, 1)) / 3.0)
        source_score = min(1.0, float(len(retrieval_sources.get(memory_id, set()))) / 2.0)
        access_score = min(1.0, float(result.metadata.get("access_count", 0) or 0) / 10.0)
        return 0.72 * rag_score + 0.18 * evidence_score + 0.07 * source_score + 0.03 * access_score

    @classmethod
    def _expand_seed_priority(
        cls,
        result: MemoryRetrieveResult,
        evidence_counts: dict[str, int],
        retrieval_sources: dict[str, set[str]],
    ) -> float:
        memory_id = result.memory_id
        score = float(result.score or 0.0)
        supported_bonus = (
            0.45 if cls._is_react_candidate_supported(memory_id, evidence_counts, retrieval_sources) else 0.0
        )
        evidence_score = min(1.0, float(evidence_counts.get(memory_id, 1)) / 3.0)
        source_score = min(1.0, float(len(retrieval_sources.get(memory_id, set()))) / 2.0)
        return supported_bonus + 0.45 * score + 0.07 * evidence_score + 0.03 * source_score

    @classmethod
    def _select_expand_seed_ids(
        cls,
        candidate_map: dict[str, MemoryRetrieveResult],
        evidence_counts: dict[str, int],
        retrieval_sources: dict[str, set[str]],
        requested_seed_ids: list[str],
        max_seed_count: int,
        stop_score: float,
    ) -> list[str]:
        requested_candidates = [candidate_map[mid] for mid in requested_seed_ids if mid in candidate_map]
        if not requested_candidates:
            return []

        top_score = max(float(result.score or 0.0) for result in candidate_map.values()) if candidate_map else 0.0
        high_conf_seed_floor = max(0.78, stop_score * 0.9)
        supported_seed_floor = max(0.55, high_conf_seed_floor - 0.2)

        eligible_candidates: list[MemoryRetrieveResult] = []
        for result in requested_candidates:
            score = float(result.score or 0.0)
            is_supported = cls._is_react_candidate_supported(result.memory_id, evidence_counts, retrieval_sources)
            if is_supported and score >= supported_seed_floor:
                eligible_candidates.append(result)
                continue
            if score >= high_conf_seed_floor and score >= max(0.0, top_score - 0.08):
                eligible_candidates.append(result)

        ranked = sorted(
            eligible_candidates,
            key=lambda x: cls._expand_seed_priority(x, evidence_counts, retrieval_sources),
            reverse=True,
        )
        return [result.memory_id for result in ranked[:max_seed_count]]

    @classmethod
    def _build_candidates_for_judge(
        cls,
        candidate_map: dict[str, MemoryRetrieveResult],
        evidence_counts: dict[str, int],
        retrieval_sources: dict[str, set[str]],
        judge_pool_size: int,
    ) -> list[dict[str, object]]:
        sorted_candidates = sorted(
            candidate_map.values(),
            key=lambda x: cls._judge_candidate_priority(x, evidence_counts, retrieval_sources),
            reverse=True,
        )[:judge_pool_size]
        return [
            {
                "id": result.memory_id,
                "topic": result.metadata.get("topic", ""),
                "content": cls._judge_content(result),
                "domain": result.metadata.get("domain", ""),
                "type": result.metadata.get("type", ""),
                "tags": (result.metadata.get("tags") or [])[:5],
                "access_count": result.metadata.get("access_count", 0),
                "evidence_count": evidence_counts.get(result.memory_id, 1),
                "retrieval_sources": sorted(retrieval_sources.get(result.memory_id, set())),
                "judge_priority": round(cls._judge_candidate_priority(result, evidence_counts, retrieval_sources), 4),
            }
            for result in sorted_candidates
        ]

    @classmethod
    def _merge_react_candidates(
        cls,
        candidate_map: dict[str, MemoryRetrieveResult],
        hit_counts: dict[str, int],
        evidence_counts: dict[str, int],
        retrieval_sources: dict[str, set[str]],
        results: list[MemoryRetrieveResult],
        retrieval_source: str,
    ) -> dict[str, int]:
        merge_stats = {
            "new_count": 0,
            "reinforced_count": 0,
            "support_gain_count": 0,
        }
        touched: set[str] = set()
        reinforced: set[str] = set()
        support_gains: set[str] = set()
        for result in results:
            memory_id = result.memory_id
            if not memory_id:
                continue
            was_supported = cls._is_react_candidate_supported(memory_id, evidence_counts, retrieval_sources)
            existing = candidate_map.get(memory_id)
            if existing is None:
                merge_stats["new_count"] += 1
                candidate_map[memory_id] = result
            else:
                if memory_id not in reinforced:
                    merge_stats["reinforced_count"] += 1
                    reinforced.add(memory_id)
                merged_metadata = {**existing.metadata, **result.metadata}
                if (result.score or 0.0) >= (existing.score or 0.0):
                    candidate_map[memory_id] = result.model_copy(update={"metadata": merged_metadata})
                else:
                    candidate_map[memory_id] = existing.model_copy(update={"metadata": merged_metadata})

            hit_counts[memory_id] = hit_counts.get(memory_id, 0) + 1
            if memory_id not in touched:
                evidence_counts[memory_id] = evidence_counts.get(memory_id, 0) + 1
                touched.add(memory_id)
            retrieval_sources.setdefault(memory_id, set()).add(retrieval_source)
            is_supported = cls._is_react_candidate_supported(memory_id, evidence_counts, retrieval_sources)
            if not was_supported and is_supported and memory_id not in support_gains:
                merge_stats["support_gain_count"] += 1
                support_gains.add(memory_id)
        return merge_stats

    @staticmethod
    def _has_material_react_gain(
        *,
        new_candidate_count: int,
        reinforced_candidate_count: int,
        support_gain_count: int,
        min_new_candidates: int,
    ) -> bool:
        if new_candidate_count >= min_new_candidates:
            return True
        if support_gain_count > 0:
            return True
        return reinforced_candidate_count >= max(1, min_new_candidates)

    @staticmethod
    def _normalize_react_score_weights(weights: dict[str, float]) -> dict[str, float]:
        cleaned = {key: max(0.0, float(value)) for key, value in weights.items()}
        total = sum(cleaned.values()) or 1.0
        return {key: round(value / total, 4) for key, value in cleaned.items()}

    @classmethod
    def _react_evidence_score(
        cls,
        memory_id: str,
        evidence_counts: dict[str, int],
        retrieval_sources: dict[str, set[str]],
        react_step_count: int,
    ) -> float:
        step_denom = max(react_step_count, 1)
        evidence_score = float(evidence_counts.get(memory_id, 1)) / step_denom
        source_bonus = min(0.2, max(0, len(retrieval_sources.get(memory_id, set())) - 1) * 0.1)
        return min(1.0, evidence_score + source_bonus)

    @classmethod
    def _resolve_react_final_score_weights(
        cls,
        *,
        candidate_map: dict[str, MemoryRetrieveResult],
        evidence_counts: dict[str, int],
        retrieval_sources: dict[str, set[str]],
        selected_ids: list[str],
        judge_input_count: int,
        react_step_count: int,
        top_k: int,
    ) -> tuple[dict[str, float], str]:
        candidate_count = max(len(candidate_map), 1)
        avg_evidence = sum(evidence_counts.get(memory_id, 1) for memory_id in candidate_map) / candidate_count
        supported_count = sum(
            1
            for memory_id in candidate_map
            if cls._is_react_candidate_supported(memory_id, evidence_counts, retrieval_sources)
        )
        supported_ratio = supported_count / candidate_count
        selection_rate = len(selected_ids) / max(judge_input_count, 1)
        top_score = max((float(candidate.score or 0.0) for candidate in candidate_map.values()), default=0.0)

        weights = {"rag": 0.35, "evidence": 0.25, "rank": 0.40}
        reasons: list[str] = ["balanced_default"]

        if avg_evidence >= 1.5 or supported_ratio >= 0.5:
            weights["rag"] -= 0.08
            weights["evidence"] += 0.22
            weights["rank"] -= 0.14
            reasons.append("evidence_dense")

        if selection_rate <= 0.5 and candidate_count >= max(top_k * 2, 4):
            weights["rag"] -= 0.06
            weights["evidence"] -= 0.06
            weights["rank"] += 0.12
            reasons.append("judge_rank_noise_control")

        if top_score >= 0.9 and selection_rate >= 0.75 and supported_ratio < 0.4:
            weights["rag"] += 0.08
            weights["evidence"] -= 0.03
            weights["rank"] -= 0.05
            reasons.append("rag_confident")

        if react_step_count >= 3 and supported_ratio >= 0.6:
            weights["evidence"] += 0.06
            weights["rag"] -= 0.03
            weights["rank"] -= 0.03
            reasons.append("multi_step_consensus")

        return cls._normalize_react_score_weights(weights), "+".join(reasons)

    @classmethod
    def _resolve_react_fill_score_weights(cls, score_weights: dict[str, float]) -> dict[str, float]:
        fill_weights = {
            "rag": float(score_weights.get("rag", 0.35)) + float(score_weights.get("rank", 0.4)) * 0.6,
            "evidence": float(score_weights.get("evidence", 0.25)) + float(score_weights.get("rank", 0.4)) * 0.4,
        }
        return cls._normalize_react_score_weights(fill_weights)

    @classmethod
    def _score_react_selected_candidate(
        cls,
        *,
        candidate: MemoryRetrieveResult,
        rank: int,
        total_selected: int,
        evidence_counts: dict[str, int],
        retrieval_sources: dict[str, set[str]],
        react_step_count: int,
        score_weights: dict[str, float],
    ) -> float:
        rag_score = float(candidate.score or 0.0)
        evidence_score = cls._react_evidence_score(
            candidate.memory_id,
            evidence_counts,
            retrieval_sources,
            react_step_count,
        )
        rank_score = cls._sigmoid_rank_score(rank, total_selected)
        final_score = (
            float(score_weights.get("rag", 0.0)) * rag_score
            + float(score_weights.get("evidence", 0.0)) * evidence_score
            + float(score_weights.get("rank", 0.0)) * rank_score
        )
        return round(final_score, 6)

    @classmethod
    def _score_react_fill_candidate(
        cls,
        *,
        candidate: MemoryRetrieveResult,
        evidence_counts: dict[str, int],
        retrieval_sources: dict[str, set[str]],
        react_step_count: int,
        fill_weights: dict[str, float],
    ) -> float:
        rag_score = float(candidate.score or 0.0)
        evidence_score = cls._react_evidence_score(
            candidate.memory_id,
            evidence_counts,
            retrieval_sources,
            react_step_count,
        )
        fill_score = float(fill_weights.get("rag", 0.0)) * rag_score + float(
            fill_weights.get("evidence", 0.0)
        ) * evidence_score
        return round(fill_score, 6)

    async def _retrieve_llm_react(self, retrieve: MemoryRetrieve) -> list[MemoryRetrieveResult]:
        """LLM 主动式检索：受限 ReAct loop（plan → act → observe → judge）。"""
        import asyncio
        import time
        from collections import Counter

        from configs import config
        from runtime.memory.trace import ReActStepTrace, ResultDetail, RetrievalTrace

        t_total = time.monotonic()
        trace = RetrievalTrace(
            user_id=self.user_id,
            agent_id=retrieve.agent_id or None,
            project_id=retrieve.project_id or None,
            retrieve_type="llm",
            top_k=retrieve.top_k,
            query_hash=RetrievalTrace.hash_query(retrieve.query),
            react_enabled=bool(config.MEMORY_RETRIEVE_REACT_ENABLED),
        )

        t0 = time.monotonic()
        memory_structure: dict | None = None
        domains: list[str] = []
        topics: list[str] = []
        try:
            memory_structure, domains, topics = await self._load_memory_structure()
        except Exception:
            logger.warning("Failed to load memory structure for ReAct retrieval", exc_info=True)
        trace.ms_domain_count = len(domains)
        trace.ms_topic_count = len(topics)
        trace.latency_step0_ms = int((time.monotonic() - t0) * 1000)

        candidate_map: dict[str, MemoryRetrieveResult] = {}
        hit_counts: dict[str, int] = {}
        evidence_counts: dict[str, int] = {}
        retrieval_sources: dict[str, set[str]] = {}
        action_history: list[dict[str, object]] = []
        seen_search_signatures: set[tuple[str, str]] = set()
        raw_total = 0
        stop_reason = ""

        max_steps = config.MEMORY_RETRIEVE_REACT_MAX_STEPS
        max_search_actions = config.MEMORY_RETRIEVE_REACT_MAX_SEARCH_ACTIONS
        max_expand_actions = config.MEMORY_RETRIEVE_REACT_MAX_EXPAND_ACTIONS
        candidate_pool_multiplier = config.MEMORY_RETRIEVE_REACT_CANDIDATE_POOL_MULTIPLIER
        judge_pool_multiplier = config.MEMORY_RETRIEVE_REACT_JUDGE_POOL_MULTIPLIER
        stop_score = config.MEMORY_RETRIEVE_REACT_STOP_SCORE
        min_new_candidates = config.MEMORY_RETRIEVE_REACT_MIN_NEW_CANDIDATES

        search_actions = 0
        expand_actions = 0
        search_budget_bonus = 0
        expand_budget_bonus = 0
        planner_elapsed_ms = 0
        retrieval_elapsed_ms = 0

        for step_idx in range(max_steps):
            step_started = time.monotonic()
            input_candidate_count = len(candidate_map)
            remaining_search_actions = max(0, max_search_actions + search_budget_bonus - search_actions)
            remaining_expand_actions = max(0, max_expand_actions + expand_budget_bonus - expand_actions)
            planner_state = {
                "memory_structure": memory_structure or {},
                "actions_taken": action_history[-4:],
                "current_candidates": self._build_react_candidate_summary(
                    candidate_map, evidence_counts, retrieval_sources
                ),
                "retrieval_feedback": self._build_react_feedback_summary(
                    candidate_map,
                    action_history,
                    evidence_counts,
                    retrieval_sources,
                    retrieve.top_k,
                ),
                "remaining_steps": max_steps - step_idx,
                "remaining_search_actions": remaining_search_actions,
                "remaining_expand_actions": remaining_expand_actions,
                "top_k": retrieve.top_k,
            }

            planner_started = time.monotonic()
            action = await asyncio.to_thread(LLMGenerator.plan_memory_react_action, retrieve.query, planner_state)
            planner_elapsed_ms += int((time.monotonic() - planner_started) * 1000)
            if step_idx == 0 and action.get("action") == "stop":
                action = {
                    "action": "search",
                    "query": retrieve.query,
                    "filters": dict(retrieve.filters or {}),
                    "retrieval_method": "",
                    "weights": {},
                    "score_threshold": None,
                    "memory_ids": [],
                    "reason_summary": "bootstrap_seed_search",
                }

            action_type = str(action.get("action") or "stop")
            query = str(action.get("query") or "").strip()
            normalized_query = ""
            filters = dict(action.get("filters") or {})
            retrieval_method = str(action.get("retrieval_method") or "").strip().lower()
            weights = dict(action.get("weights") or {})
            action_score_threshold = action.get("score_threshold")
            threshold_reason = ""
            query_hash = RetrievalTrace.hash_query(query) if query else ""
            new_candidate_count = 0
            reinforced_candidate_count = 0
            support_gain_count = 0
            step_graph_prefetch_count = 0
            step_graph_boost_count = 0
            step_graph_expansion_count = 0
            step_stop_reason = ""
            strategy_reason = ""

            if action_type == "search":
                if search_actions >= max_search_actions + search_budget_bonus:
                    action_type = "stop"
                    step_stop_reason = "search_budget_exhausted"
                else:
                    normalized_query = self._normalize_react_query(query or retrieve.query)
                    feedback = self._build_react_feedback_summary(
                        candidate_map,
                        action_history,
                        evidence_counts,
                        retrieval_sources,
                        retrieve.top_k,
                    )
                    retrieval_method, weights, strategy_reason = self._resolve_react_search_strategy(
                        query=query or retrieve.query,
                        requested_method=retrieval_method,
                        requested_weights=weights,
                        feedback=feedback,
                        min_new_candidates=min_new_candidates,
                    )
                    action_score_threshold, threshold_reason = self._resolve_react_score_threshold(
                        requested_score_threshold=action_score_threshold,
                        retrieve_score_threshold=retrieve.score_threshold,
                        method=retrieval_method,
                        feedback=feedback,
                        min_new_candidates=min_new_candidates,
                        top_k=retrieve.top_k,
                    )
                    search_signature = (normalized_query, retrieval_method)
                    if search_signature in seen_search_signatures:
                        trace.react_repeated_action_count += 1
                        action_type = "stop"
                        step_stop_reason = "repeated_search_signature"
                    else:
                        seen_search_signatures.add(search_signature)
                        search_actions += 1
                        trace.react_unique_action_query_count = len(seen_search_signatures)
                        merged_filters = {**dict(retrieve.filters or {}), **filters}
                        merged_filters["retrieval_method"] = retrieval_method
                        merged_filters["weights"] = weights
                        merged_filters["score_threshold"] = float(action_score_threshold)
                        search_retrieve = retrieve.model_copy(
                            update={
                                "query": query or retrieve.query,
                                "top_k": max(retrieve.top_k * candidate_pool_multiplier, retrieve.top_k),
                                "filters": merged_filters,
                                "score_threshold": float(action_score_threshold),
                            }
                        )
                        retrieval_started = time.monotonic()
                        results, stats = await self._retrieve_rag_with_graph(search_retrieve, prefetch_threshold=0.5)
                        retrieval_elapsed_ms += int((time.monotonic() - retrieval_started) * 1000)
                        raw_total += len(results)
                        step_graph_prefetch_count = stats.get("graph_prefetch_count", 0)
                        step_graph_boost_count = stats.get("graph_boost_count", 0)
                        step_graph_expansion_count = stats.get("graph_expansion_count", 0)
                        merge_stats = self._merge_react_candidates(
                            candidate_map,
                            hit_counts,
                            evidence_counts,
                            retrieval_sources,
                            results,
                            "react_search",
                        )
                        new_candidate_count = merge_stats["new_count"]
                        reinforced_candidate_count = merge_stats["reinforced_count"]
                        support_gain_count = merge_stats["support_gain_count"]
                        if self._has_material_react_gain(
                            new_candidate_count=new_candidate_count,
                            reinforced_candidate_count=reinforced_candidate_count,
                            support_gain_count=support_gain_count,
                            min_new_candidates=min_new_candidates,
                        ):
                            search_budget_bonus = min(search_budget_bonus + 1, max_steps)
            elif action_type == "expand":
                if expand_actions >= max_expand_actions + expand_budget_bonus:
                    action_type = "stop"
                    step_stop_reason = "expand_budget_exhausted"
                else:
                    requested_seed_ids = [mid for mid in action.get("memory_ids", []) if mid in candidate_map]
                    seed_ids = self._select_expand_seed_ids(
                        candidate_map,
                        evidence_counts,
                        retrieval_sources,
                        requested_seed_ids=requested_seed_ids,
                        max_seed_count=retrieve.top_k,
                        stop_score=stop_score,
                    )
                    if not requested_seed_ids:
                        trace.react_repeated_action_count += 1
                        action_type = "stop"
                        step_stop_reason = "no_valid_expand_seeds"
                    elif not seed_ids:
                        trace.react_repeated_action_count += 1
                        step_stop_reason = "weak_expand_seeds"
                    else:
                        expand_actions += 1
                        expand_retrieve = retrieve.model_copy(
                            update={"top_k": max(retrieve.top_k * candidate_pool_multiplier, retrieve.top_k)}
                        )
                        base_scores = {mid: candidate_map[mid].score or 0.0 for mid in seed_ids}
                        retrieval_started = time.monotonic()
                        results = await self._graph_expand_neighbors(
                            memory_ids=seed_ids,
                            existing_ids=set(candidate_map.keys()),
                            retrieve=expand_retrieve,
                            base_scores=base_scores,
                        )
                        retrieval_elapsed_ms += int((time.monotonic() - retrieval_started) * 1000)
                        raw_total += len(results)
                        step_graph_expansion_count = len(results)
                        merge_stats = self._merge_react_candidates(
                            candidate_map,
                            hit_counts,
                            evidence_counts,
                            retrieval_sources,
                            results,
                            "react_expand",
                        )
                        new_candidate_count = merge_stats["new_count"]
                        reinforced_candidate_count = merge_stats["reinforced_count"]
                        support_gain_count = merge_stats["support_gain_count"]
                        if self._has_material_react_gain(
                            new_candidate_count=new_candidate_count,
                            reinforced_candidate_count=reinforced_candidate_count,
                            support_gain_count=support_gain_count,
                            min_new_candidates=min_new_candidates,
                        ):
                            expand_budget_bonus = min(expand_budget_bonus + 1, max_steps)
            else:
                step_stop_reason = "planner_stop"

            trace.react_steps.append(
                ReActStepTrace(
                    step_index=step_idx,
                    action_type=action_type,
                    query_hash=query_hash,
                    retrieval_method=retrieval_method,
                    score_threshold=float(action_score_threshold) if action_score_threshold is not None else None,
                    input_candidate_count=input_candidate_count,
                    output_candidate_count=len(candidate_map),
                    new_candidate_count=new_candidate_count,
                    graph_prefetch_count=step_graph_prefetch_count,
                    graph_boost_count=step_graph_boost_count,
                    graph_expansion_count=step_graph_expansion_count,
                    latency_ms=int((time.monotonic() - step_started) * 1000),
                    strategy_reason=strategy_reason,
                    threshold_reason=threshold_reason,
                    stop_reason=step_stop_reason,
                    reason_summary=str(action.get("reason_summary") or ""),
                )
            )
            trace.react_total_new_candidates += new_candidate_count
            action_history.append(
                {
                    "action": action_type,
                    "normalized_query": normalized_query,
                    "query_hash": query_hash,
                    "new_candidate_count": new_candidate_count,
                    "reinforced_candidate_count": reinforced_candidate_count,
                    "support_gain_count": support_gain_count,
                    "search_budget_bonus": search_budget_bonus,
                    "expand_budget_bonus": expand_budget_bonus,
                    "score_threshold": action_score_threshold,
                    "threshold_reason": threshold_reason,
                    "retrieval_method": retrieval_method,
                    "strategy_reason": strategy_reason,
                    "stop_reason": step_stop_reason,
                }
            )

            if action_type == "stop":
                stop_reason = step_stop_reason or "planner_stop"
                break

            if len(candidate_map) >= retrieve.top_k and not self._has_material_react_gain(
                new_candidate_count=new_candidate_count,
                reinforced_candidate_count=reinforced_candidate_count,
                support_gain_count=support_gain_count,
                min_new_candidates=min_new_candidates,
            ):
                stop_reason = "low_yield"
                break
            if len(candidate_map) >= retrieve.top_k:
                top_score = max(result.score or 0.0 for result in candidate_map.values())
                if top_score >= stop_score:
                    stop_reason = "high_confidence"
                    break
        else:
            stop_reason = "max_steps"

        trace.react_step_count = len(trace.react_steps)
        trace.react_stop_reason = stop_reason
        trace.candidate_total_raw = raw_total
        trace.candidate_total_unique = len(candidate_map)
        trace.latency_step1_ms = planner_elapsed_ms
        trace.latency_step2_ms = retrieval_elapsed_ms

        if not candidate_map:
            fallback_retrieve = retrieve.model_copy(
                update={
                    "query": retrieve.query,
                    "top_k": max(retrieve.top_k * candidate_pool_multiplier, retrieve.top_k),
                    "score_threshold": 0.0,
                }
            )
            results, _stats = await self._retrieve_rag_with_graph(fallback_retrieve, prefetch_threshold=0.5)
            raw_total += len(results)
            self._merge_react_candidates(
                candidate_map,
                hit_counts,
                evidence_counts,
                retrieval_sources,
                results,
                "fallback_search",
            )
            trace.candidate_total_raw = raw_total
            trace.candidate_total_unique = len(candidate_map)

        if not candidate_map:
            trace.latency_total_ms = int((time.monotonic() - t_total) * 1000)
            self._emit_trace(trace)
            return []

        judge_started = time.monotonic()
        candidates_for_judge = self._build_candidates_for_judge(
            candidate_map,
            evidence_counts,
            retrieval_sources,
            judge_pool_size=retrieve.top_k * judge_pool_multiplier,
        )
        trace.judge_input_count = len(candidates_for_judge)
        selected_ids = [candidate["id"] for candidate in candidates_for_judge]
        try:
            selected_ids = await asyncio.to_thread(
                LLMGenerator.judge_memory_relevance, retrieve.query, candidates_for_judge
            )
        except Exception:
            logger.warning("ReAct final judge failed, falling back to score ranking", exc_info=True)
            trace.judge_failed = True
        trace.judge_output_count = len(selected_ids)
        trace.judge_selection_rate = trace.judge_output_count / max(trace.judge_input_count, 1)
        score_weights, weight_reason = self._resolve_react_final_score_weights(
            candidate_map=candidate_map,
            evidence_counts=evidence_counts,
            retrieval_sources=retrieval_sources,
            selected_ids=selected_ids,
            judge_input_count=trace.judge_input_count,
            react_step_count=trace.react_step_count,
            top_k=retrieve.top_k,
        )
        trace.judge_score_weights = score_weights
        trace.judge_weight_reason = weight_reason
        trace.latency_step3_ms = int((time.monotonic() - judge_started) * 1000)

        output: list[MemoryRetrieveResult] = []
        output_ids: set[str] = set()
        total_selected = max(len(selected_ids), 1)
        scored_selected: list[tuple[float, MemoryRetrieveResult]] = []
        for rank, memory_id in enumerate(selected_ids):
            candidate = candidate_map.get(memory_id)
            if candidate is None or memory_id in output_ids:
                continue
            final_score = self._score_react_selected_candidate(
                candidate=candidate,
                rank=rank,
                total_selected=total_selected,
                evidence_counts=evidence_counts,
                retrieval_sources=retrieval_sources,
                react_step_count=trace.react_step_count,
                score_weights=score_weights,
            )
            scored_selected.append((final_score, candidate))
        for final_score, candidate in sorted(scored_selected, key=lambda item: item[0], reverse=True):
            if candidate.memory_id in output_ids:
                continue
            output.append(candidate.model_copy(update={"score": final_score}))
            output_ids.add(candidate.memory_id)
            if len(output) >= retrieve.top_k:
                break

        if len(output) < retrieve.top_k:
            fill_weights = self._resolve_react_fill_score_weights(score_weights)
            for candidate in sorted(
                candidate_map.values(),
                key=lambda x: self._score_react_fill_candidate(
                    candidate=x,
                    evidence_counts=evidence_counts,
                    retrieval_sources=retrieval_sources,
                    react_step_count=trace.react_step_count,
                    fill_weights=fill_weights,
                ),
                reverse=True,
            ):
                if candidate.memory_id in output_ids:
                    continue
                fill_score = self._score_react_fill_candidate(
                    candidate=candidate,
                    evidence_counts=evidence_counts,
                    retrieval_sources=retrieval_sources,
                    react_step_count=trace.react_step_count,
                    fill_weights=fill_weights,
                )
                output.append(candidate.model_copy(update={"score": fill_score}))
                output_ids.add(candidate.memory_id)
                if len(output) >= retrieve.top_k:
                    break

        trace.final_count = len(output)
        if output:
            scores = sorted(result.score or 0.0 for result in output)
            trace.final_score_avg = sum(scores) / len(scores)
            trace.final_score_p50 = scores[len(scores) // 2]
            trace.final_score_p10 = scores[max(0, len(scores) // 10)]
            trace.domain_dist = dict(Counter(result.metadata.get("domain", "") for result in output))
            trace.source_dist = dict(Counter(result.metadata.get("source", "rag") for result in output))
            trace.type_dist = dict(Counter(result.metadata.get("type", "") for result in output))

        judge_rank_map = {memory_id: rank for rank, memory_id in enumerate(selected_ids)}
        final_score_map = {result.memory_id: result.score or 0.0 for result in output}
        final_rank_map = {result.memory_id: rank for rank, result in enumerate(output)}
        for memory_id, candidate in candidate_map.items():
            trace.result_details.append(
                ResultDetail(
                    memory_id=memory_id,
                    hit_count=hit_counts.get(memory_id, 1),
                    evidence_count=evidence_counts.get(memory_id, 1),
                    rag_score=candidate.score or 0.0,
                    from_expansion="react_expand" in retrieval_sources.get(memory_id, set())
                    or candidate.metadata.get("source") == "graph_expansion",
                    judge_rank=judge_rank_map.get(memory_id),
                    final_score=final_score_map.get(memory_id),
                    final_rank=final_rank_map.get(memory_id),
                    memory_domain=candidate.metadata.get("domain", ""),
                    memory_type=candidate.metadata.get("type", ""),
                    memory_source=candidate.metadata.get("source", ""),
                    retrieval_sources=sorted(retrieval_sources.get(memory_id, set())),
                )
            )

        trace.latency_total_ms = int((time.monotonic() - t_total) * 1000)
        self._emit_trace(trace)
        return output
