from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from models import KnowledgeBase, MemoryBase
from runtime.generator.generator import LLMGenerator
from runtime.memory.retrieval_manager import MemoryRetrievalMixin
from runtime.memory.types import Memory, MemoryTopicSegment, MemoryTopicSegmentProcessed

logger = logging.getLogger(__name__)


class MemoryManager(MemoryRetrievalMixin):
    """统一记忆管理器。"""

    def __init__(
        self,
        user_id: str,
    ) -> None:
        self.user_id = user_id

    @staticmethod
    def _normalize_topic(name: str) -> str:
        """规范化话题名称，用于 intra-batch 去重比较。"""
        return name.strip().lower().replace(" ", "")

    @staticmethod
    def _format_memory_content(
        mem_type: str,
        mem_domain: str,
        topic: str,
        segments: list[str],
        created_at: datetime | None = None,
        operation: str = "create",
        existing_content: str = "",
    ) -> str:
        """通过 LLM 推理将话题内容片段格式化为适合 RAG 检索的记忆文档。"""
        timestamp = ""
        if created_at is not None:
            aware = created_at if created_at.tzinfo else created_at.replace(tzinfo=UTC)
            timestamp = aware.strftime("%Y-%m-%d %H:%M UTC")

        return LLMGenerator.generate_memory_format(
            mem_type=mem_type,
            mem_domain=mem_domain,
            topic=topic,
            segments=segments,
            timestamp=timestamp,
            operation=operation,
            existing_content=existing_content,
        )

    @staticmethod
    def _format_full_memory_content(mem_type: str, mem_domain: str, topic: str, mem_content: str) -> str:
        return "\n".join(
            [
                f"memory_type: {mem_type}",
                f"memory_domain: {mem_domain}",
                f"memory_topic: {topic}",
                "",
                mem_content.strip(),
            ]
        ).strip()

    @staticmethod
    def _sync_memory_tag_associations(session, memory_id: str, tag_ids: list[str]) -> None:
        """同步 MemoryRecord.tags 与 memory_tag_associations，移除陈旧关联。"""
        from models.memory_tags import MemoryTagAssociation, UserCustomTag

        deduplicated_tag_ids = list(dict.fromkeys(tag_ids))
        desired_tag_ids = set(deduplicated_tag_ids)

        existing_associations = (
            session.query(MemoryTagAssociation).filter(MemoryTagAssociation.memory_id == memory_id).all()
        )
        existing_tag_ids = {str(assoc.tag_id) for assoc in existing_associations}

        touched_tag_ids = list(existing_tag_ids | desired_tag_ids)
        tags_by_id: dict[str, UserCustomTag] = {}
        if touched_tag_ids:
            tags = session.query(UserCustomTag).filter(UserCustomTag.id.in_(touched_tag_ids)).all()
            tags_by_id = {str(tag.id): tag for tag in tags}

        for assoc in existing_associations:
            tag_id = str(assoc.tag_id)
            if tag_id in desired_tag_ids:
                continue
            session.delete(assoc)
            tag = tags_by_id.get(tag_id)
            if tag and (tag.usage_count or 0) > 0:
                tag.usage_count -= 1

        for tag_id in deduplicated_tag_ids:
            if tag_id in existing_tag_ids:
                continue
            session.add(
                MemoryTagAssociation(
                    memory_id=memory_id,
                    tag_id=tag_id,
                    assigned_by="",
                )
            )
            tag = tags_by_id.get(tag_id)
            if tag:
                tag.usage_count = (tag.usage_count or 0) + 1

    async def store(self, memory: Memory) -> str:
        """存储记忆。"""
        domain, kb = await self.generate_memory_domain(memory)
        segment_list: list[MemoryTopicSegmentProcessed] = await self.generate_memory_topic(memory, domain, kb)
        tag_list: list[str] = await self.generate_memory_tags(memory, kb)
        mem_ids: list[str] = await self.create_memory(memory, domain, segment_list, tag_list)
        await self.update_memory_graph(memory, mem_ids, domain, segment_list, tag_list)
        return mem_ids[0] if mem_ids else ""

    async def generate_memory_domain(self, memory: Memory) -> tuple[MemoryBase, KnowledgeBase]:
        """根据记忆内容生成领域。"""
        if not memory.summary_enabled:
            classification = LLMGenerator.generate_memory_classification(memory.content)
            domain: str = classification["domain"]
            memory_type: str = classification["type"]
        else:
            domain = memory.domain
            memory_type = memory.type

        from models.engine import get_db

        with get_db() as session:
            existing: MemoryBase = (
                session.query(MemoryBase)
                .filter(MemoryBase.user_id == self.user_id, MemoryBase.domain == domain)
                .first()
            )
            if existing:
                kb: KnowledgeBase = session.query(KnowledgeBase).filter(KnowledgeBase.id == existing.mem_kb_id).first()
                session.expunge(kb)
                return existing, kb
            from service.knowledge_base_service import KnowledgeBaseService

            kb = KnowledgeBaseService.create_knowledge_base(
                f"{self.user_id}_{domain}_kb",
                "paragraph",
                0,
                self.user_id,
                500,
                0,
            )
            new_record = MemoryBase(
                user_id=self.user_id,
                domain=domain,
                type=memory_type,
                mem_kb_id=str(kb.id),
            )
            session.add(new_record)
            session.commit()
            session.refresh(new_record)
        return new_record, kb

    async def generate_memory_topic(
        self, memory: Memory, domain: MemoryBase, kb: KnowledgeBase
    ) -> list[MemoryTopicSegmentProcessed]:
        """根据记忆内容生成话题。"""
        if memory.summary_enabled:
            return [MemoryTopicSegmentProcessed(topic=memory.topic, topic_content_segment=[memory.content])]

        json_schema: str = LLMGenerator.generate_memory_topic(memory.content, MemoryTopicSegment.json_schema())
        topic_segments: list[MemoryTopicSegment] = MemoryTopicSegment.parse_list(json_schema)

        return [
            MemoryTopicSegmentProcessed(
                topic=segment.topic,
                topic_content_segment=segment.topic_content_segment,
            )
            for segment in topic_segments
        ]

    async def generate_memory_tags(self, memory: Memory, kb: KnowledgeBase) -> list[str]:
        """根据记忆内容生成标签。"""
        from configs import config
        from runtime.model_manager import ModelManager
        from runtime.rag.embeddings.cache_embeddings import CacheEmbeddings
        from service.tag_service import TagService

        json_schema: str = LLMGenerator.generate_memory_tags(memory.content)
        raw_tags: list[str] = json.loads(json_schema)

        seen: set[str] = set()
        unique_tags: list[str] = []
        for tag in raw_tags:
            key = tag.strip().lower()
            if key not in seen:
                seen.add(key)
                unique_tags.append(key)

        embedding_model = ModelManager().get_model_instance(
            model_name=kb.embedding_model_provider + "/" + kb.embedding_model
        )
        embeddings = CacheEmbeddings(embedding_model)
        tag_vecs = embeddings.embed_documents(unique_tags)
        result_tags: list[str] = []

        for tag, vec in zip(unique_tags, tag_vecs):
            if vec is None:
                user_custom_tag = TagService.get_or_create(name=tag, user_id=self.user_id)
                result_tags.append(str(user_custom_tag.id))
                continue
            similar = TagService.find_similar(
                vector=vec, user_id=self.user_id, threshold=config.MEMORY_GATE_DUPLICATE_SIMILARITY
            )
            if similar is None:
                user_custom_tag = TagService.get_or_create(name=tag, user_id=self.user_id, vector=vec)
                result_tags.append(str(user_custom_tag.id))
            else:
                result_tags.append(str(similar.id))
                logger.debug(
                    "Tag '%s' similar to '%s' (threshold=%.2f), reusing",
                    tag,
                    similar,
                    config.MEMORY_GATE_DUPLICATE_SIMILARITY,
                )

        return result_tags

    async def create_memory(
        self,
        memory: Memory,
        domain: MemoryBase,
        segment_list: list[MemoryTopicSegmentProcessed],
        tag_list: list[str],
    ) -> list[str]:
        """创建记忆。"""
        from models.engine import get_db
        from models.memory import MemoryRecord
        from service.knowledge_base_service import KnowledgeBaseService

        mem_ids: list[str] = []
        deduplicated_tag_list = list(dict.fromkeys(tag_list))

        for segment in segment_list:
            with get_db() as session:
                existing_record = (
                    session.query(MemoryRecord)
                    .filter(
                        MemoryRecord.user_id == self.user_id,
                        MemoryRecord.domain == domain.domain,
                        MemoryRecord.topic == segment.topic,
                        MemoryRecord.deleted == 0,
                    )
                    .order_by(MemoryRecord.created_at.desc())
                    .first()
                )
                existing_record_id = str(existing_record.id) if existing_record else None
                existing_doc_id = (
                    str(existing_record.kb_doc_id) if existing_record and existing_record.kb_doc_id else None
                )

            existing_content = ""
            operation = "create"
            if existing_doc_id:
                existing_content = KnowledgeBaseService.get_memory_doc_content(existing_doc_id)
                operation = "append"

            formatted = self._format_memory_content(
                mem_type=domain.type,
                mem_domain=domain.domain,
                topic=segment.topic,
                segments=segment.topic_content_segment,
                created_at=memory.created_at,
                operation=operation,
                existing_content=existing_content,
            )
            from utils import inject_frontmatter

            formatted = inject_frontmatter(formatted, source=memory.source, project_id=memory.project_id)
            if existing_doc_id:
                doc_id = KnowledgeBaseService.update_memory_doc(existing_doc_id, formatted, self.user_id)
            else:
                doc_id = KnowledgeBaseService.paragraph_rag_from_memory(
                    formatted,
                    user_id=self.user_id,
                    mem_kb_id=str(domain.mem_kb_id),
                    agent_id=memory.agent_id,
                    project_id=memory.project_id,
                    source=memory.source,
                )

            with get_db() as session:
                if existing_record_id:
                    record: MemoryRecord | None = (
                        session.query(MemoryRecord).filter(MemoryRecord.id == existing_record_id).first()
                    )
                    if record is None:
                        raise ValueError(f"MemoryRecord not found during upsert: {existing_record_id}")
                    action = "Updated"
                else:
                    record = MemoryRecord(
                        user_id=memory.user_id,
                        type=domain.type,
                        memory_base_id=domain.id,
                        domain=domain.domain,
                        source=memory.source,
                        topic=segment.topic,
                        tags=deduplicated_tag_list,
                        kb_doc_id=doc_id,
                    )
                    session.add(record)
                    action = "Created"

                record.memory_base_id = domain.id
                record.user_id = memory.user_id
                record.type = domain.type
                record.domain = domain.domain
                record.topic = segment.topic
                record.tags = deduplicated_tag_list
                record.source = memory.source
                record.kb_doc_id = doc_id

                session.flush()
                session.refresh(record)

                memory_id = str(record.id)
                self._sync_memory_tag_associations(session, memory_id, deduplicated_tag_list)
                session.commit()

            logger.info("%s memory: id=%s, domain=%s, topic=%s", action, memory_id, domain.domain, segment.topic)
            mem_ids.append(memory_id)

        return mem_ids

    async def update_memory_graph(
        self,
        memory: Memory,
        mem_ids: list[str],
        domain: MemoryBase,
        segment_list: list[MemoryTopicSegmentProcessed],
        tag_list: list[str],
    ) -> None:
        """创建记忆图谱：将新记忆写入图谱节点，并与历史记忆建立关联边。"""
        from component.graph.base_graph import GraphManager
        from models.engine import get_db
        from models.memory import MemoryRecord
        from runtime.memory.graph.knowledge_graph import KnowledgeGraphLayer, MemoryRef

        graph_store = GraphManager(graph_name=f"{self.user_id}_memory_graph")
        knowledge_graph = KnowledgeGraphLayer(graph_store=graph_store)

        for memory_id, segment in zip(mem_ids, segment_list):
            await knowledge_graph.add_memory_ref(
                MemoryRef(
                    id=memory_id,
                    memory_type=domain.type,
                    user_id=self.user_id,
                    project_id=memory.project_id,
                    agent_id=memory.agent_id,
                    memory_domain=domain.domain,
                    summary=segment.topic,
                )
            )
        logger.debug("Memory graph: created %d MemoryRef nodes", len(mem_ids))

        if domain.domain == "relationship":
            from runtime.memory.graph.entity_extractor import EntityExtractor
            from runtime.memory.graph.relation_builder import RelationBuilder

            extractor = EntityExtractor()
            builder = RelationBuilder(knowledge_graph)
            for memory_id, segment in zip(mem_ids, segment_list):
                text = "\n".join(segment.topic_content_segment)
                if not text.strip():
                    continue
                entities_added, relations_added = await builder.build_from_text(text, extractor, memory_id=memory_id)
                logger.debug(
                    "Memory graph: entity extraction memory_id=%s, topic=%s, entities=%d, relations=%d",
                    memory_id,
                    segment.topic,
                    entities_added,
                    relations_added,
                )

        for memory_id, segment in zip(mem_ids, segment_list):
            with get_db() as session:
                peers = (
                    session.query(MemoryRecord.id)
                    .filter(
                        MemoryRecord.user_id == self.user_id,
                        MemoryRecord.topic == segment.topic,
                        MemoryRecord.deleted == 0,
                        MemoryRecord.id.notin_(mem_ids),
                    )
                    .limit(20)
                    .all()
                )
            for (peer_id,) in peers:
                await knowledge_graph.link_memory_refs(
                    source_id=memory_id,
                    target_id=str(peer_id),
                    rel_type="SHARES_TOPIC",
                    properties={"topic": segment.topic, "weight": 1.0},
                )
            if peers:
                logger.debug(
                    "Memory graph: linked memory_id=%s to %d topic peers (topic=%s)",
                    memory_id,
                    len(peers),
                    segment.topic,
                )

        if tag_list:
            tag_set = set(tag_list)
            with get_db() as session:
                candidates = (
                    session.query(MemoryRecord)
                    .filter(
                        MemoryRecord.memory_base_id == str(domain.id),
                        MemoryRecord.deleted == 0,
                        MemoryRecord.id.notin_(mem_ids),
                    )
                    .order_by(MemoryRecord.created_at.desc())
                    .limit(50)
                    .all()
                )
                tag_peers: list[tuple[str, set, float]] = []
                for candidate in candidates:
                    peer_tags = set(candidate.tags or [])
                    shared = tag_set & peer_tags
                    if shared:
                        union = tag_set | peer_tags
                        jaccard = len(shared) / len(union)
                        tag_peers.append((str(candidate.id), shared, jaccard))

            for memory_id in mem_ids:
                for peer_id, shared_tags, weight in tag_peers:
                    await knowledge_graph.link_memory_refs(
                        source_id=memory_id,
                        target_id=peer_id,
                        rel_type="SHARES_TAG",
                        properties={"shared_tags": list(shared_tags), "weight": weight},
                    )

            if tag_peers:
                logger.debug(
                    "Memory graph: linked %d new memories to %d tag peers",
                    len(mem_ids),
                    len(tag_peers),
                )

        logger.info(
            "Memory graph updated: user=%s, domain=%s, memories=%d",
            self.user_id,
            domain.domain,
            len(mem_ids),
        )

    def delete_memories_by_agent(self, user_id: str):
        """删除指定 agent_id 相关的记忆（软删除）。"""
        from models.engine import get_db
        from models.memory import MemoryRecord

        with get_db() as session:
            session.query(MemoryRecord).filter(
                MemoryRecord.user_id == user_id,
                MemoryRecord.deleted == 0,
            ).update({MemoryRecord.deleted: 1}, synchronize_session=False)
            session.commit()

        logger.info("Deleted memories for user=%s", user_id)
