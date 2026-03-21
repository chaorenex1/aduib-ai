from __future__ import annotations

import json
from typing import Any

from libs.context import get_current_user_id
from models import Agent, ToolInfo, get_db
from runtime.tool.tool_manager import ToolManager

DEFAULT_CAPABILITY_TYPES = ("subagent", "skill", "tool")
MAX_LOOKUP_LIMIT = 50
MAX_SKILL_MODEL_CANDIDATES = 20


class CapabilityLookupError(ValueError):
    """Raised when capability lookup parameters are invalid."""


class CapabilityLookupService:
    @classmethod
    async def lookup(cls, payload: dict[str, Any], message_id: str | None = None) -> dict[str, Any]:
        del message_id

        query_value = payload.get("query")
        if query_value is None:
            query = ""
        elif isinstance(query_value, str):
            query = query_value.strip()
        else:
            raise CapabilityLookupError("query must be a string")

        selected_types = cls._parse_types(payload.get("types"))
        limit = cls._parse_limit(payload.get("limit"))
        include_meta = bool(payload.get("include_meta", True))
        user_id = payload.get("user_id") or get_current_user_id()
        candidate_terms = cls._extract_candidate_terms(query)
        query_terms = cls._build_terms(query, candidate_terms)

        results: list[dict[str, Any]] = []
        with get_db() as session:
            if "subagent" in selected_types:
                results.extend(cls._lookup_subagents(session, user_id=user_id, query_terms=query_terms))
            if "tool" in selected_types:
                results.extend(cls._lookup_tools(session, query_terms=query_terms))
        if "skill" in selected_types:
            skill_results = cls._lookup_skills()
            cls._apply_skill_relevance(skill_results, query=query, candidate_terms=query_terms)
            results.extend(skill_results)

        ranked = cls._rank_results(results, query=query, query_terms=query_terms)
        if query:
            ranked = [item for item in ranked if float(item.get("score", 0.0)) > 0.0]
        if not include_meta:
            for item in ranked:
                item.pop("meta", None)

        trimmed = ranked[:limit]
        return {
            "query": query,
            "candidate_terms": query_terms,
            "types": list(selected_types),
            "total": len(trimmed),
            "results": trimmed,
        }

    @classmethod
    def _lookup_subagents(cls, session, *, user_id: Any, query_terms: list[str]) -> list[dict[str, Any]]:
        query = session.query(Agent).filter(Agent.deleted == 0, Agent.builtin == 0)
        query = cls._apply_candidate_sql_filter(
            query,
            columns=[Agent.name, Agent.description],
            query_terms=query_terms,
        )
        rows = query.all()
        current_user_id = str(user_id).strip().lower() if user_id is not None else None
        results: list[dict[str, Any]] = []
        for agent in rows:
            if int(getattr(agent, "deleted", 0) or 0) != 0:
                continue
            if int(getattr(agent, "builtin", 0) or 0) != 0:
                continue
            owner = str(getattr(agent, "user_id", "") or "").strip().lower()
            if current_user_id and owner not in {"", current_user_id}:
                continue
            results.append(
                {
                    "capability_type": "subagent",
                    "name": agent.name,
                    "description": agent.description or "",
                    "invoke_via": "subagent",
                    "score": 0.0,
                    "meta": {
                        "agent_id": agent.id,
                        "tools": agent.tools or [],
                        "agent_parameters": agent.agent_parameters or {},
                        "user_id": agent.user_id,
                    },
                }
            )
        return results

    @classmethod
    def _lookup_skills(cls) -> list[dict[str, Any]]:
        tool_manager = ToolManager()
        skill_controller = tool_manager.get_skill_controller()
        if not skill_controller:
            return []
        skills_instance = skill_controller.get_skills_instance()
        if skills_instance is None:
            skill_controller.load_tools()
            skills_instance = skill_controller.get_skills_instance()
        if skills_instance is None:
            return []

        results: list[dict[str, Any]] = []
        for skill in skills_instance.get_all_skills():
            results.append(
                {
                    "capability_type": "skill",
                    "name": skill.name,
                    "description": skill.description or "",
                    "invoke_via": "skill",
                    "score": 0.0,
                    "meta": {
                        "source_path": skill.source_path,
                        "scripts": list(skill.scripts or []),
                        "references": list(skill.references or []),
                        "allowed_tools": list(skill.allowed_tools or []),
                        "metadata": getattr(skill, "metadata", None) or {},
                    },
                }
            )
        return results

    @classmethod
    def _lookup_tools(cls, session, query_terms: list[str]) -> list[dict[str, Any]]:
        query = session.query(ToolInfo).filter(ToolInfo.deleted == 0)
        query = cls._apply_candidate_sql_filter(
            query,
            columns=[ToolInfo.name, ToolInfo.description, ToolInfo.provider, ToolInfo.parameters],
            query_terms=query_terms,
        )
        rows = query.all()
        results: list[dict[str, Any]] = []
        for tool in rows:
            if int(getattr(tool, "deleted", 0) or 0) != 0:
                continue
            results.append(
                {
                    "capability_type": "tool",
                    "name": tool.name,
                    "description": tool.description or "",
                    "invoke_via": "tool",
                    "score": 0.0,
                    "meta": {
                        "provider": tool.provider,
                        "tool_type": tool.type,
                        "parameters": cls._safe_json_loads(tool.parameters),
                        "credentials": tool.credentials,
                        "mcp_server_url": tool.mcp_server_url,
                    },
                }
            )
        return results

    @classmethod
    def _rank_results(
        cls, results: list[dict[str, Any]], *, query: str, query_terms: list[str]
    ) -> list[dict[str, Any]]:
        for item in results:
            if item.get("capability_type") == "skill" and query:
                item["score"] = float(item.get("model_score", 0.0))
            else:
                item["score"] = cls._score_item(item, query=query_terms)
        return sorted(
            results,
            key=lambda item: (
                -float(item.get("score", 0.0)),
                cls._type_priority(item.get("capability_type")),
                item.get("name", ""),
            ),
        )

    @classmethod
    def _score_item(cls, item: dict[str, Any], *, query: list[str]) -> float:
        if not query:
            return float(10 - cls._type_priority(item.get("capability_type")))

        name = cls._to_text(item.get("name"))
        description = cls._to_text(item.get("description"))
        search_blob = cls._build_search_blob(item)
        score = 0.0

        for idx, term in enumerate(query):
            weight = max(1.0, 1.6 - idx * 0.15)
            if name == term:
                score += 100.0 * weight
            elif term in name:
                score += 50.0 * weight
            elif term in description:
                score += 20.0 * weight
            elif term in search_blob:
                score += 12.0 * weight

            for token in term.split():
                if token in name:
                    score += 10.0
                elif token in description:
                    score += 4.0
                elif token in search_blob:
                    score += 2.0

        if score > 0.0:
            score += max(0.0, 5.0 - cls._type_priority(item.get("capability_type")))
        return score

    @classmethod
    def _apply_skill_relevance(cls, skills: list[dict[str, Any]], *, query: str, candidate_terms: list[str]) -> None:
        if not query or not skills:
            return

        preselected = sorted(
            skills,
            key=lambda item: cls._score_item(item, query=candidate_terms),
            reverse=True,
        )[:MAX_SKILL_MODEL_CANDIDATES]
        judgments = cls._judge_skills_with_model(query=query, candidate_terms=candidate_terms, skills=preselected)
        judgment_by_name = {
            str(item.get("name")): item for item in judgments if isinstance(item, dict) and item.get("name")
        }

        for skill in skills:
            matched = judgment_by_name.get(skill.get("name"))
            if not matched:
                skill["model_score"] = 0.0
                continue
            skill["model_score"] = float(matched.get("score", 0.0) or 0.0)
            skill.setdefault("meta", {})["relevance_reason"] = matched.get("reason", "")

    @classmethod
    def _extract_candidate_terms(cls, query: str) -> list[str]:
        if not query:
            return []
        instruction = (
            "You are extracting capability search candidates for a developer tool lookup.\n"
            "Given a user query, return the most useful candidate keywords and short phrases that can match tool names, "
            "agent names, skill names, capability descriptions, script names, provider names, and parameter names.\n"
            "Prefer concise retrieval terms. Include English identifiers when likely. Do not explain.\n"
            'Return strict JSON only in this shape: {"candidate_terms": ["...", "..."]}.\n'
            f"User query: {query}"
        )
        payload = cls._generate_structured_payload(instruction)
        if not isinstance(payload, dict):
            return []
        raw_terms = payload.get("candidate_terms")
        if not isinstance(raw_terms, list):
            return []

        terms: list[str] = []
        seen: set[str] = set()
        for item in raw_terms:
            if not isinstance(item, str):
                continue
            value = " ".join(item.strip().lower().split())
            if not value or value in seen:
                continue
            seen.add(value)
            terms.append(value)
        return terms

    @classmethod
    def _judge_skills_with_model(
        cls, *, query: str, candidate_terms: list[str], skills: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if not query or not skills:
            return []
        skill_candidates = [
            {
                "name": item.get("name"),
                "description": item.get("description"),
            }
            for item in skills
        ]
        instruction = (
            "You are ranking skills for a capability lookup tool.\n"
            "Analyze the user query and candidate retrieval terms step by step internally, then judge how relevant each skill is "
            "based only on the skill name and description.\n"
            "Use a 0-100 score where 100 means strongly suitable and 0 means irrelevant.\n"
            "Return only relevant skills with score > 0.\n"
            'Return strict JSON only in this shape: {"skills": [{"name": "...", "score": 0, "reason": "..."}]}.\n'
            f"User query: {query}\n"
            f"Candidate terms: {json.dumps(candidate_terms, ensure_ascii=False)}\n"
            f"Skills: {json.dumps(skill_candidates, ensure_ascii=False)}"
        )
        payload = cls._generate_structured_payload(instruction)
        if not isinstance(payload, dict):
            return []
        skills_payload = payload.get("skills")
        if not isinstance(skills_payload, list):
            return []
        return [item for item in skills_payload if isinstance(item, dict)]

    @staticmethod
    def _generate_structured_payload(instruction: str) -> dict[str, Any] | list[Any] | None:
        try:
            from runtime.generator.generator import LLMGenerator

            generated = LLMGenerator.generate_structured_output(instruction)
            output = generated.get("output") if isinstance(generated, dict) else None
            if not output:
                return None
            return json.loads(output)
        except Exception:
            return None

    @classmethod
    def _build_terms(cls, query: str, candidate_terms: list[str]) -> list[str]:
        terms: list[str] = []
        seen: set[str] = set()
        for raw in [query, *(candidate_terms or [])]:
            value = cls._to_text(raw)
            if not value or value in seen:
                continue
            seen.add(value)
            terms.append(value)
        return terms

    @classmethod
    def _apply_candidate_sql_filter(cls, query, *, columns: list[Any], query_terms: list[str]):
        if not query_terms:
            return query

        from sqlalchemy import and_, func, or_

        clauses: list[Any] = []
        for term in query_terms:
            tokens = [token for token in term.split() if token]
            if not tokens:
                continue

            term_clauses: list[Any] = []
            for column in columns:
                lowered = func.lower(column)
                term_clauses.append(lowered.ilike(f"%{term}%"))
                if len(tokens) > 1:
                    term_clauses.append(and_(*[lowered.ilike(f"%{token}%") for token in tokens]))
                for token in tokens:
                    term_clauses.append(lowered.ilike(f"%{token}%"))
            if term_clauses:
                clauses.append(or_(*term_clauses))

        if not clauses:
            return query
        return query.filter(or_(*clauses))

    @staticmethod
    def _type_priority(capability_type: Any) -> int:
        if capability_type == "subagent":
            return 0
        if capability_type == "skill":
            return 1
        if capability_type == "tool":
            return 2
        return 9

    @staticmethod
    def _to_text(value: Any) -> str:
        if value is None:
            return ""
        return " ".join(str(value).strip().lower().split())

    @classmethod
    def _build_search_blob(cls, item: dict[str, Any]) -> str:
        parts: list[str] = []
        parts.extend(cls._collect_search_parts(item.get("name")))
        parts.extend(cls._collect_search_parts(item.get("description")))
        parts.extend(cls._collect_search_parts(item.get("meta")))
        return cls._to_text(" ".join(parts))

    @classmethod
    def _collect_search_parts(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, dict):
            parts: list[str] = []
            for key, item in value.items():
                parts.append(str(key))
                parts.extend(cls._collect_search_parts(item))
            return parts
        if isinstance(value, (list, tuple, set)):
            parts: list[str] = []
            for item in value:
                parts.extend(cls._collect_search_parts(item))
            return parts
        if isinstance(value, (str, int, float, bool)):
            return [str(value)]
        return []

    @classmethod
    def _parse_types(cls, value: Any) -> tuple[str, ...]:
        if value is None:
            return DEFAULT_CAPABILITY_TYPES
        if isinstance(value, str):
            raw_values = [value]
        elif isinstance(value, list):
            raw_values = value
        else:
            raise CapabilityLookupError("types must be a string or array")

        items: list[str] = []
        seen: set[str] = set()
        for raw in raw_values:
            if not isinstance(raw, str):
                raise CapabilityLookupError("types entries must be strings")
            item = raw.strip().lower()
            if item not in DEFAULT_CAPABILITY_TYPES:
                raise CapabilityLookupError("types must only contain subagent, skill, or tool")
            if item and item not in seen:
                seen.add(item)
                items.append(item)
        if not items:
            raise CapabilityLookupError("types must not be empty")
        return tuple(items)

    @staticmethod
    def _parse_limit(value: Any) -> int:
        if value is None:
            return 10
        try:
            limit = int(value)
        except (TypeError, ValueError) as exc:
            raise CapabilityLookupError("limit must be an integer") from exc
        if limit < 1:
            raise CapabilityLookupError("limit must be at least 1")
        return min(limit, MAX_LOOKUP_LIMIT)

    @staticmethod
    def _safe_json_loads(value: Any) -> Any:
        if value in (None, ""):
            return None
        if isinstance(value, (dict, list)):
            return value
        if not isinstance(value, str):
            return value
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
