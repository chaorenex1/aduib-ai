import asyncio
import datetime
import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import text

from libs.deps import get_db

try:
    from models import Agent, AgentTodo, FailurePattern
except ImportError:
    AgentTodo = None
    Agent = None
    FailurePattern = None

try:
    from runtime.model_execution.large_language_model import LLMGenerator
except Exception:
    from runtime.generator.generator import LLMGenerator  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class FailureAnalyzerResult:
    patterns_found: int = field(default=0)
    patterns_updated: int = field(default=0)
    repair_generated: int = field(default=0)


class FailureAnalyzer:
    def __init__(self, lookback_days: int = 14) -> None:
        self.lookback_days = lookback_days

    async def analyze(self, user_id: str) -> FailureAnalyzerResult:
        result = FailureAnalyzerResult()
        if AgentTodo is None or Agent is None or FailurePattern is None:
            return result

        cutoff = datetime.datetime.now() - datetime.timedelta(days=self.lookback_days)

        try:
            with get_db() as session:
                failure_type_col = getattr(AgentTodo, "failure_type", None)
                if failure_type_col is None:
                    failure_type_col = text("NULL").label("failure_type")

                rows = (
                    session.query(
                        AgentTodo.id,
                        failure_type_col,
                        AgentTodo.failure_evidence,
                        AgentTodo.updated_at,
                    )
                    .join(Agent, text("CAST(agent_todo.agent_id AS TEXT) = CAST(agent.id AS TEXT)"))
                    .filter(AgentTodo.status == "failed")
                    .filter(AgentTodo.failure_evidence.isnot(None))
                    .filter(AgentTodo.updated_at >= cutoff)
                    .filter(Agent.user_id == user_id)
                    .limit(500)
                    .all()
                )

                grouped: dict[str, list[dict]] = {}
                for row in rows:
                    evidence = row.failure_evidence if isinstance(row.failure_evidence, dict) else {}
                    failure_type: Optional[str] = getattr(row, "failure_type", None) or evidence.get("failure_type")
                    pattern_type = _normalize_failure_type(failure_type)
                    item = {
                        "todo_id": row.id,
                        "failure_type": failure_type or pattern_type,
                        "failure_evidence": row.failure_evidence,
                        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                    }
                    grouped.setdefault(pattern_type, []).append(item)

                now = datetime.datetime.now()
                for pattern_type, items in grouped.items():
                    symptoms = _extract_symptoms(items)
                    hash_input = f"{user_id}:{pattern_type}:{symptoms}"
                    pattern_hash = hashlib.sha256(hash_input.encode()).hexdigest()

                    fp = session.query(FailurePattern).filter(FailurePattern.pattern_hash == pattern_hash).one_or_none()

                    if fp is None:
                        fp = FailurePattern(
                            user_id=user_id,
                            pattern_type=pattern_type,
                            pattern_hash=pattern_hash,
                            occurrence_count=len(items),
                            evidence=_trim_evidence(items),
                        )
                        session.add(fp)
                        result.patterns_found += 1
                    else:
                        fp.occurrence_count = (fp.occurrence_count or 0) + len(items)
                        existing = fp.evidence if isinstance(fp.evidence, list) else []
                        fp.evidence = (existing + items)[-20:]
                        fp.last_seen_at = now
                        result.patterns_updated += 1

                    if (fp.occurrence_count or 0) >= 3 and not (fp.repair_strategy or "").strip():
                        try:
                            strategy = await _generate_repair_strategy(pattern_type, fp.evidence or [])
                            fp.repair_strategy = strategy
                            result.repair_generated += 1
                        except Exception:
                            logger.warning(
                                "FailureAnalyzer: repair generation failed for %s", pattern_type, exc_info=True
                            )

                session.commit()
        except Exception:
            logger.warning("FailureAnalyzer: analyze failed for user %s", user_id, exc_info=True)

        return result


def _normalize_failure_type(value: Optional[str]) -> str:
    if not value:
        return "unknown"
    normalized = value.strip().lower().replace(" ", "_")
    return normalized or "unknown"


def _extract_symptoms(items: list[dict]) -> str:
    keys: set[str] = set()
    for item in items[:3]:
        evidence = item.get("failure_evidence")
        if isinstance(evidence, dict):
            keys.update(evidence.keys())
    return ":".join(sorted(keys))


def _trim_evidence(items: list[dict]) -> list[dict]:
    return items[-20:]


async def _generate_repair_strategy(pattern_type: str, evidence_items: list) -> str:
    prompt = (
        "You are a debugging expert. Analyze these failure patterns and suggest repair strategies.\n"
        f"Pattern type: {pattern_type}\n"
        "Evidence samples (up to 3):\n"
    )
    for item in evidence_items[:3]:
        prompt += f"- {json.dumps(item, ensure_ascii=False)}\n"
    prompt += "\nProvide a concise repair strategy (2-3 sentences) focusing on root cause and fix approach."

    try:
        generate = getattr(LLMGenerator, "generate_content", None)
        if generate is None:
            return ""
        if asyncio.iscoroutinefunction(generate):
            return await generate(prompt)
        return await asyncio.to_thread(generate, prompt)
    except Exception:
        logger.warning("Failed to generate repair strategy for %s", pattern_type)
        return ""
