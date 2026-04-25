from __future__ import annotations

import json
import logging
from pathlib import Path

from component.storage.base_storage import storage_manager
from runtime.entities.llm_entities import ChatCompletionRequest
from runtime.entities.message_entities import SystemPromptMessage, UserPromptMessage
from runtime.memory.committed_tree import CommittedMemoryTree
from runtime.memory.prepare_context.common import (
    CANDIDATE_DISCOVERY_ACTION_SCHEMA,
    CANDIDATE_FILE_MAX_CHARS,
    MAX_CANDIDATE_READS,
    PATH_SEARCH_MAX_RESULTS,
    SEARCH_QUERY_MAX_CHARS,
    build_search_query,
    candidate_search_roots,
    classify_branch_scope,
    is_candidate_memory_path,
    load_json_payload,
    summarize_candidate_content,
    to_scoped_storage_path,
    unique_preserving_order,
)
from runtime.memory.prepare_context.types import (
    CandidateDiscoveryAction,
    CandidateDiscoveryWorkingState,
    CandidateMemoryRecord,
    CandidatePathMatch,
    CandidateSearchQuery,
    NormalizedSourceMaterial,
    PreparedPrefetchContext,
    SearchResultRecord,
)
from runtime.model_manager import ModelManager

logger = logging.getLogger(__name__)


