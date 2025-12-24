import hashlib
import logging
from typing import Any

from sqlalchemy import select, func, bindparam, desc

from models import KnowledgeBase, get_db, BrowserHistory
from models.document import KnowledgeDocument
from runtime.entities.document_entities import Document
from runtime.rag.rag_type import RagType
from runtime.rag.retrieve.retrieve import RerankMode

logger = logging.getLogger(__name__)


class KnowledgeBaseService:
    @staticmethod
    def _contains_cjk(text: str) -> bool:
        """
        Lightweight detection to determine if the search query includes CJK characters.
        Used to pick the correct tokenizer for browser history retrieval.
        """
        if not text:
            return False
        return any("\u4e00" <= char <= "\u9fff" for char in text)

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
                    },
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

        file_hash = hashlib.sha256(crawl_text.encode("utf-8")).hexdigest()
        file_name = f"/web_memo/{file_hash}.{crawl_type}"
        file_record = FileService.upload_bytes(file_name, crawl_text.encode("utf-8"))

        from runtime.generator.generator import LLMGenerator

        name,language = LLMGenerator.generate_conversation_name(crawl_text)
        # name, language = LLMGenerator.generate_conversation_name(crawl_text), "chinese"
        with get_db() as session:
            existing_kb = (
                session.query(KnowledgeBase).filter_by(default_base=1, rag_type=RagType.PARAGRAPH).one_or_none()
            )
            if not existing_kb:
                existing_kb = cls.create_knowledge_base("Default Paragraph KB", RagType.PARAGRAPH, 1)

            doc = (
                session.query(KnowledgeDocument)
                .filter_by(
                    knowledge_base_id=existing_kb.id,
                    file_id=str(file_record.id),
                )
                .one_or_none()
            )
            if not doc:
                doc = KnowledgeDocument(
                    knowledge_base_id=existing_kb.id,
                    title=name,
                    file_id=file_record.id,
                    doc_language=language,
                    doc_from="web_memo",
                    rag_type=RagType.PARAGRAPH,
                    data_source_type="file",
                    rag_status="pending",
                )

                session.add(doc)
                session.commit()
                session.refresh(doc)

        RagManager().run([doc])

    @classmethod
    async def paragraph_rag_from_blog_content(cls, blog_content: bytes,filename:str) -> None:
        """
        Create a knowledge document from web crawl text and store it in the default paragraph knowledge base.
        """
        from service import FileService
        from runtime.rag_manager import RagManager

        # file_hash = hashlib.sha256(blog_content).hexdigest()
        file_name = f"/blog_content/{filename}"
        file_record = FileService.upload_bytes(file_name, blog_content)

        from runtime.generator.generator import LLMGenerator

        name, language = LLMGenerator.generate_conversation_name(str(blog_content))
        with get_db() as session:
            existing_kb = (
                session.query(KnowledgeBase).filter_by(default_base=1, rag_type=RagType.PARAGRAPH).one_or_none()
            )
            if not existing_kb:
                existing_kb = cls.create_knowledge_base("Default Paragraph KB", RagType.PARAGRAPH, 1)

            doc = (
                session.query(KnowledgeDocument)
                .filter_by(
                    knowledge_base_id=existing_kb.id,
                    file_id=str(file_record.id),
                )
                .one_or_none()
            )
            if not doc:
                doc = KnowledgeDocument(
                    knowledge_base_id=existing_kb.id,
                    title=name,
                    file_id=file_record.id,
                    doc_language=language,
                    doc_from="blog_content",
                    rag_type=RagType.PARAGRAPH,
                    data_source_type="file",
                    rag_status="pending",
                )

                session.add(doc)
                session.commit()
                session.refresh(doc)

                RagManager().run([doc])
            else:
                logger.warning("Document already exists in knowledge base.")
                if doc.rag_status != "completed":
                    RagManager().run([doc])

    @classmethod
    async def qa_rag_from_conversation_message(cls,message_id: str) -> None:
        """
        Create a knowledge document from web crawl text and store it in the default paragraph knowledge base.
        """
        from runtime.rag_manager import RagManager
        from runtime.generator.generator import LLMGenerator

        # name,language = LLMGenerator.generate_conversation_name(crawl_text)
        name, language = "", "chinese"
        with get_db() as session:
            existing_kb = session.query(KnowledgeBase).filter_by(default_base=1, rag_type=RagType.QA).one_or_none()
            if not existing_kb:
                existing_kb = cls.create_knowledge_base("Default QA KB", RagType.QA, 1)
            doc = KnowledgeDocument(
                knowledge_base_id=existing_kb.id,
                title=name,
                file_id="",
                message_id=message_id,
                doc_language=language,
                doc_from="conversation_message",
                rag_type=RagType.QA,
                data_source_type="db_table",
                rag_status="pending",
            )
            session.add(doc)
            session.commit()
            session.refresh(doc)

        RagManager().run([doc])

    @classmethod
    async def retrieve_from_knowledge_base(cls, rag_type: str, query: str) -> list[Document]:
        """
        Retrieve relevant documents from the knowledge base using RAG.
        """
        from runtime.rag.rag_processor.rag_processor_factory import RAGProcessorFactory

        rag_processor = RAGProcessorFactory.get_rag_processor(rag_type)
        with get_db() as session:
            existing_kb = session.query(KnowledgeBase).filter_by(default_base=1, rag_type=rag_type).one_or_none()
            if not existing_kb:
                return []
        return rag_processor.retrieve(
            RerankMode.WEIGHTED_SCORE,
            query,
            existing_kb,
            existing_kb.reranking_rule.get("top_k", 10),
            existing_kb.reranking_rule.get("score_threshold", 0.8),
            {
                "reranking_model_name": existing_kb.rerank_model,
                "reranking_provider_name": existing_kb.rerank_model_provider,
            }
            if existing_kb.rerank_model and existing_kb.rerank_model_provider
            else {},
            {
                "keyword_weight": existing_kb.reranking_rule.get("keyword_weight", 0.2),
                "vector_weight": existing_kb.reranking_rule.get("vector_weight", 0.8),
                "embedding_model_name": existing_kb.embedding_model,
                "embedding_provider_name": existing_kb.embedding_model_provider,
            }
        )

    @classmethod
    async def retrieval_from_browser_history(cls, query, start_time, end_time):
        """
        Retrieve relevant documents from the Browser History.
        """
        use_cjk_tokenizer = cls._contains_cjk(query)
        ts_vector = (
            func.to_jieba_tsvector(BrowserHistory.crawl_content)
            if use_cjk_tokenizer
            else func.to_tsvector("simple", BrowserHistory.crawl_content)
        )
        ts_query = (
            func.to_jieba_tsquery(bindparam("search_query"))
            if use_cjk_tokenizer
            else func.plainto_tsquery("simple", bindparam("search_query"))
        )
        base_rank = func.ts_rank(ts_vector, ts_query)
        density_rank = func.ts_rank_cd(ts_vector, ts_query)
        normalized_rank = func.coalesce(
            base_rank / func.nullif(density_rank, 0),
            base_rank,
        ).label("rank")

        with get_db() as session:
            stmt = (
                select(
                    BrowserHistory.id,
                    BrowserHistory.url,
                    BrowserHistory.crawl_content,
                    BrowserHistory.visit_time,
                    normalized_rank,
                )
                .where(base_rank > 0)
                .order_by(desc("rank"))
            )
            if start_time:
                stmt = stmt.where(BrowserHistory.visit_time >= start_time)
            if end_time:
                stmt = stmt.where(BrowserHistory.visit_time <= end_time)
            stmt = stmt.limit(20)
            logger.debug(stmt)
            res = session.execute(stmt, {"search_query": query})
            results = [(row[0], row[1], row[2], row[3], row[4]) for row in res]
        docs = []
        for record in results:
            if record[4]>=0.6:  # score threshold
                meta = {
                    "id": record[0],
                    "url": record[1],
                    "content": record[2],
                    "visit_time": record[3],
                    "score": record[4],
                }
                docs.append(meta)
        return docs

    @classmethod
    async def retry_failed_paragraph_rag_embeddings(cls):
        """
        Retry failed paragraph RAG embeddings.
        """
        with get_db() as session:
            blog_list: list[KnowledgeDocument] = session.query(KnowledgeDocument).filter(
                KnowledgeDocument.rag_status != 'completed',
                KnowledgeDocument.rag_type == 'paragraph',
                KnowledgeDocument.rag_count < 3,
            ).all()
            for blog in blog_list:
                try:
                    from runtime.rag_manager import RagManager
                    manager = RagManager()
                    blog_ = [blog]
                    manager.clean(blog_)
                    manager.run(blog_)
                    blog.rag_count += 1
                    session.commit()
                except Exception as e:
                    logger.exception(f"Failed to process document ID {blog.id}: {e}")
                    session.rollback()


    @classmethod
    async  def clean_knowledge_documents(cls):
        """
        Clean knowledge documents with failed RAG status exceeding retry limit.
        """
        with get_db() as session:
            docs_to_delete: list[KnowledgeDocument] = session.query(KnowledgeDocument).filter(
                KnowledgeDocument.rag_status != 'completed',
                KnowledgeDocument.rag_count >= 3,
            ).all()
            from runtime.rag_manager import RagManager
            try:
                RagManager().clean(docs_to_delete)
                for doc in docs_to_delete:
                    session.delete(doc)
                session.commit()
            except Exception as e:
                logger.exception(f"Failed to clean knowledge documents: {e}")
                session.rollback()

    @classmethod
    async def retrieve_With_doc_id(cls, doc_id)->dict[str, Any]:
        """
        Retrieve document by doc_id.
        """
        with get_db() as session:
            doc = session.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id).one_or_none()
            if not doc:
                return {"doc_id": doc_id, "error": "Document not found"}
            return {
                "doc_id": doc.id,
                "doc_content": doc.content}
