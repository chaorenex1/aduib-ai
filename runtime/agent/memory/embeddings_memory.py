import logging
import re
import time
from typing import Optional

from component.vdb.base_vector import BaseVector
from models import KnowledgeBase
from runtime.agent.agent_type import Message
from runtime.agent.memory.memory_base import MemoryBase
from runtime.entities.document_entities import Document
from runtime.entities.model_entities import ModelType
from runtime.generator.generator import LLMGenerator
from runtime.model_execution.gpt_tokenizer import GPTTokenizer
from runtime.model_manager import ModelManager
from runtime.rag.clean.clean_processor import CleanProcessor
from runtime.rag.embeddings.cache_embeddings import CacheEmbeddings
from runtime.rag.embeddings.embeddings import Embeddings
from runtime.rag.rag_config import AUTOMATIC_RULES
from runtime.rag.splitter.text_splitter import RecursiveTextSplitter

logger = logging.getLogger(__name__)


class LongTermEmbeddingsMemory(MemoryBase):
    def __init__(self, agent_id: Optional[str] = None,chunk_size: int = 500, chunk_overlap: int = 50,top_k: int = 30, score_threshold: float = 0.5):
        self.agent_id = agent_id
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.top_k = top_k
        self.score_threshold = score_threshold
        self.text_splitter = RecursiveTextSplitter(
            chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap
        )
        self.pattern = r"^[\u2000-\u206F\u2E00-\u2E7F\u3000-\u303F!\"#$%&'()*+,./:;<=>?@^_`~]+"
        self.knowledge: KnowledgeBase = KnowledgeBase(rag_type="long-term")
        from component.vdb.vector_factory import Vector
        self.embeddings = self._get_embeddings()
        self.vector: BaseVector = Vector.get_vector_factory("milvus")().init_vector(knowledge=self.knowledge,
                                                                                    attributes=[],
                                                                                    embeddings=self.embeddings)
        self.vector.collection_name = f"agent_{self.agent_id}_memory"

    def delete_memory(self) -> None:
        self.vector.delete_by_metadata_field("agent_id", self.agent_id)

    def add_memory(self, message: Message) -> None:
        token_nums = GPTTokenizer.get_token_nums(message.assistant_message)
        logger.debug(f"Message ID: {message.id}, Token Count: {token_nums}")
        message_timestamp = message.meta["timestamp"] if "timestamp" in message.meta else time.time()
        documents = [Document(content=message.assistant_message,
                              metadata={"message_id": message.id,
                                        "role": "assistant",
                                        "agent_id": self.agent_id,
                                        "user_message": message.user_message,
                                        "timestamp": message_timestamp})]
        all_documents = []
        for document in documents:
            # document clean
            document_text = CleanProcessor.clean(document.content, {"rules": AUTOMATIC_RULES})
            document.content = document_text
            if token_nums > self.chunk_size and document.metadata["role"] == "assistant":
                document.content = LLMGenerator.generate_summary(document.content)
                split_docs = self.text_splitter.split_documents([document])
                for split_doc in split_docs:
                    if split_doc.content.strip():
                        split_doc.content = re.sub(self.pattern, "", split_doc.content).strip()
                        split_doc.metadata = document.metadata
                        all_documents.append(split_doc)
            else:
                all_documents.append(document)
        self.create(texts=all_documents)

    def get_memory(self, query: str) -> list[dict]:
        results = []
        try:
            embed_query = self.embeddings.embed_query(query)
            documents = self.vector.search_by_vector(embed_query, search_type="similarity_score_threshold", top_k=self.top_k,
                                                     score_threshold=self.score_threshold)
            # group by user_message
            user_message_dict = {}
            for doc in documents:
                user_message = doc.metadata.get("user_message", "default")
                if user_message not in user_message_dict:
                    user_message_dict[user_message] = []
                user_message_dict[user_message].append(doc)
            for user_message, docs in user_message_dict.items():
                combined_content = "\n".join([doc.content for doc in docs])
                combined_timestamp = max(doc.metadata.get("timestamp", 0) for doc in docs)
                results.append({"user_message": user_message, "assistant_message": combined_content,
                                "timestamp": combined_timestamp})
            results = sorted(results, key=lambda x: x["timestamp"], reverse=True)
        except Exception as e:
            logger.error(f"Error retrieving memory: {e}")
        return results

    def _get_embeddings(self) -> Embeddings:
        model_manager = ModelManager()
        embedding_model = model_manager.get_default_model_instance(
            model_type=ModelType.EMBEDDING.to_model_type()
        )
        return CacheEmbeddings(embedding_model)

    def create(self, texts: Optional[list] = None, **kwargs):
        if texts:
            start = time.time()
            logger.info("start embedding %s texts %s", len(texts), start)
            batch_size = 10
            total_batches = len(texts) + batch_size - 1
            for i in range(0, len(texts), batch_size):
                batch = texts[i: i + batch_size]
                batch_start = time.time()
                logger.info("Processing batch %s/%s (%s texts)", i // batch_size + 1, total_batches, len(batch))
                batch_embeddings = self.embeddings.embed_documents([document.content for document in batch])
                logger.info("Embedding batch %s/%s took %s s", i // batch_size + 1, total_batches,
                            time.time() - batch_start)
                self.vector.save(texts=batch, embeddings=batch_embeddings, **kwargs)
            logger.info("Embedding %s texts took %s s", len(texts), time.time() - start)
