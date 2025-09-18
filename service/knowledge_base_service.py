import hashlib

from models import KnowledgeBase, get_db
from models.document import KnowledgeDocument
from runtime.rag.rag_type import RagType


class KnowledgeBaseService:

    @classmethod
    async def paragraph_rag_from_web_memo(cls, crawl_text: str, crawl_type: str) -> None:
        """
        Create a RAG (Retrieval-Augmented Generation) knowledge base from a web memo URL.
        :param url: The URL of the web memo.
        :param ua: Optional user agent string.
        :return: None
        """
        from .file_service import FileService

        file_hash = hashlib.sha256(crawl_text.encode('utf-8')).hexdigest()
        file_name = f"web_memo_{file_hash}.{crawl_type}"
        file_record = FileService.upload_bytes(file_name, crawl_text.encode('utf-8'))

        from runtime.generator.generator import LLMGenerator
        name = LLMGenerator.generate_conversation_name(crawl_text)
        language = LLMGenerator.generate_language(crawl_text)
        with get_db() as session:
            existing_kb = session.query(KnowledgeBase).filter_by(default_base==1,rag_type=RagType.PARAGRAPH).one_or_none()
            if existing_kb:
                doc = KnowledgeDocument(
                    knowledge_base_id=existing_kb.id,
                    title=name,
                    file_id=file_record.id,
                    doc_language=language,
                    doc_from="web_memo",
                    rag_type=RagType.PARAGRAPH,
                    data_source_type='file',
                    # data_process_rule={
                    #     "mode": "custom",
                    #     "rules": {
                    #         "pre_processing_rules": [
                    #             {"id": "remove_extra_spaces", "enabled": True},
                    #             {"id": "remove_urls_emails", "enabled": False},
                    #         ],
                    #         "segmentation": {"delimiter": "\n", "max_tokens": 500, "chunk_overlap": 50},
                    #     }
                    # },
                    # embedding_model="Qwen/Qwen3-Embedding-4B",
                    # embedding_model_provider="transformer"
                )
                session.add(doc)
                session.commit()
                session.refresh(doc)


    @classmethod
    async def retrieve_from_knowledge_base(cls, query: str, top_k: int = 5):
        from runtime.rag.rag_processor.rag_processor_factory import RAGProcessorFactory
        rag_processor = RAGProcessorFactory.get_rag_processor("qa")
        return rag_processor.retrieve("",query, top_k,None, 0.0, "")