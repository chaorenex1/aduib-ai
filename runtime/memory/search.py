from __future__ import annotations

import json
import logging

from configs import config
from runtime.entities import ChatCompletionRequest
from runtime.memory.find_index import MemoryFindIndex
from runtime.model_manager import ModelManager

from .search_l2 import MemorySearchL2Reader
from .search_prompt import MemorySearchPromptBuilder
from .search_rerank import MemorySearchReranker
from .search_types import (
    L0L1Hit,
    L2Candidate,
    L2ReadResult,
    MemorySearchRequestDTO,
    MemorySearchResponseDTO,
    MemorySearchResultItemDTO,
    SearchCandidate,
    SearchPlan,
    SearchRequest,
)

logger = logging.getLogger(__name__)


class MemorySearchRuntime:
    @classmethod
    def search_for_current_user(cls, user_id: str, payload: MemorySearchRequestDTO) -> MemorySearchResponseDTO:
        request = SearchRequest(
            query=cls._normalize_query(payload.query),
            session=payload.session,
            include_types=cls._normalize_include_types(payload.include_types),
            top_k=payload.top_k,
            score_threshold=payload.score_threshold,
        )
        session_text = cls._serialize_session(request.session)
        l0l1_hits = cls._retrieve_l0_l1_candidates(user_id=user_id, request=request)
        plan = cls._plan_search(
            query=request.query,
            session_text=session_text,
            hits=l0l1_hits,
            include_types=request.include_types,
            top_k=request.top_k,
        )
        branch_paths = cls._select_branch_paths_for_l2(plan=plan, hits=l0l1_hits)
        l2_candidates = cls._load_l2_candidates(
            user_id=user_id,
            branch_paths=branch_paths,
            include_types=request.include_types or plan.target_memory_types,
            max_files=plan.max_l2_files,
        )
        l2_reads = cls._read_l2_contents(query=plan.normalized_query or request.query, candidates=l2_candidates)
        candidates = cls._merge_candidates(l0l1_hits=l0l1_hits, l2_reads=l2_reads, plan=plan)
        reranked = cls._rerank_candidates(
            query=plan.normalized_query or request.query,
            candidates=candidates,
            top_k=request.top_k,
        )
        filtered = cls._filter_final_candidates(candidates=reranked, score_threshold=request.score_threshold)
        collapsed = cls._collapse_same_branch(candidates=filtered)[: request.top_k]
        return cls._to_response(query=request.query, candidates=collapsed)

    @staticmethod
    def _normalize_query(query: str) -> str:
        return " ".join(str(query).strip().split())

    @staticmethod
    def _normalize_include_types(include_types: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in include_types:
            value = str(item).strip().lower()
            if not value or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
        return normalized

    @staticmethod
    def _serialize_session(session) -> str:
        return MemorySearchPromptBuilder.serialize_session(session)

    @classmethod
    def _retrieve_l0_l1_candidates(cls, user_id: str, request: SearchRequest) -> list[L0L1Hit]:
        l0_hits = MemoryFindIndex.search_l0(
            user_id=user_id,
            query=request.query,
            include_types=request.include_types,
            top_k=config.MEMORY_SEARCH_L0L1_INITIAL_TOP_K,
        )
        l0_hits = [item for item in l0_hits if item.score >= config.MEMORY_SEARCH_L0L1_MIN_SCORE]
        branch_paths = [item.branch_path for item in l0_hits]
        l1_hits = MemoryFindIndex.load_l1_by_branch_paths(
            user_id=user_id,
            branch_paths=branch_paths,
            include_types=request.include_types,
        )

        hits: list[L0L1Hit] = []
        seen: set[tuple[str, str, str]] = set()
        for item in l0_hits:
            key = (item.branch_path, item.file_path, "l0")
            if key in seen:
                continue
            seen.add(key)
            hits.append(
                L0L1Hit(
                    branch_path=item.branch_path,
                    file_path=item.file_path,
                    memory_type=item.memory_type,
                    memory_level="l0",
                    content=item.content,
                    score=item.score,
                    updated_at=item.updated_at,
                    tags=item.tags,
                )
            )
        branch_score_lookup = {item.branch_path: item.score for item in l0_hits}
        for item in l1_hits:
            key = (item.branch_path, item.file_path, "l1")
            if key in seen:
                continue
            seen.add(key)
            hits.append(
                L0L1Hit(
                    branch_path=item.branch_path,
                    file_path=item.file_path,
                    memory_type=item.memory_type,
                    memory_level="l1",
                    content=item.content,
                    score=branch_score_lookup.get(item.branch_path, item.source_l0_score),
                    updated_at=item.updated_at,
                    tags=item.tags,
                )
            )
        return sorted(hits, key=lambda item: (-item.score, item.branch_path, item.file_path))

    @classmethod
    def _plan_search(
        cls,
        query: str,
        session_text: str,
        hits: list[L0L1Hit],
        include_types: list[str],
        top_k: int,
    ) -> SearchPlan:
        model_manager = ModelManager()
        model_instance = model_manager.get_planner_model_instance() or model_manager.get_default_model_instance("llm")
        if model_instance is None:
            raise RuntimeError("memory search planner model unavailable")

        messages = MemorySearchPromptBuilder.build_messages(
            query=query,
            session=[],
            hits=hits,
            include_types=include_types,
            top_k=top_k,
            session_text=session_text,
        )
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=messages,
            temperature=0.0,
            stream=False,
        )
        try:
            response = model_instance.invoke_llm_sync(prompt_messages=request, user=None)
        except Exception as exc:
            logger.warning("memory search planner invocation failed: %s", exc)
            raise RuntimeError("memory search planner invocation failed") from exc

        raw_text = str(response.message.content or "").strip()
        plan = cls._parse_search_plan(raw_text)
        return plan.model_copy(
            update={
                "normalized_query": plan.normalized_query or query,
                "max_l2_files": min(
                    max(plan.max_l2_files or 1, 1),
                    config.MEMORY_SEARCH_MAX_L2_FILES_PER_BRANCH,
                ),
            }
        )

    @classmethod
    def _parse_search_plan(cls, raw_text: str) -> SearchPlan:
        payload = cls._load_json_payload(raw_text)
        return SearchPlan.model_validate(
            {
                "normalized_query": str(payload.get("normalized_query") or "").strip(),
                "intent": str(payload.get("intent") or "").strip(),
                "query_rewrites": cls._normalize_str_list(payload.get("query_rewrites") or []),
                "target_memory_types": cls._normalize_include_types(payload.get("target_memory_types") or []),
                "selected_branch_paths": cls._normalize_str_list(payload.get("selected_branch_paths") or []),
                "expand_l2": bool(payload.get("expand_l2")),
                "max_l2_files": int(payload.get("max_l2_files") or config.MEMORY_SEARCH_MAX_L2_FILES_PER_BRANCH),
            }
        )

    @staticmethod
    def _load_json_payload(raw_text: str) -> dict[str, object]:
        text = str(raw_text or "").strip()
        if not text:
            raise ValueError("memory search plan output is empty")
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].strip() == "```":
                text = "\n".join(lines[1:-1]).strip()
                if text.lower().startswith("json"):
                    text = text[4:].strip()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("memory search plan output is not a JSON object") from exc
        if isinstance(payload, dict):
            return payload
        raise ValueError("memory search plan output is not a JSON object")

    @staticmethod
    def _normalize_str_list(values: list[object]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in values:
            value = str(item or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
        return normalized

    @classmethod
    def _select_branch_paths_for_l2(cls, plan: SearchPlan, hits: list[L0L1Hit]) -> list[str]:
        if not plan.expand_l2:
            return []

        hit_branch_paths = [item.branch_path for item in hits]
        allowed_branches = set(hit_branch_paths)
        selected = [item for item in plan.selected_branch_paths if item in allowed_branches]
        if not selected:
            return []

        deduped: list[str] = []
        seen: set[str] = set()
        for branch_path in selected:
            if branch_path in seen:
                continue
            seen.add(branch_path)
            deduped.append(branch_path)
        return deduped[: config.MEMORY_SEARCH_MAX_L2_BRANCHES]

    @staticmethod
    def _load_l2_candidates(
        user_id: str,
        branch_paths: list[str],
        include_types: list[str],
        max_files: int,
    ) -> list[L2Candidate]:
        return MemorySearchL2Reader.list_l2_candidates(
            user_id=user_id,
            branch_paths=branch_paths,
            include_types=include_types,
            max_files=max_files,
        )

    @staticmethod
    def _read_l2_contents(query: str, candidates: list[L2Candidate]) -> list[L2ReadResult]:
        return MemorySearchL2Reader.read_candidates(query=query, candidates=candidates)

    @classmethod
    def _merge_candidates(
        cls,
        l0l1_hits: list[L0L1Hit],
        l2_reads: list[L2ReadResult],
        plan: SearchPlan,
    ) -> list[SearchCandidate]:
        target_types = set(plan.target_memory_types)
        merged: list[SearchCandidate] = []
        for item in l0l1_hits:
            merged.append(
                SearchCandidate(
                    branch_path=item.branch_path,
                    file_path=item.file_path,
                    memory_type=item.memory_type,
                    source_level=item.memory_level,
                    content=item.content,
                    abstract=item.content,
                    vector_score=item.score,
                    updated_at=item.updated_at,
                    tags=item.tags,
                )
            )
        for item in l2_reads:
            merged.append(
                SearchCandidate(
                    branch_path=item.branch_path,
                    file_path=item.file_path,
                    memory_type=item.memory_type,
                    source_level="l2",
                    content=item.content,
                    abstract=item.abstract,
                    vector_score=None,
                    updated_at=item.updated_at,
                    tags=item.tags,
                )
            )

        if not target_types:
            return merged
        filtered = [item for item in merged if item.memory_type in target_types]
        return filtered or merged

    @staticmethod
    def _rerank_candidates(query: str, candidates: list[SearchCandidate], top_k: int) -> list[SearchCandidate]:
        return MemorySearchReranker.rerank(query=query, candidates=candidates, top_k=top_k)

    @staticmethod
    def _filter_final_candidates(candidates: list[SearchCandidate], score_threshold: float) -> list[SearchCandidate]:
        filtered: list[SearchCandidate] = []
        for item in candidates:
            final_score = item.final_score
            if final_score is None:
                final_score = item.vector_score if item.vector_score is not None else 0.0
            if final_score >= score_threshold:
                filtered.append(item.model_copy(update={"final_score": final_score}))
        return filtered

    @classmethod
    def _collapse_same_branch(cls, candidates: list[SearchCandidate]) -> list[SearchCandidate]:
        return cls._dedupe_by_branch_keep_best(candidates)

    @staticmethod
    def _dedupe_by_branch_keep_best(candidates: list[SearchCandidate]) -> list[SearchCandidate]:
        best_by_branch: dict[str, SearchCandidate] = {}
        for item in candidates:
            score = item.final_score
            if score is None:
                score = item.vector_score if item.vector_score is not None else 0.0
            current = best_by_branch.get(item.branch_path)
            if current is None:
                best_by_branch[item.branch_path] = item.model_copy(update={"final_score": score})
                continue
            current_score = current.final_score
            if current_score is None:
                current_score = current.vector_score if current.vector_score is not None else 0.0
            if score > current_score:
                best_by_branch[item.branch_path] = item.model_copy(update={"final_score": score})
        return sorted(
            best_by_branch.values(),
            key=lambda item: (-(item.final_score or item.vector_score or 0.0), item.branch_path, item.file_path),
        )

    @classmethod
    def _to_response(cls, query: str, candidates: list[SearchCandidate]) -> MemorySearchResponseDTO:
        return MemorySearchResponseDTO(
            query=query,
            results=[
                MemorySearchResultItemDTO(
                    abstract=item.abstract,
                    score=item.final_score if item.final_score is not None else (item.vector_score or 0.0),
                    memory_type=item.memory_type,
                    metadata=cls._minimal_metadata(tags=item.tags, updated_at=item.updated_at),
                )
                for item in candidates
            ],
        )

    @staticmethod
    def _minimal_metadata(tags: list[str], updated_at: str | None) -> dict[str, object]:
        metadata: dict[str, object] = {"tags": list(tags)}
        if updated_at is not None:
            metadata["updated_at"] = updated_at
        return metadata
