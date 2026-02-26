"""
EntityExtractor - 从文本中提取实体，适配新的 Entity 结构。

集成现有的 LLMGenerator 和 TripleCleaner 功能，将三元组转换为新的统一记忆架构格式。
"""

from __future__ import annotations

import hashlib
import json
import logging

from runtime.memory.types.base import Entity, EntityType, Relation

logger = logging.getLogger(__name__)


class EntityExtractor:
    """从文本中提取实体，适配新的 Entity 结构。"""

    def __init__(
        self,
        language: str = "zh",
        use_llm: bool = True,
    ) -> None:
        """
        Args:
            language: 文档语言 (zh/en)
            use_llm: 是否使用 LLM 提取 (False = 仅规则匹配，用于测试)
        """
        self._language = language
        self._use_llm = use_llm

    async def extract_from_text(self, text: str) -> list[tuple[Entity, Relation, Entity]]:
        """从文本提取实体和关系三元组。

        Args:
            text: 要处理的文本

        Returns:
            list of (subject_entity, relation, object_entity) tuples
        """
        if not self._use_llm:
            # 不使用LLM时返回空列表
            return []

        try:
            # 懒导入以避免导入错误
            from runtime.generator.generator import LLMGenerator
            from runtime.agent.clean.triple_clean import TripleCleaner

            # 1. 使用LLM提取三元组
            triples_json = LLMGenerator.generate_triples(text)
            triples_data = json.loads(triples_json)

            # 2. 转换为元组格式并清理
            raw_triples = [
                (t["subject"], t["relation"], t["object"])
                for t in triples_data
            ]

            cleaner = TripleCleaner(doc_lang=self._language)
            cleaned_triples = cleaner.deduplicate(triples=raw_triples)

            # 3. 转换为Entity和Relation对象
            return self._triples_to_entities_and_relations(cleaned_triples)

        except Exception as e:
            logger.error(f"三元组提取失败: {e}")
            return []

    def _triples_to_entities_and_relations(
        self,
        triples: list[tuple[str, str, str]],
    ) -> list[tuple[Entity, Relation, Entity]]:
        """Convert raw string triples to typed Entity/Relation objects."""
        result = []

        for subject_name, relation_type, object_name in triples:
            # 生成确定性的实体ID
            subject_id = self._generate_entity_id(subject_name)
            object_id = self._generate_entity_id(object_name)

            # 创建实体
            subject_entity = Entity(
                id=subject_id,
                name=subject_name,
                type=EntityType.CONCEPT,
                properties={}
            )

            object_entity = Entity(
                id=object_id,
                name=object_name,
                type=EntityType.CONCEPT,
                properties={}
            )

            # 创建关系
            relation = Relation(
                source_id=subject_id,
                target_id=object_id,
                type=relation_type,
                properties={},
                weight=1.0
            )

            result.append((subject_entity, relation, object_entity))

        return result

    def _generate_entity_id(self, name: str) -> str:
        """生成实体的确定性ID。"""
        # 使用名称的哈希来生成确定性ID
        name_hash = hashlib.md5(name.encode('utf-8')).hexdigest()[:8]
        return f"entity_{name_hash}"