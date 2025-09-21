import json
import logging
import time

from component.graph.base_graph import GraphManager
from runtime.agent.agent_type import Message
from runtime.agent.clean.triple_clean import TripleCleaner
from runtime.agent.memory.memory_base import MemoryBase
from runtime.generator.generator import LLMGenerator

logger = logging.getLogger(__name__)


class LongTermGraphMemory(MemoryBase):

    def __init__(self):
        self.graph_manager = GraphManager()

    def add_memory(self, message: Message) -> None:
        # 创建消息节点
        message_id = message.id
        message_language = message.meta["language"] if "language" in message.meta else "zh"
        message_timestamp = message.meta["timestamp"] if "timestamp" in message.meta else time.time()
        self.graph_manager.create_node("Message", {"id": message.id, "user_message": message.user_message,
                                                   "timestamp": message_timestamp,
                                                   "language": message_language})
        # 上下文串联
        if message.prev_message_id:
            self.graph_manager.create_relationship(message.prev_message_id, message_id, "NEXT", {})

        try:
            # 关联三元组
            triples = json.loads(LLMGenerator.generate_triples(message.assistant_message))
            if triples:
                # convert dict to list of tuples
                triple_tuples = TripleCleaner(doc_lang=message_language).deduplicate(
                    triples=[(t['subject'], t['relation'], t['object']) for t in triples])
                for triple in triple_tuples:
                    subject_id = "Entity_" + triple[0]
                    object_id = "Entity_" + triple[2]
                    # 创建实体节点
                    self.graph_manager.create_node("Entity", {"id": subject_id, "name": triple[0]})
                    self.graph_manager.create_node("Entity", {"id": object_id, "name": triple[2]})
                    # 创建关系节点
                    self.graph_manager.create_relationship(subject_id, object_id, triple[1], {"message_id": message.id})
                    self.graph_manager.create_relationship(message_id, subject_id, "HAS_TRIPLE", {})
                    self.graph_manager.create_relationship(message_id, object_id, "HAS_TRIPLE", {})
        except Exception as e:

            logger.error(f"Error generating triples: {e}")

    def get_memory(self, query: str) -> list[dict]:
        cypher = f"""
        MATCH (m:Message {{id: '{query}' }})-[:NEXT*0..20]->->(related)
    OPTIONAL MATCH (related)-[:HAS_TRIPLE]->(entity:Entity)
    OPTIONAL MATCH (subject)-[rel]->(object)
    WHERE (subject = entity OR object = entity)
    RETURN 
        related.id AS message_id,
        related.user_message AS user_message,
        collect(DISTINCT {{
            subject: subject.name,
            relation: type(rel),
            object: object.name
        }}) AS triples
    ORDER BY related.timestamp ASC
    """
        results = self.graph_manager.query(cypher)
        return results

    def delete_memory(self) -> None:
        self.graph_manager.delete_node("User")
        self.graph_manager.delete_node("Assistant")
        self.graph_manager.delete_node("Message")
        self.graph_manager.delete_node("Entity")
        self.graph_manager.delete_relationship("NEXT")
        self.graph_manager.delete_relationship("SENT")
        self.graph_manager.delete_relationship("REPLIED")
        self.graph_manager.delete_relationship("HAS_TRIPLE")
