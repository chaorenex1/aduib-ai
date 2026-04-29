from __future__ import annotations

from configs import config

from .find_index import MemoryFindIndex
from .find_rerank import MemoryFindReranker
from .find_types import (
    FindCandidate,
    FindRequest,
    L0VectorHit,
    L1BranchHit,
    MemoryFindRequestDTO,
    MemoryFindResponseDTO,
    MemoryFindResultItemDTO,
)


class MemoryFindRuntime:
    @classmethod
    def find_for_current_user(cls, user_id: str, payload: MemoryFindRequestDTO) -> MemoryFindResponseDTO:
        request = FindRequest(
            query=cls._normalize_query(payload.query),
            include_types=cls._normalize_include_types(payload.include_types),
            top_k=payload.top_k,
            score_threshold=payload.score_threshold,
        )
        l0_hits = cls._retrieve_l0_hits(user_id=user_id, request=request)
        expandable_l0_hits = cls._select_l0_for_l1_expansion(hits=l0_hits, request=request)
        l1_hits = cls._load_branch_l1_hits(
            user_id=user_id,
            l0_hits=expandable_l0_hits,
            include_types=request.include_types,
        )
        candidates = cls._merge_candidates(l0_hits=l0_hits, l1_hits=l1_hits)
        reranked = cls._rerank_candidates(query=request.query, candidates=candidates, top_k=request.top_k)
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

    @classmethod
    def _retrieve_l0_hits(cls, user_id: str, request: FindRequest) -> list[L0VectorHit]:
        return MemoryFindIndex.search_l0(
            user_id=user_id,
            query=request.query,
            include_types=request.include_types,
            top_k=config.MEMORY_FIND_L0_INITIAL_TOP_K,
        )

    @staticmethod
    def _select_l0_for_l1_expansion(hits: list[L0VectorHit], request: FindRequest) -> list[L0VectorHit]:
        _ = request
        return [item for item in hits if item.score < config.MEMORY_FIND_L0_EXPAND_TO_L1_THRESHOLD]

    @classmethod
    def _load_branch_l1_hits(
        cls,
        user_id: str,
        l0_hits: list[L0VectorHit],
        include_types: list[str],
    ) -> list[L1BranchHit]:
        if not l0_hits:
            return []
        branch_scores: dict[str, float] = {}
        for item in l0_hits:
            branch_scores[item.branch_path] = max(item.score, branch_scores.get(item.branch_path, 0.0))
        l1_hits = MemoryFindIndex.load_l1_by_branch_paths(
            user_id=user_id,
            branch_paths=list(branch_scores),
            include_types=include_types,
        )
        enriched: list[L1BranchHit] = []
        for item in l1_hits:
            enriched.append(
                item.model_copy(update={"source_l0_score": branch_scores.get(item.branch_path, item.source_l0_score)})
            )
        return enriched

    @staticmethod
    def _merge_candidates(l0_hits: list[L0VectorHit], l1_hits: list[L1BranchHit]) -> list[FindCandidate]:
        merged: list[FindCandidate] = []
        seen: set[tuple[str, str, str]] = set()
        for item in l0_hits:
            key = (item.branch_path, item.file_path, "l0")
            if key in seen:
                continue
            seen.add(key)
            merged.append(
                FindCandidate(
                    branch_path=item.branch_path,
                    file_path=item.file_path,
                    memory_type=item.memory_type,
                    content=item.content,
                    source_level="l0",
                    vector_score=item.score,
                    updated_at=item.updated_at,
                    tags=item.tags,
                )
            )
        for item in l1_hits:
            key = (item.branch_path, item.file_path, "l1")
            if key in seen:
                continue
            seen.add(key)
            merged.append(
                FindCandidate(
                    branch_path=item.branch_path,
                    file_path=item.file_path,
                    memory_type=item.memory_type,
                    content=item.content,
                    source_level="l1",
                    vector_score=item.source_l0_score,
                    updated_at=item.updated_at,
                    tags=item.tags,
                )
            )
        return merged

    @staticmethod
    def _rerank_candidates(query: str, candidates: list[FindCandidate], top_k: int) -> list[FindCandidate]:
        return MemoryFindReranker.rerank(query=query, candidates=candidates, top_k=top_k)

    @staticmethod
    def _filter_final_candidates(candidates: list[FindCandidate], score_threshold: float) -> list[FindCandidate]:
        filtered: list[FindCandidate] = []
        for item in candidates:
            final_score = item.final_score if item.final_score is not None else item.vector_score
            if final_score >= score_threshold:
                filtered.append(item.model_copy(update={"final_score": final_score}))
        return filtered

    @classmethod
    def _collapse_same_branch(cls, candidates: list[FindCandidate]) -> list[FindCandidate]:
        return cls._dedupe_by_branch_keep_best(candidates)

    @staticmethod
    def _dedupe_by_branch_keep_best(candidates: list[FindCandidate]) -> list[FindCandidate]:
        best_by_branch: dict[str, FindCandidate] = {}
        for item in candidates:
            current = best_by_branch.get(item.branch_path)
            score = item.final_score if item.final_score is not None else item.vector_score
            if current is None:
                best_by_branch[item.branch_path] = item.model_copy(update={"final_score": score})
                continue
            current_score = current.final_score if current.final_score is not None else current.vector_score
            if score > current_score:
                best_by_branch[item.branch_path] = item.model_copy(update={"final_score": score})
        return sorted(
            best_by_branch.values(),
            key=lambda item: (-(item.final_score or item.vector_score), item.branch_path, item.file_path),
        )

    @classmethod
    def _to_response(cls, query: str, candidates: list[FindCandidate]) -> MemoryFindResponseDTO:
        return MemoryFindResponseDTO(
            query=query,
            results=[
                MemoryFindResultItemDTO(
                    abstract=item.content,
                    score=item.final_score if item.final_score is not None else item.vector_score,
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
