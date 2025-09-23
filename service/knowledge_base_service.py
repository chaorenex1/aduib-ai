import hashlib

from models import KnowledgeBase, get_db
from models.document import KnowledgeDocument
from runtime.rag.rag_type import RagType


class KnowledgeBaseService:

    @classmethod
    def create_knowledge_base(cls, name: str, rag_type: str, default: int) -> KnowledgeBase:
        with get_db() as session:
            kb = KnowledgeBase(
                name=name,
                default_base=default,
                rag_type=rag_type,
                data_process_rule={
                    "mode": "custom",
                    "rules": {
                        "pre_processing_rules": [
                            {"id": "remove_extra_spaces", "enabled": True},
                            {"id": "remove_urls_emails", "enabled": False},
                        ],
                        "segmentation": {"delimiter": "\n,.,。", "max_tokens": 500, "chunk_overlap": 50},
                    }
                },
                embedding_model="modelscope.cn/Qwen/Qwen3-Embedding-8B-GGUF:Q8_0",
                embedding_model_provider="ollama",
                rerank_model="Qwen/Qwen3-Reranker-4B",
                rerank_model_provider="transformer",
                reranking_rule={"score_threshold": 0.8, "top_k": 5},
            )
            session.add(kb)
            session.commit()
            session.refresh(kb)
            return kb

    @classmethod
    async def paragraph_rag_from_web_memo(cls, crawl_text: str, crawl_type: str) -> None:
        """
        Create a knowledge document from web crawl text and store it in the default paragraph knowledge base.
        """
        from service import FileService
        from runtime.rag_manager import RagManager

        file_hash = hashlib.sha256(crawl_text.encode('utf-8')).hexdigest()
        file_name = f"/web_memo/{file_hash}.{crawl_type}"
        file_record = FileService.upload_bytes(file_name, crawl_text.encode('utf-8'))

        from runtime.generator.generator import LLMGenerator
        # name,language = LLMGenerator.generate_conversation_name(crawl_text)
        name, language = "", "chinese"
        with get_db() as session:
            existing_kb = session.query(KnowledgeBase).filter_by(default_base=1,
                                                                 rag_type=RagType.PARAGRAPH).one_or_none()
            if not existing_kb:
                existing_kb = cls.create_knowledge_base("Default Paragraph KB", RagType.PARAGRAPH, 1)

            doc = session.query(KnowledgeDocument).filter_by(
                knowledge_base_id=existing_kb.id,
                file_id=str(file_record.id),
            ).one_or_none()
            if not doc:
                doc = KnowledgeDocument(knowledge_base_id=existing_kb.id,
                                        title=name,
                                        file_id=file_record.id,
                                        doc_language=language,
                                        doc_from="web_memo",
                                        rag_type=RagType.PARAGRAPH,
                                        data_source_type='file',
                                        rag_status="pending", )

                session.add(doc)
                session.commit()
                session.refresh(doc)

        RagManager().run([doc])

    @classmethod
    async def qa_rag_from_conversation_message(cls) -> None:
        """
        Create a knowledge document from web crawl text and store it in the default paragraph knowledge base.
        """
        from runtime.rag_manager import RagManager
        from runtime.generator.generator import LLMGenerator
        # name,language = LLMGenerator.generate_conversation_name(crawl_text)
        name, language = "", "chinese"
        with get_db() as session:
            existing_kb = session.query(KnowledgeBase).filter_by(default_base=1,
                                                                 rag_type=RagType.QA).one_or_none()
            if not existing_kb:
                existing_kb = cls.create_knowledge_base("Default QA KB", RagType.QA, 1)
            doc = KnowledgeDocument(
                knowledge_base_id=existing_kb.id,
                title=name,
                file_id="",
                doc_language=language,
                doc_from="conversation_message",
                rag_type=RagType.QA,
                data_source_type='db_table',
                rag_status="pending",
            )
            session.add(doc)
            session.commit()
            session.refresh(doc)

        RagManager().run([doc])

    @classmethod
    async def retrieve_from_knowledge_base(cls,
                                           rag_type: str,
                                           query: str) -> list[dict]:
        """
        Retrieve relevant documents from the knowledge base using RAG.
        """
        from runtime.rag.rag_processor.rag_processor_factory import RAGProcessorFactory
        rag_processor = RAGProcessorFactory.get_rag_processor(rag_type)
        with get_db() as session:
            existing_kb = session.query(KnowledgeBase).filter_by(default_base=1,
                                                                 rag_type=rag_type).one_or_none()
            if not existing_kb:
                return []
        return rag_processor.retrieve("score_similarity",
                                      query,
                                      existing_kb,
                                      existing_kb.reranking_rule.get("top_k", 10),
                                      existing_kb.reranking_rule.get("score_threshold", 0.8),
                                      {
                                          "reranking_model_name": existing_kb.rerank_model,
                                          "reranking_provider_name": existing_kb.rerank_model_provider
                                      } if existing_kb.rerank_model and existing_kb.rerank_model_provider else {}
                                      )