class CandidateDiscoveryLoop:
    MAX_TURNS = 5

    def __init__(self, *, source: NormalizedSourceMaterial, static_context: PreparedPrefetchContext) -> None:
        self.source = source
        self.static_context = static_context

    def run(self) -> list[CandidateMemoryRecord]:
        state = CandidateDiscoveryWorkingState(source=self.source, static_context=self.static_context)
        for _turn in range(self.MAX_TURNS):
            action = self._next_action(state)
            if action.action in {"finalize", "stop_noop"}:
                state.completed = True
                break
            self._apply_action(state, action)

        self._sync_static_context(state)
        return list(state.candidate_memories)

    def _next_action(self, state: CandidateDiscoveryWorkingState) -> CandidateDiscoveryAction:
        query = build_search_query(state.source.text_blocks)
        roots = candidate_search_roots(user_id=state.source.user_id, agent_id=state.source.agent_id)
        if not query or not roots:
            return CandidateDiscoveryAction(
                action="stop_noop", reasoning="No source text or memory branch scope available."
            )
        raw_action = self._invoke_action_model(state=state, default_query=query, roots=roots)
        try:
            action = CandidateDiscoveryAction.model_validate(load_json_payload(raw_action))
        except (TypeError, ValueError) as exc:
            logger.warning("candidate discovery model returned invalid action: %s", exc)
            raise RuntimeError("candidate discovery model returned invalid action") from exc
        return self._sanitize_action(action=action, roots=roots, state=state)

    def _apply_action(self, state: CandidateDiscoveryWorkingState, action: CandidateDiscoveryAction) -> None:
        if action.action == "search_candidate_paths":
            if action.search_query is None:
                state.completed = True
                return
            state.query_history.append(action.search_query)
            state.search_results.extend(self._search_candidate_paths(action.search_query))
            self._sync_static_context(state)
            return

        if action.action != "read_candidate_files":
            state.completed = True
            return

        self._merge_candidate_memories(state, self._read_candidate_files(action.candidate_paths))
        self._attach_candidates_to_search_results(state)
        self._merge_candidate_paths_into_already_read(state)
        self._sync_static_context(state)

    def _invoke_action_model(
        self,
        *,
        state: CandidateDiscoveryWorkingState,
        default_query: str,
        roots: list[str],
    ) -> str:
        try:
            model_manager = ModelManager()
            model_instance = model_manager.get_planner_model_instance() or model_manager.get_default_model_instance(
                "llm"
            )
        except Exception as exc:
            logger.warning("candidate discovery model unavailable: %s", exc)
            raise RuntimeError("candidate discovery model unavailable") from exc
        if model_instance is None:
            raise RuntimeError("candidate discovery model unavailable")

        request_messages = [
            SystemPromptMessage(
                content=(
                    "You drive only the candidate-memory discovery loop for prepare_extract_context. "
                    "Return exactly one JSON object matching the requested action schema. "
                    "Do not request directory tree or L0/L1 summary work. "
                    "Use search_candidate_paths before read_candidate_files; use finalize only after useful "
                    "candidate memories exist; use stop_noop when no useful candidate discovery remains."
                )
            ),
            UserPromptMessage(
                content=json.dumps(
                    {
                        "action_schema": CANDIDATE_DISCOVERY_ACTION_SCHEMA,
                        "source_material": {
                            "source_kind": state.source.source_kind,
                            "text_blocks": state.source.text_blocks,
                            "messages": state.source.messages,
                        },
                        "default_query": default_query,
                        "allowed_path_scopes": roots,
                        "query_history": [
                            item.model_dump(mode="python", exclude_none=True) for item in state.query_history
                        ],
                        "search_results": [
                            item.model_dump(mode="python", exclude_none=True) for item in state.search_results
                        ],
                        "candidate_memories": [
                            item.model_dump(mode="python", exclude_none=True) for item in state.candidate_memories
                        ],
                        "excluded_paths": ["**/overview.md", "**/summary.md", "users/*/project/**"],
                    },
                    ensure_ascii=False,
                )
            ),
        ]
        request = ChatCompletionRequest(
            model=model_instance.model,
            messages=request_messages,
            temperature=0.0,
            stream=False,
        )
        try:
            response = model_instance.invoke_llm_sync(prompt_messages=request, user=self.source.user_id)
        except Exception as exc:
            logger.warning("candidate discovery model invocation failed: %s", exc)
            raise RuntimeError("candidate discovery model unavailable") from exc
        return str(response.message.content or "").strip()

    def _sanitize_action(
        self,
        *,
        action: CandidateDiscoveryAction,
        roots: list[str],
        state: CandidateDiscoveryWorkingState,
    ) -> CandidateDiscoveryAction:
        if action.action == "search_candidate_paths":
            if action.search_query is None:
                return CandidateDiscoveryAction(action="stop_noop", reasoning="Missing search query.")
            allowed_scopes = [path for path in action.search_query.path_scopes if path in roots]
            if not allowed_scopes:
                return CandidateDiscoveryAction(action="stop_noop", reasoning="No valid search scope.")
            query = action.search_query.query.strip()
            if not query:
                return CandidateDiscoveryAction(action="stop_noop", reasoning="Empty search query.")
            return action.model_copy(
                update={
                    "search_query": action.search_query.model_copy(
                        update={"query": query[:SEARCH_QUERY_MAX_CHARS], "path_scopes": allowed_scopes}
                    )
                }
            )
        if action.action == "read_candidate_files":
            candidate_paths = self._sanitize_candidate_paths(
                candidate_paths=action.candidate_paths,
                roots=roots,
                already_read={
                    *self.static_context.already_read_paths,
                    *(item.file_path for item in state.candidate_memories),
                },
            )
            if not candidate_paths:
                return CandidateDiscoveryAction(action="stop_noop", reasoning="No valid candidate paths to read.")
            return action.model_copy(update={"candidate_paths": candidate_paths})
        return action

    def _search_candidate_paths(self, search_query: CandidateSearchQuery) -> list[SearchResultRecord]:
        results: list[SearchResultRecord] = []
        for path_scope in search_query.path_scopes:
            raw_result = CommittedMemoryTree.search_paths(
                query=search_query.query,
                path=path_scope,
                max_results=PATH_SEARCH_MAX_RESULTS,
            )
            matches = [
                CandidatePathMatch(file_path=str(item.get("path") or ""), score=float(item.get("score") or 0.0))
                for item in raw_result.get("matches") or []
                if is_candidate_memory_path(str(item.get("path") or ""))
            ]
            results.append(
                SearchResultRecord(
                    query=str(raw_result.get("query") or search_query.query),
                    path=str(raw_result.get("path") or path_scope),
                    matches=matches,
                    total=len(matches),
                    truncated=bool(raw_result.get("truncated")),
                    committed_view=bool(raw_result.get("committed_view", True)),
                )
            )
        return results

    def _read_candidate_files(self, candidate_paths: list[str]) -> list[CandidateMemoryRecord]:
        candidates: list[CandidateMemoryRecord] = []
        for file_path in unique_preserving_order(candidate_paths):
            if not is_candidate_memory_path(file_path) or not storage_manager.exists(to_scoped_storage_path(file_path)):
                continue
            raw_read = CommittedMemoryTree.read_file(
                path=file_path,
                max_chars=CANDIDATE_FILE_MAX_CHARS,
                include_metadata=False,
            )
            branch_path = file_path.rsplit("/", 1)[0]
            _scope_type, memory_type = classify_branch_scope(branch_path)
            candidates.append(
                CandidateMemoryRecord(
                    title=Path(file_path).stem,
                    file_path=file_path,
                    branch_path=branch_path,
                    memory_type=memory_type,
                    match_source="path_search",
                    match_reason="query terms matched the file path or title",
                    content_summary=summarize_candidate_content(str(raw_read.get("content") or "")),
                )
            )
        return candidates

    def _sanitize_candidate_paths(
        self,
        *,
        candidate_paths: list[str],
        roots: list[str],
        already_read: set[str],
    ) -> list[str]:
        normalized_paths: list[str] = []
        for file_path in unique_preserving_order(candidate_paths):
            normalized_path = str(file_path or "").strip().strip("/")
            if normalized_path in already_read:
                continue
            if not is_candidate_memory_path(normalized_path):
                continue
            if not any(normalized_path.startswith(f"{root}/") for root in roots):
                continue
            normalized_paths.append(normalized_path)
            if len(normalized_paths) >= MAX_CANDIDATE_READS:
                break
        return normalized_paths

    def _merge_candidate_memories(
        self,
        state: CandidateDiscoveryWorkingState,
        candidates: list[CandidateMemoryRecord],
    ) -> None:
        existing_candidate_paths = {item.file_path for item in state.candidate_memories}
        for candidate in candidates:
            if candidate.file_path in existing_candidate_paths:
                continue
            state.candidate_memories.append(candidate)
            existing_candidate_paths.add(candidate.file_path)

    def _attach_candidates_to_search_results(self, state: CandidateDiscoveryWorkingState) -> None:
        candidates_by_path = {item.file_path: item for item in state.candidate_memories}
        updated_results: list[SearchResultRecord] = []
        for result in state.search_results:
            updated_results.append(
                result.model_copy(
                    update={
                        "candidate_memories": [
                            candidates_by_path[match.file_path]
                            for match in result.matches
                            if match.file_path in candidates_by_path
                        ]
                    }
                )
            )
        state.search_results = updated_results

    def _merge_candidate_paths_into_already_read(self, state: CandidateDiscoveryWorkingState) -> None:
        already_read = {*self.static_context.already_read_paths}
        already_read.update(item.file_path for item in state.candidate_memories)
        self.static_context.already_read_paths = sorted(already_read)

    def _sync_static_context(self, state: CandidateDiscoveryWorkingState) -> None:
        self.static_context.search_results = list(state.search_results)
        self.static_context.candidate_memories = list(state.candidate_memories)
