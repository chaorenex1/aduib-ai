from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

from runtime.memory.types import MemorySignalType

logger = logging.getLogger(__name__)

# 默认参数，同时也是各组件的 fallback 值
DEFAULT_PARAMS: dict = {
    "quality_scorer": {
        "recency_half_life_days": 30.0,
        "max_access_saturation": 10,
        "max_tag_saturation": 5,
        "weight_recency": 0.5,
        "weight_usage": 0.3,
        "weight_richness": 0.2,
    },
    "insight_distiller": {
        "min_episodic_count": 3,
        "max_topics_per_run": 10,
    },
    "memory_pruner": {
        "quality_threshold": 0.2,
        "inactive_days": 60,
        "retention_threshold": 0.1,
        "half_life_hours": 168.0,
    },
}

# 各参数的合法范围，防止 LLM 输出越界值
PARAM_BOUNDS: dict = {
    "quality_scorer": {
        "recency_half_life_days": (7.0, 180.0),
        "max_access_saturation": (3, 50),
        "max_tag_saturation": (2, 20),
        "weight_recency": (0.1, 0.8),
        "weight_usage": (0.1, 0.6),
        "weight_richness": (0.05, 0.4),
    },
    "insight_distiller": {
        "min_episodic_count": (2, 10),
        "max_topics_per_run": (3, 50),
    },
    "memory_pruner": {
        "quality_threshold": (0.05, 0.5),
        "inactive_days": (14, 180),
        "retention_threshold": (0.01, 0.3),
        "half_life_hours": (24.0, 720.0),
    },
}

PARAM_MAX_DELTAS: dict = {
    "quality_scorer": {
        "recency_half_life_days": 10.0,
        "max_access_saturation": 3,
        "max_tag_saturation": 2,
        "weight_recency": 0.08,
        "weight_usage": 0.08,
        "weight_richness": 0.08,
    },
    "insight_distiller": {
        "min_episodic_count": 1,
        "max_topics_per_run": 3,
    },
    "memory_pruner": {
        "quality_threshold": 0.05,
        "inactive_days": 14,
        "retention_threshold": 0.04,
        "half_life_hours": 48.0,
    },
}


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


def _validate_params(raw: dict) -> dict:
    """校验并裁剪 LLM 输出的参数，确保所有值在合法范围内。"""
    result: dict = {}
    for component, defaults in DEFAULT_PARAMS.items():
        raw_comp = raw.get(component, {})
        bounds = PARAM_BOUNDS.get(component, {})
        comp_result: dict = {}
        for key, default_val in defaults.items():
            val = raw_comp.get(key, default_val)
            # 类型强转
            try:
                val = type(default_val)(val)
            except (TypeError, ValueError):
                val = default_val
            # 边界裁剪
            if key in bounds:
                lo, hi = bounds[key]
                val = _clamp(val, lo, hi)
            comp_result[key] = val
        # 修正权重之和为 1.0
        if component == "quality_scorer":
            w_sum = comp_result["weight_recency"] + comp_result["weight_usage"] + comp_result["weight_richness"]
            if abs(w_sum - 1.0) > 0.01:
                scale = 1.0 / w_sum
                comp_result["weight_recency"] = round(comp_result["weight_recency"] * scale, 4)
                comp_result["weight_usage"] = round(comp_result["weight_usage"] * scale, 4)
                comp_result["weight_richness"] = round(
                    1.0 - comp_result["weight_recency"] - comp_result["weight_usage"],
                    4,
                )
        result[component] = comp_result
    return result


