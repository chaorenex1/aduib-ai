from __future__ import annotations

from runtime.memory.base.contracts import MemoryWritePipelineContext, PreparedExtractContext
from runtime.memory.prepare_context.candidate_discovery import CandidateDiscoveryLoop as _CandidateDiscoveryLoop
from runtime.memory.prepare_context.common import dump_prefetched_context
from runtime.memory.prepare_context.prefetch import StaticPrefetchBuilder
from runtime.memory.prepare_context.source_material import SourceMaterialNormalizer


def prepare_extract_context(context: MemoryWritePipelineContext) -> dict:
    normalized = SourceMaterialNormalizer(context).normalize()
    static_prefetch = StaticPrefetchBuilder(
        user_id=normalized.user_id,
        agent_id=normalized.agent_id,
    ).build()
    candidate_memories = _CandidateDiscoveryLoop(
        source=normalized,
        static_context=static_prefetch,
    ).run()
    prefetched_context = static_prefetch.model_copy(update={"candidate_memories": candidate_memories})
    prefetched_payload = dump_prefetched_context(prefetched_context)

    prepared = PreparedExtractContext(
        task_id=context.task_id,
        phase=context.phase,
        source_kind=normalized.source_kind,
        source_hash=normalized.source_hash,
        source_ref=context.source_ref,
        archive_ref=context.archive_ref,
        user_id=normalized.user_id or context.user_id,
        agent_id=normalized.agent_id or context.agent_id,
        project_id=normalized.project_id or context.project_id,
        language=normalized.language,
        messages=normalized.messages,
        text_blocks=normalized.text_blocks,
        prefetched_context=prefetched_payload,
        stats={
            "message_count": len(normalized.messages),
            "text_block_count": len(normalized.text_blocks),
            "prefetched_directory_count": len(prefetched_context.directory_views),
            "prefetched_file_count": len(prefetched_context.file_reads),
            "prefetched_search_count": len(prefetched_context.search_results),
            "prefetched_branch_summary_count": len(prefetched_context.branch_summaries),
            "prefetched_candidate_memory_count": len(prefetched_context.candidate_memories),
            "prefetched_tree_root_count": len(prefetched_context.directory_tree.roots),
        },
        conversation_snapshot=normalized.conversation_snapshot,
        session_snapshot=normalized.session_snapshot,
        archived_snapshot=normalized.archived_snapshot,
    )
    return prepared.model_dump(mode="python", exclude_none=True)
