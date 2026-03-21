from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class LearningResult:
    user_id: str = ""
    quality_scored: int = 0
    insights_created: int = 0
    merges_performed: int = 0
    memories_pruned: int = 0
    signals_processed: int = 0
    memories_updated: int = 0
    patterns_found: int = 0
    patterns_updated: int = 0
    repair_generated: int = 0
    levels_optimized: int = 0
    routing_updated: bool = False
    elapsed_seconds: float = 0.0
    error: str = field(default="")


class MemoryLearningEngine:
    REDIS_LOCK_TTL: int = 3600

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id

    async def run_learning_cycle(self) -> LearningResult:
        result = LearningResult(user_id=self.user_id)
        start_time = time.monotonic()

        lock_key = f"memory_learning_lock:{self.user_id}"
        redis_client = None
        lock_acquired = False
        try:
            from component.cache.redis_cache import redis_client
        except Exception:
            pass

        if redis_client is not None:
            acquired = redis_client.set(lock_key, "1", ex=self.REDIS_LOCK_TTL, nx=True)
            if not acquired:
                logger.info("Learning cycle already running for user %s, skipping", self.user_id)
                result.error = "lock_not_acquired"
                return result
            lock_acquired = True

        try:
            # 加载当前生效的优化参数（无记录则使用默认值）
            from runtime.memory.learning.param_optimizer import ParamOptimizer

            optimizer = ParamOptimizer(self.user_id)
            active_params = optimizer.load_params()

            try:
                from runtime.memory.learning.quality_scorer import QualityScorer

                result.quality_scored = await QualityScorer(params=active_params.get("quality_scorer")).score_all(
                    self.user_id
                )
            except Exception:
                logger.exception("Phase 1 (QualityScorer) failed for user %s", self.user_id)

            try:
                from runtime.memory.learning.insight_distiller import InsightDistiller

                distil = await InsightDistiller(params=active_params.get("insight_distiller")).distill(self.user_id)
                result.insights_created = distil.insights_created
            except Exception:
                logger.exception("Phase 2 (InsightDistiller) failed for user %s", self.user_id)

            try:
                from runtime.memory.learning.memory_pruner import MemoryPruner

                prune = await MemoryPruner(params=active_params.get("memory_pruner")).prune(self.user_id)
                result.memories_pruned = prune.pruned
            except Exception:
                logger.exception("Phase 3 (MemoryPruner) failed for user %s", self.user_id)

            try:
                from runtime.memory.learning.signal_scorer import SignalScorer

                sig = await SignalScorer().score_all(self.user_id)
                result.signals_processed = sig.signals_processed
                result.memories_updated = sig.memories_updated
            except Exception:
                logger.exception("Phase 4 (SignalScorer) failed for user %s", self.user_id)

            try:
                from runtime.memory.learning.failure_analyzer import FailureAnalyzer

                fa_result = await FailureAnalyzer().analyze(self.user_id)
                result.patterns_found = fa_result.patterns_found
                result.patterns_updated = fa_result.patterns_updated
                result.repair_generated = fa_result.repair_generated
            except Exception:
                logger.exception("Phase 5 (FailureAnalyzer) failed for user %s", self.user_id)

            try:
                from runtime.memory.learning.cost_optimizer import CostOptimizer

                co_result = await CostOptimizer().optimize(self.user_id)
                result.levels_optimized = co_result.levels_optimized
                result.routing_updated = co_result.routing_updated
            except Exception:
                logger.exception("Phase 6 (CostOptimizer) failed for user %s", self.user_id)

            result.elapsed_seconds = round(time.monotonic() - start_time, 2)
            logger.info(
                (
                    "LearningEngine: user=%s scored=%d insights=%d merges=%d pruned=%d "
                    "signals=%d mem_updated=%d patterns=%d repairs=%d levels=%d "
                    "routing_updated=%s elapsed=%.2fs"
                ),
                self.user_id,
                result.quality_scored,
                result.insights_created,
                result.merges_performed,
                result.memories_pruned,
                result.signals_processed,
                result.memories_updated,
                result.patterns_found,
                result.repair_generated,
                result.levels_optimized,
                result.routing_updated,
                result.elapsed_seconds,
            )
            try:
                from models.engine import get_db
                from models.memory_learning_log import MemoryLearningLog

                with get_db() as session:
                    session.add(
                        MemoryLearningLog(
                            user_id=result.user_id,
                            quality_scored=result.quality_scored,
                            insights_created=result.insights_created,
                            merges_performed=result.merges_performed,
                            memories_pruned=result.memories_pruned,
                            signals_processed=result.signals_processed,
                            patterns_found=result.patterns_found,
                            routing_updated=result.routing_updated,
                            elapsed_seconds=result.elapsed_seconds,
                            error=result.error or None,
                        )
                    )
                    session.commit()
            except Exception:
                logger.warning(
                    "LearningEngine: failed to persist LearningResult for user %s",
                    self.user_id,
                    exc_info=True,
                )

            # 满足条件时触发参数优化（非阻塞，失败不影响主流程）
            try:
                if optimizer.should_optimize():
                    logger.info("LearningEngine: triggering param optimization for user %s", self.user_id)
                    optimizer.optimize()
            except Exception:
                logger.warning("LearningEngine: param optimization failed for user %s", self.user_id, exc_info=True)

            return result
        finally:
            if redis_client is not None and lock_acquired:
                redis_client.delete(lock_key)