class ParamOptimizer:
    """收集统计数据 → LLM 评估 → 写入 memory_learning_params。"""

    OPTIMIZE_MIN_CYCLES: int = 7  # 至少有这么多次 learning log 才触发
    OPTIMIZE_INTERVAL_DAYS: int = 7  # 上次优化距今超过 N 天才重新优化
    OPTIMIZE_MIN_RETRIEVAL_QUERIES: int = 8
    OPTIMIZE_MIN_EXPOSED_MEMORIES: int = 5

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def should_optimize(self) -> bool:
        """判断当前是否需要执行参数优化。"""
        from models.engine import get_db
        from models.memory_learning_log import MemoryLearningLog
        from models.memory_learning_params import MemoryLearningParams

        with get_db() as session:
            cycle_count = session.query(MemoryLearningLog).filter(MemoryLearningLog.user_id == self.user_id).count()
            if cycle_count < self.OPTIMIZE_MIN_CYCLES:
                return False

            cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=self.OPTIMIZE_INTERVAL_DAYS)
            last = (
                session.query(MemoryLearningParams)
                .filter(MemoryLearningParams.user_id == self.user_id)
                .order_by(MemoryLearningParams.created_at.desc())
                .first()
            )
            if last is not None and last.created_at >= cutoff:
                return False

        return True

    def load_params(self) -> dict:
        """加载当前生效参数，无记录时返回默认值。"""
        from models.engine import get_db
        from models.memory_learning_params import MemoryLearningParams

        with get_db() as session:
            record = (
                session.query(MemoryLearningParams)
                .filter(MemoryLearningParams.user_id == self.user_id)
                .order_by(MemoryLearningParams.created_at.desc())
                .first()
            )
            if record is not None and isinstance(record.params, dict):
                return _validate_params(record.params)
        return DEFAULT_PARAMS

    def optimize(self) -> bool:
        """执行一次参数优化，返回是否成功写入新参数。"""
        try:
            stats = self._collect_stats()
            evidence_ok, evidence_reasons, evidence_summary = self._assess_optimization_evidence(stats)
            if not evidence_ok:
                logger.info(
                    "ParamOptimizer: skipped for user %s due to insufficient evidence: %s | summary=%s",
                    self.user_id,
                    "; ".join(evidence_reasons),
                    json.dumps(evidence_summary, ensure_ascii=False, sort_keys=True),
                )
                return False

            from runtime.generator.generator import LLMGenerator

            raw = LLMGenerator.evaluate_learning_params(stats)
            if not raw:
                logger.warning("ParamOptimizer: LLM returned empty result for user %s", self.user_id)
                return False

            candidate_params = _validate_params(raw)
            current_params = _validate_params(stats.get("current_params", DEFAULT_PARAMS))
            validated, change_limit_summary = self._apply_param_change_limits(current_params, candidate_params)
            reasoning = raw.get("reasoning", "")
            debug_snapshot = self._build_optimizer_debug_snapshot(stats, raw, validated, change_limit_summary)
            reasoning_with_snapshot = self._format_reasoning_with_snapshot(reasoning, debug_snapshot)

            from models.engine import get_db
            from models.memory_learning_params import MemoryLearningParams

            with get_db() as session:
                session.add(
                    MemoryLearningParams(
                        user_id=self.user_id,
                        params=validated,
                        reasoning=reasoning_with_snapshot,
                    )
                )
                session.commit()

            logger.info(
                "ParamOptimizer: wrote new params for user %s — reasoning: %s",
                self.user_id,
                reasoning[:120] if reasoning else "(none)",
            )
            logger.info(
                "ParamOptimizer: debug snapshot for user %s: %s",
                self.user_id,
                json.dumps(debug_snapshot, ensure_ascii=False, sort_keys=True),
            )
            return True

        except Exception:
            logger.exception("ParamOptimizer: optimization failed for user %s", self.user_id)
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_trends(cycles: list[dict]) -> dict:
        """将原始 cycle 列表压缩为趋势摘要，前半段 vs 后半段平均值对比。

        返回结构：
        {
          "<metric>": {
            "early_avg": float,   # 前半段均值
            "recent_avg": float,  # 后半段均值
            "delta": float,       # recent - early（正=上升，负=下降）
            "direction": str,     # "rising" | "falling" | "stable"
          }, ...
          "error_rate": float,    # 有 error 的 cycle 占比
          "cycle_count": int,
        }
        """
        if not cycles:
            return {"cycle_count": 0}

        metrics = ["quality_scored", "insights_created", "merges_performed", "memories_pruned"]
        n = len(cycles)
        mid = max(1, n // 2)
        early = cycles[:mid]
        recent = cycles[mid:]

        def avg(rows, key):
            vals = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
            return round(sum(vals) / len(vals), 3) if vals else 0.0

        trends: dict = {"cycle_count": n}
        for m in metrics:
            e = avg(early, m)
            r = avg(recent, m)
            delta = round(r - e, 3)
            if abs(delta) < 0.5:
                direction = "stable"
            elif delta > 0:
                direction = "rising"
            else:
                direction = "falling"
            trends[m] = {"early_avg": e, "recent_avg": r, "delta": delta, "direction": direction}

        error_count = sum(1 for c in cycles if c.get("error"))
        trends["error_rate"] = round(error_count / n, 3)
        return trends

    @staticmethod
    def _summarize_retrieval_rows(rows: list[dict]) -> dict:
        """压缩检索质量指标，供趋势分析和 LLM 调参参考。"""
        if not rows:
            return {"query_count": 0}

        n = len(rows)

        def avg(key: str, digits: int = 4) -> float:
            vals = [float(r.get(key, 0.0) or 0.0) for r in rows]
            return round(sum(vals) / n, digits) if vals else 0.0

        return {
            "query_count": n,
            "success_rate": avg("success_rate"),
            "empty_rate": avg("empty_rate"),
            "result_fill_rate": avg("result_fill_rate"),
            "avg_final_score": avg("avg_final_score"),
            "avg_selection_rate": avg("avg_selection_rate"),
            "supported_result_ratio": avg("supported_result_ratio"),
            "expansion_result_ratio": avg("expansion_result_ratio"),
            "avg_latency_ms": avg("avg_latency_ms", digits=1),
            "avg_react_steps": avg("avg_react_steps", digits=3),
        }

    @classmethod
    def _compute_retrieval_trends(cls, retrievals: list[dict]) -> dict:
        """将最近检索日志压缩为更贴近质量的趋势摘要。"""
        if not retrievals:
            return {
                "query_count": 0,
                "overall": {"query_count": 0},
                "trends": {},
                "stop_reason_dist": {},
                "by_type": {},
            }

        n = len(retrievals)
        mid = max(1, n // 2)
        early = retrievals[:mid]
        recent = retrievals[mid:]

        overall = cls._summarize_retrieval_rows(retrievals)
        early_summary = cls._summarize_retrieval_rows(early)
        recent_summary = cls._summarize_retrieval_rows(recent)

        thresholds = {
            "success_rate": 0.02,
            "empty_rate": 0.02,
            "result_fill_rate": 0.03,
            "avg_final_score": 0.03,
            "avg_selection_rate": 0.03,
            "supported_result_ratio": 0.03,
            "expansion_result_ratio": 0.03,
            "avg_latency_ms": 50.0,
            "avg_react_steps": 0.25,
        }

        trends: dict[str, dict] = {"query_count": n}
        for metric, stable_threshold in thresholds.items():
            early_avg = float(early_summary.get(metric, 0.0) or 0.0)
            recent_avg = float(recent_summary.get(metric, 0.0) or 0.0)
            delta = round(recent_avg - early_avg, 4)
            if abs(delta) < stable_threshold:
                direction = "stable"
            elif delta > 0:
                direction = "rising"
            else:
                direction = "falling"
            trends[metric] = {
                "early_avg": round(early_avg, 4),
                "recent_avg": round(recent_avg, 4),
                "delta": delta,
                "direction": direction,
            }

        stop_reason_dist: dict[str, float] = {}
        stop_reason_counts: dict[str, int] = {}
        for retrieval in retrievals:
            stop_reason = str(retrieval.get("react_stop_reason") or "").strip()
            if not stop_reason:
                continue
            stop_reason_counts[stop_reason] = stop_reason_counts.get(stop_reason, 0) + 1
        for stop_reason, count in sorted(stop_reason_counts.items(), key=lambda item: item[1], reverse=True):
            stop_reason_dist[stop_reason] = round(count / n, 4)

        rows_by_type: dict[str, list[dict]] = {}
        for retrieval in retrievals:
            retrieve_type = str(retrieval.get("retrieve_type") or "unknown")
            rows_by_type.setdefault(retrieve_type, []).append(retrieval)

        return {
            "query_count": n,
            "overall": overall,
            "trends": trends,
            "stop_reason_dist": stop_reason_dist,
            "by_type": {
                retrieve_type: cls._summarize_retrieval_rows(rows) for retrieve_type, rows in rows_by_type.items()
            },
        }

    @staticmethod
    def _compute_signal_funnel(signal_rows: list[dict]) -> dict:
        """基于 LearningSignal 构建轻量漏斗摘要。"""
        if not signal_rows:
            return {
                "event_counts": {"exposed": 0, "selected": 0, "used_in_answer": 0},
                "unique_memory_counts": {"exposed": 0, "selected": 0, "used_in_answer": 0},
                "rates": {
                    "selected_per_exposed": 0.0,
                    "used_per_selected": 0.0,
                    "used_per_exposed": 0.0,
                },
                "exposed_by_retrieve_type": {},
            }

        stage_map = {
            MemorySignalType.MEMORY_EXPOSED.value: "exposed",
            MemorySignalType.MEMORY_SELECTED.value: "selected",
            MemorySignalType.MEMORY_USED_IN_ANSWER.value: "used_in_answer",
        }
        event_counts = {"exposed": 0, "selected": 0, "used_in_answer": 0}
        unique_ids = {
            "exposed": set(),
            "selected": set(),
            "used_in_answer": set(),
        }
        exposed_by_retrieve_type: dict[str, dict[str, object]] = {}

        for row in signal_rows:
            signal_type = str(row.get("signal_type") or "")
            stage = stage_map.get(signal_type)
            if stage is None:
                continue
            event_counts[stage] += 1

            source_id = str(row.get("source_id") or "").strip()
            if source_id:
                unique_ids[stage].add(source_id)

            if stage != "exposed":
                continue

            context = row.get("context") if isinstance(row.get("context"), dict) else {}
            retrieve_type = str(context.get("retrieve_type") or "unknown").strip() or "unknown"
            bucket = exposed_by_retrieve_type.setdefault(retrieve_type, {"event_count": 0, "memory_ids": set()})
            bucket["event_count"] = int(bucket.get("event_count", 0)) + 1
            if source_id:
                bucket_memory_ids = bucket.get("memory_ids")
                if isinstance(bucket_memory_ids, set):
                    bucket_memory_ids.add(source_id)

        exposed_unique = len(unique_ids["exposed"])
        selected_unique = len(unique_ids["selected"])
        used_unique = len(unique_ids["used_in_answer"])

        return {
            "event_counts": event_counts,
            "unique_memory_counts": {
                "exposed": exposed_unique,
                "selected": selected_unique,
                "used_in_answer": used_unique,
            },
            "rates": {
                "selected_per_exposed": round(selected_unique / max(exposed_unique, 1), 4),
                "used_per_selected": round(used_unique / max(selected_unique, 1), 4),
                "used_per_exposed": round(used_unique / max(exposed_unique, 1), 4),
            },
            "exposed_by_retrieve_type": {
                retrieve_type: {
                    "event_count": int(bucket.get("event_count", 0)),
                    "unique_memory_count": (
                        len(bucket["memory_ids"])
                        if isinstance(bucket.get("memory_ids"), set)
                        else 0
                    ),
                }
                for retrieve_type, bucket in exposed_by_retrieve_type.items()
            },
        }

    @staticmethod
    def _build_retrieval_text_summary(retrieval_quality: dict, signal_funnel: dict) -> list[str]:
        """将趋势和漏斗压缩为文本摘要，方便 LLM 快速抓重点。"""
        query_count = int(retrieval_quality.get("query_count", 0) or 0)
        if query_count <= 0:
            return ["最近30天没有检索日志，暂时无法判断检索质量趋势。"]

        overall = retrieval_quality.get("overall", {}) if isinstance(retrieval_quality, dict) else {}
        trends = retrieval_quality.get("trends", {}) if isinstance(retrieval_quality, dict) else {}
        stop_reason_dist = (
            retrieval_quality.get("stop_reason_dist", {}) if isinstance(retrieval_quality, dict) else {}
        )
        rates = signal_funnel.get("rates", {}) if isinstance(signal_funnel, dict) else {}
        unique_counts = signal_funnel.get("unique_memory_counts", {}) if isinstance(signal_funnel, dict) else {}
        exposed_by_type = (
            signal_funnel.get("exposed_by_retrieve_type", {}) if isinstance(signal_funnel, dict) else {}
        )

        def trend_phrase(metric: str) -> str:
            metric_trend = trends.get(metric, {}) if isinstance(trends, dict) else {}
            direction = str(metric_trend.get("direction") or "stable")
            delta = float(metric_trend.get("delta", 0.0) or 0.0)
            return f"{metric}:{direction}({delta:+.4f})"

        summary = [
            (
                f"最近30天共有{query_count}次检索，"
                f"success_rate={float(overall.get('success_rate', 0.0) or 0.0):.4f}，"
                f"empty_rate={float(overall.get('empty_rate', 0.0) or 0.0):.4f}，"
                f"avg_final_score={float(overall.get('avg_final_score', 0.0) or 0.0):.4f}，"
                f"avg_latency_ms={float(overall.get('avg_latency_ms', 0.0) or 0.0):.1f}。"
            ),
            "关键趋势: "
            + "；".join(
                [
                    trend_phrase("success_rate"),
                    trend_phrase("empty_rate"),
                    trend_phrase("avg_final_score"),
                    trend_phrase("supported_result_ratio"),
                    trend_phrase("avg_latency_ms"),
                ]
            ),
            (
                "记忆漏斗: exposed="
                f"{int(unique_counts.get('exposed', 0) or 0)} -> "
                f"selected={int(unique_counts.get('selected', 0) or 0)} -> "
                f"used_in_answer={int(unique_counts.get('used_in_answer', 0) or 0)}，"
                f"selected/exposed={float(rates.get('selected_per_exposed', 0.0) or 0.0):.4f}，"
                f"used/selected={float(rates.get('used_per_selected', 0.0) or 0.0):.4f}。"
            ),
        ]

        if stop_reason_dist:
            top_reasons = ", ".join(f"{name}={ratio:.2%}" for name, ratio in list(stop_reason_dist.items())[:3])
            summary.append(f"主要停止原因: {top_reasons}。")

        if exposed_by_type:
            exposure_mix = ", ".join(
                (
                    f"{retrieve_type}:events={int(bucket.get('event_count', 0) or 0)}"
                    f"/unique={int(bucket.get('unique_memory_count', 0) or 0)}"
                )
                for retrieve_type, bucket in sorted(exposed_by_type.items())
            )
            summary.append(f"暴露来源分布: {exposure_mix}。")

        return summary

    @staticmethod
    def _build_optimizer_debug_snapshot(stats: dict, raw: dict, validated: dict, change_limit_summary: dict) -> dict:
        """生成一份精简且可持久化的调试快照。"""
        retrieval_quality = stats.get("retrieval_quality", {}) if isinstance(stats, dict) else {}
        signal_funnel = stats.get("signal_funnel", {}) if isinstance(stats, dict) else {}
        return {
            "cycle_trends": stats.get("cycle_trends", {}) if isinstance(stats, dict) else {},
            "retrieval_quality_overall": (
                retrieval_quality.get("overall", {}) if isinstance(retrieval_quality, dict) else {}
            ),
            "retrieval_quality_trends": (
                retrieval_quality.get("trends", {}) if isinstance(retrieval_quality, dict) else {}
            ),
            "signal_funnel_rates": signal_funnel.get("rates", {}) if isinstance(signal_funnel, dict) else {},
            "retrieval_text_summary": (
                stats.get("retrieval_text_summary", []) if isinstance(stats, dict) else []
            ),
            "current_params": stats.get("current_params", {}) if isinstance(stats, dict) else {},
            "llm_reasoning": str(raw.get("reasoning", "") or "") if isinstance(raw, dict) else "",
            "change_limit_summary": change_limit_summary if isinstance(change_limit_summary, dict) else {},
            "validated_params": validated if isinstance(validated, dict) else {},
        }

    @staticmethod
    def _format_reasoning_with_snapshot(reasoning: str, debug_snapshot: dict) -> str:
        """将调参理由和 debug snapshot 拼成可落库文本。"""
        reasoning_text = str(reasoning or "").strip()
        snapshot_json = json.dumps(debug_snapshot, ensure_ascii=False, indent=2, sort_keys=True)
        if reasoning_text:
            return f"{reasoning_text}\n\n[optimizer_debug_snapshot]\n{snapshot_json}"
        return f"[optimizer_debug_snapshot]\n{snapshot_json}"

    @classmethod
    def _assess_optimization_evidence(cls, stats: dict) -> tuple[bool, list[str], dict]:
        """判断当前统计是否足以支撑一次有效调参。"""
        retrieval_quality = stats.get("retrieval_quality", {}) if isinstance(stats, dict) else {}
        signal_funnel = stats.get("signal_funnel", {}) if isinstance(stats, dict) else {}
        retrieval_query_count = int(retrieval_quality.get("query_count", 0) or 0)
        unique_memory_counts = (
            signal_funnel.get("unique_memory_counts", {}) if isinstance(signal_funnel, dict) else {}
        )
        exposed_unique = int(unique_memory_counts.get("exposed", 0) or 0)
        selected_unique = int(unique_memory_counts.get("selected", 0) or 0)
        used_unique = int(unique_memory_counts.get("used_in_answer", 0) or 0)
        rates = signal_funnel.get("rates", {}) if isinstance(signal_funnel, dict) else {}

        reasons: list[str] = []
        if retrieval_query_count < cls.OPTIMIZE_MIN_RETRIEVAL_QUERIES:
            reasons.append(
                f"retrieval_query_count_below_threshold({retrieval_query_count}<{cls.OPTIMIZE_MIN_RETRIEVAL_QUERIES})"
            )
        if exposed_unique < cls.OPTIMIZE_MIN_EXPOSED_MEMORIES:
            reasons.append(
                f"exposed_memory_count_below_threshold({exposed_unique}<{cls.OPTIMIZE_MIN_EXPOSED_MEMORIES})"
            )
        if selected_unique <= 0:
            reasons.append("selected_memory_signal_missing")

        evidence_summary = {
            "retrieval_query_count": retrieval_query_count,
            "exposed_unique_memories": exposed_unique,
            "selected_unique_memories": selected_unique,
            "used_unique_memories": used_unique,
            "selected_per_exposed": float(rates.get("selected_per_exposed", 0.0) or 0.0),
            "used_per_selected": float(rates.get("used_per_selected", 0.0) or 0.0),
        }
        return not reasons, reasons, evidence_summary

    @classmethod
    def _apply_param_change_limits(cls, current_params: dict, candidate_params: dict) -> tuple[dict, dict]:
        """限制单次参数变更幅度，避免一次优化改得过猛。"""
        base_current = _validate_params(current_params or DEFAULT_PARAMS)
        base_candidate = _validate_params(candidate_params or DEFAULT_PARAMS)
        limited: dict = {}
        limited_changes: list[dict] = []

        for component, defaults in DEFAULT_PARAMS.items():
            current_component = base_current.get(component, {})
            candidate_component = base_candidate.get(component, {})
            max_deltas = PARAM_MAX_DELTAS.get(component, {})
            limited_component: dict = {}

            for key, default_value in defaults.items():
                current_value = current_component.get(key, default_value)
                candidate_value = candidate_component.get(key, default_value)
                max_delta = max_deltas.get(key)
                if max_delta is None:
                    limited_value = candidate_value
                else:
                    limited_value = _clamp(candidate_value, current_value - max_delta, current_value + max_delta)
                    if isinstance(default_value, int) and not isinstance(default_value, bool):
                        limited_value = int(round(limited_value))
                    elif isinstance(default_value, float):
                        limited_value = round(float(limited_value), 6)
                    if limited_value != candidate_value:
                        limited_changes.append(
                            {
                                "component": component,
                                "key": key,
                                "current": current_value,
                                "candidate": candidate_value,
                                "limited": limited_value,
                                "max_delta": max_delta,
                            }
                        )
                limited_component[key] = limited_value
            limited[component] = limited_component

        validated_limited = _validate_params(limited)
        return validated_limited, {"limited_change_count": len(limited_changes), "limited_changes": limited_changes}

    def _collect_stats(self) -> dict:
        """从数据库收集统计数据，作为 LLM 的输入。"""
        import math

        from sqlalchemy import func

        from models.engine import get_db
        from models.memory import MemoryBase, MemoryRecord
        from models.memory_learning_log import MemoryLearningLog
        from models.memory_learning_params import MemoryLearningParams
        from models.memory_retrieval_log import MemoryRetrievalLog, MemoryRetrievalResult

        # 1. 最近 30 天的 learning cycle 趋势
        cutoff_30d = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=30)
        with get_db() as session:
            logs = (
                session.query(MemoryLearningLog)
                .filter(
                    MemoryLearningLog.user_id == self.user_id,
                    MemoryLearningLog.created_at >= cutoff_30d,
                )
                .order_by(MemoryLearningLog.created_at.asc())
                .all()
            )
            recent_cycles = [
                {
                    "date": log.created_at.strftime("%Y-%m-%d") if log.created_at else "",
                    "quality_scored": log.quality_scored or 0,
                    "insights_created": log.insights_created or 0,
                    "merges_performed": log.merges_performed or 0,
                    "memories_pruned": log.memories_pruned or 0,
                    "elapsed_seconds": round(log.elapsed_seconds or 0, 1),
                    "error": log.error or None,
                }
                for log in logs
            ]
        cycle_trends = self._compute_trends(recent_cycles)

        # 2. 当前记忆质量分布
        with get_db() as session:
            quality_rows = (
                session.query(MemoryRecord.quality_score)
                .join(MemoryRecord.memory_base)
                .filter(
                    MemoryBase.user_id == self.user_id,
                    MemoryRecord.deleted == 0,
                    MemoryRecord.quality_score.isnot(None),
                )
                .all()
            )
            scores = sorted([r.quality_score for r in quality_rows if r.quality_score is not None])

        def percentile(lst, p):
            if not lst:
                return 0.0
            idx = int(math.ceil(p / 100 * len(lst))) - 1
            return round(lst[max(0, idx)], 4)

        quality_dist = {
            "total": len(scores),
            "p25": percentile(scores, 25),
            "p50": percentile(scores, 50),
            "p75": percentile(scores, 75),
            "low_ratio": round(sum(1 for s in scores if s < 0.2) / max(len(scores), 1), 4),
        }

        # 3. 情节/语义 类型分布
        with get_db() as session:
            type_rows = (
                session.query(MemoryRecord.type, func.count().label("cnt"))
                .join(MemoryRecord.memory_base)
                .filter(MemoryBase.user_id == self.user_id, MemoryRecord.deleted == 0)
                .group_by(MemoryRecord.type)
                .all()
            )
        type_counts = {row.type: row.cnt for row in type_rows}
        total_mem = sum(type_counts.values()) or 1
        type_ratio = {t: round(c / total_mem, 4) for t, c in type_counts.items()}

        # 4. 话题统计
        with get_db() as session:
            total_topic_rows = (
                session.query(MemoryRecord.domain, MemoryRecord.topic)
                .join(MemoryRecord.memory_base)
                .filter(
                    MemoryBase.user_id == self.user_id,
                    MemoryRecord.deleted == 0,
                    MemoryRecord.topic.isnot(None),
                    MemoryRecord.topic != "",
                )
                .distinct()
                .all()
            )
            semantic_topic_rows = (
                session.query(MemoryRecord.domain, MemoryRecord.topic)
                .join(MemoryRecord.memory_base)
                .filter(
                    MemoryBase.user_id == self.user_id,
                    MemoryRecord.type == "semantic",
                    MemoryRecord.deleted == 0,
                    MemoryRecord.topic.isnot(None),
                    MemoryRecord.topic != "",
                )
                .distinct()
                .all()
            )
        total_topics = len(total_topic_rows)
        topics_with_semantic = len(semantic_topic_rows)
        topic_stats = {
            "total_topics": total_topics,
            "topics_with_semantic": topics_with_semantic,
            "semantic_coverage": round(topics_with_semantic / max(total_topics, 1), 4),
        }

        # 5. 当前生效参数
        with get_db() as session:
            last_param = (
                session.query(MemoryLearningParams)
                .filter(MemoryLearningParams.user_id == self.user_id)
                .order_by(MemoryLearningParams.created_at.desc())
                .first()
            )
            current_params = last_param.params if last_param else DEFAULT_PARAMS

        # 6. 记忆采纳信号趋势
        with get_db() as session:
            from models import LearningSignal

            adoption_rows = (
                session.query(LearningSignal.value)
                .filter(
                    LearningSignal.user_id == self.user_id,
                    LearningSignal.signal_type == MemorySignalType.MEMORY_ADOPTION.value,
                    LearningSignal.created_at >= cutoff_30d,
                )
                .all()
            )
            total_signals = len(adoption_rows)
            positive = sum(1 for row in adoption_rows if row.value is not None and row.value > 0)
            values = [row.value for row in adoption_rows if isinstance(row.value, (int, float))]
            adoption_rate = round(positive / max(total_signals, 1), 4)
            avg_value = round(sum(values) / len(values), 4) if values else 0.0
            adoption_rate_trend = {
                "total_signals": total_signals,
                "positive": positive,
                "adoption_rate": adoption_rate,
                "avg_value": avg_value,
            }

        # 7. 失败模式分布
        with get_db() as session:
            from models import FailurePattern

            pattern_rows = (
                session.query(FailurePattern.pattern_type, FailurePattern.occurrence_count)
                .filter(FailurePattern.user_id == self.user_id)
                .all()
            )
            total_patterns = len(pattern_rows)
            pattern_counts: dict[str, int] = {}
            for row in pattern_rows:
                pattern_counts[row.pattern_type] = pattern_counts.get(row.pattern_type, 0) + (row.occurrence_count or 0)
            top_patterns = [
                {"pattern_type": pattern_type, "count": count}
                for pattern_type, count in sorted(pattern_counts.items(), key=lambda item: item[1], reverse=True)[:10]
            ]
            failure_pattern_dist = {"top_patterns": top_patterns, "total_patterns": total_patterns}

        # 8. 路由效率
        with get_db() as session:
            latest_params = (
                session.query(MemoryLearningParams)
                .filter(MemoryLearningParams.user_id == self.user_id)
                .order_by(MemoryLearningParams.created_at.desc())
                .first()
            )
            params = latest_params.params if latest_params and isinstance(latest_params.params, dict) else {}
            routing_config = params.get("routing_config", {}) if isinstance(params, dict) else {}
            if isinstance(routing_config, dict):
                routing_efficiency = {
                    task_level: config.get("value_score")
                    for task_level, config in routing_config.items()
                    if isinstance(config, dict) and "value_score" in config
                }
            else:
                routing_efficiency = {}

        # 9. 信号覆盖率
        with get_db() as session:
            from models import LearningSignal

            distinct_source_count = (
                session.query(func.count(func.distinct(LearningSignal.source_id)))
                .filter(
                    LearningSignal.user_id == self.user_id,
                    LearningSignal.signal_type.in_(
                        [
                            MemorySignalType.MEMORY_ADOPTION.value,
                            MemorySignalType.MEMORY_EXPOSED.value,
                        ]
                    ),
                )
                .scalar()
                or 0
            )
            coverage_ratio = round(distinct_source_count / max(total_mem, 1), 4)
            signal_coverage = {
                "total_memories": total_mem,
                "memories_with_signal": distinct_source_count,
                "coverage_ratio": coverage_ratio,
            }

        # 10. 最近 30 天检索质量趋势 + 信号漏斗
        retrieval_rows: list[dict] = []
        signal_funnel_rows: list[dict] = []
        with get_db() as session:
            retrieval_logs = (
                session.query(MemoryRetrievalLog)
                .filter(
                    MemoryRetrievalLog.user_id == self.user_id,
                    MemoryRetrievalLog.created_at >= cutoff_30d,
                )
                .order_by(MemoryRetrievalLog.created_at.asc())
                .all()
            )
            log_ids = [log.id for log in retrieval_logs]
            detail_rows = (
                session.query(
                    MemoryRetrievalResult.log_id,
                    MemoryRetrievalResult.final_rank,
                    MemoryRetrievalResult.evidence_count,
                    MemoryRetrievalResult.from_expansion,
                )
                .filter(MemoryRetrievalResult.log_id.in_(log_ids))
                .all()
                if log_ids
                else []
            )
            from models import LearningSignal

            signal_rows = (
                session.query(LearningSignal.signal_type, LearningSignal.source_id, LearningSignal.context)
                .filter(
                    LearningSignal.user_id == self.user_id,
                    LearningSignal.created_at >= cutoff_30d,
                    LearningSignal.signal_type.in_(
                        [
                            MemorySignalType.MEMORY_EXPOSED.value,
                            MemorySignalType.MEMORY_SELECTED.value,
                            MemorySignalType.MEMORY_USED_IN_ANSWER.value,
                        ]
                    ),
                )
                .all()
            )

        detail_summary_by_log: dict = {}
        for detail in detail_rows:
            log_summary = detail_summary_by_log.setdefault(
                detail.log_id,
                {"supported_final": 0, "expansion_final": 0},
            )
            if detail.final_rank is None:
                continue
            if int(detail.evidence_count or 0) >= 2:
                log_summary["supported_final"] += 1
            if bool(detail.from_expansion):
                log_summary["expansion_final"] += 1

        for log in retrieval_logs:
            final_count = int(log.final_count or 0)
            detail_summary = detail_summary_by_log.get(log.id, {})
            retrieval_rows.append(
                {
                    "date": log.created_at.strftime("%Y-%m-%d") if log.created_at else "",
                    "retrieve_type": log.retrieve_type or "llm",
                    "success_rate": 1.0 if final_count > 0 else 0.0,
                    "empty_rate": 1.0 if final_count == 0 else 0.0,
                    "result_fill_rate": round(final_count / max(int(log.top_k or 1), 1), 4),
                    "avg_final_score": round(float(log.final_score_avg or 0.0), 4),
                    "avg_selection_rate": round(float(log.judge_selection_rate or 0.0), 4),
                    "supported_result_ratio": (
                        round(int(detail_summary.get("supported_final", 0)) / final_count, 4) if final_count else 0.0
                    ),
                    "expansion_result_ratio": (
                        round(int(detail_summary.get("expansion_final", 0)) / final_count, 4) if final_count else 0.0
                    ),
                    "avg_latency_ms": float(log.latency_total_ms or 0.0),
                    "avg_react_steps": float(log.react_step_count or 0.0),
                    "react_stop_reason": log.react_stop_reason or "",
                }
            )
        for row in signal_rows:
            signal_funnel_rows.append(
                {
                    "signal_type": row.signal_type,
                    "source_id": row.source_id,
                    "context": row.context if isinstance(row.context, dict) else {},
                }
            )
        retrieval_quality = self._compute_retrieval_trends(retrieval_rows)
        signal_funnel = self._compute_signal_funnel(signal_funnel_rows)
        retrieval_text_summary = self._build_retrieval_text_summary(retrieval_quality, signal_funnel)

        return {
            "recent_cycles": recent_cycles,  # 原始数据（保留供 LLM 参考）
            "cycle_trends": cycle_trends,  # 预计算趋势：前半段 vs 后半段 delta + direction
            "memory_quality": quality_dist,
            "type_ratio": type_ratio,
            "topic_stats": topic_stats,
            "current_params": current_params,
            "adoption_rate_trend": adoption_rate_trend,
            "failure_pattern_dist": failure_pattern_dist,
            "routing_efficiency": routing_efficiency,
            "signal_coverage": signal_coverage,
            "retrieval_quality": retrieval_quality,
            "signal_funnel": signal_funnel,
            "retrieval_text_summary": retrieval_text_summary,
        }
