import datetime
import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import func, text

from libs.deps import get_db
from models import MemoryLearningParams, TaskCostRecord

logger = logging.getLogger(__name__)

EPSILON = 1e-9


@dataclass
class CostOptimizerResult:
    levels_optimized: int = field(default=0)
    routing_updated: bool = field(default=False)


class CostOptimizer:
    """Phase 7 of learning cycle: optimize cost-aware routing per task level."""

    def __init__(self, lookback_days: int = 30) -> None:
        self.lookback_days = lookback_days

    async def optimize(self, user_id: str) -> CostOptimizerResult:
        import asyncio

        try:
            cutoff = datetime.datetime.now() - datetime.timedelta(days=self.lookback_days)
            routing_config = await asyncio.to_thread(_compute_routing_config, user_id, cutoff)
            if not routing_config:
                return CostOptimizerResult()
            await _save_routing_config(user_id, routing_config)
            return CostOptimizerResult(levels_optimized=len(routing_config), routing_updated=True)
        except Exception:
            logger.warning("CostOptimizer failed for user %s", user_id, exc_info=True)
            return CostOptimizerResult()


def _compute_routing_config(user_id: str, cutoff: datetime.datetime) -> dict:
    with get_db() as session:
        rows = (
            session.query(TaskCostRecord)
            .filter(
                TaskCostRecord.user_id == user_id,
                TaskCostRecord.created_at >= cutoff,
                TaskCostRecord.outcome.isnot(None),
                TaskCostRecord.task_level.isnot(None),
            )
            .order_by(func.coalesce(TaskCostRecord.created_at, cutoff))
            .all()
        )

    if not rows:
        return {}

    by_level: dict[str, list[TaskCostRecord]] = {}
    for record in rows:
        level = str(record.task_level)
        by_level.setdefault(level, []).append(record)

    routing_config: dict[str, dict[str, object]] = {}

    for task_level, records in by_level.items():
        by_model: dict[tuple[Optional[str], Optional[str]], list[TaskCostRecord]] = {}
        for record in records:
            key = (record.model_id, record.provider)
            by_model.setdefault(key, []).append(record)

        best_key: tuple[Optional[str], Optional[str]] | None = None
        best_score = -1.0

        for key, grouped in by_model.items():
            total_count = len(grouped)
            if total_count == 0:
                continue
            success_count = sum(1 for item in grouped if item.outcome == "success")
            success_rate = success_count / total_count
            costs = [float(item.total_price) for item in grouped if item.total_price is not None]
            avg_cost = sum(costs) / len(costs) if costs else 0.0
            value_score = success_rate / (avg_cost + EPSILON)
            if value_score > best_score:
                best_score = value_score
                best_key = key

        if best_key is None:
            continue

        routing_config[task_level] = {
            "model_id": best_key[0],
            "provider": best_key[1],
            "value_score": round(best_score, 6),
        }

    return routing_config


async def _save_routing_config(user_id: str, routing_config: dict) -> None:
    import asyncio

    def _save_sync() -> None:
        with get_db() as session:
            latest: Optional[MemoryLearningParams] = (
                session.query(MemoryLearningParams)
                .filter(MemoryLearningParams.user_id == user_id)
                .order_by(text("created_at desc"))
                .first()
            )
            if latest is not None:
                existing_params = dict(latest.params or {})
                existing_params["routing_config"] = routing_config
                latest.params = existing_params
                session.commit()
                return

            session.add(
                MemoryLearningParams(
                    user_id=user_id,
                    params={"routing_config": routing_config},
                )
            )
            session.commit()

    await asyncio.to_thread(_save_sync)
