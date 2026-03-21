from __future__ import annotations

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
            from runtime.generator.generator import LLMGenerator

            raw = LLMGenerator.evaluate_learning_params(stats)
            if not raw:
                logger.warning("ParamOptimizer: LLM returned empty result for user %s", self.user_id)
                return False

            validated = _validate_params(raw)
            reasoning = raw.get("reasoning", "")

            from models.engine import get_db
            from models.memory_learning_params import MemoryLearningParams

            with get_db() as session:
                session.add(
                    MemoryLearningParams(
                        user_id=self.user_id,
                        params=validated,
                        reasoning=reasoning,
                    )
                )
                session.commit()

            logger.info(
                "ParamOptimizer: wrote new params for user %s — reasoning: %s",
                self.user_id,
                reasoning[:120] if reasoning else "(none)",
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

    def _collect_stats(self) -> dict:
        """从数据库收集统计数据，作为 LLM 的输入。"""
        import math

        from sqlalchemy import func

        from models.engine import get_db
        from models.memory import MemoryBase, MemoryRecord
        from models.memory_learning_log import MemoryLearningLog
        from models.memory_learning_params import MemoryLearningParams

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
        }
