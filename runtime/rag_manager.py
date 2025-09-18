import datetime
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select

from component.storage.base_storage import storage_manager
from models import KnowledgeBase, get_db, FileResource, KnowledgeEmbeddings
from models.document import KnowledgeDocument
from runtime.entities.document_entities import Document
from runtime.model_manager import ModelManager
from runtime.rag.extractor.entity.extraction_setting import ExtractionSetting
from runtime.rag.extractor.entity.extraction_source_type import ExtractionSourceType
from runtime.rag.keyword.keyword import Keyword
from runtime.rag.rag_processor.rag_processor_base import BaseRAGProcessor
from runtime.rag.rag_processor.rag_processor_factory import RAGProcessorFactory

logger = logging.getLogger(__name__)


class RagManager:
    def __init__(self):
        self.storage = storage_manager
        self.model_manager = ModelManager()

    def run(self, knowledge_docs: list[KnowledgeDocument]):
        """Run the RAG process."""
        with get_db() as session:
            for knowledge_doc in knowledge_docs:
                try:
                    kb = session.query(KnowledgeBase).filter_by(id=knowledge_doc.knowledge_base_id).one_or_none()
                    processing_rule = kb.data_process_rule
                    if not processing_rule:
                        raise ValueError("no process rule found")
                    rag_type = knowledge_doc.rag_type
                    rag_processor = RAGProcessorFactory.get_rag_processor(rag_type)
                    # extract
                    docs = self._extract(rag_processor, knowledge_doc, kb)

                    # transform
                    documents = self._transform(rag_processor, knowledge_doc, kb, docs)
                    # save segment
                    self._load_segments(kb, documents)

                    # load
                    self._load(
                        rag_processor=rag_processor,
                        knowledge_base=kb,
                        documents=documents,
                    )
                except Exception as e:
                    logger.exception("consume document failed")
                    knowledge_doc.rag_status = "error"
                    knowledge_doc.error_message = str(e)
                    knowledge_doc.stopped_at = datetime.datetime.now()
                    session.commit()

    def _extract(
            self, rag_processor: BaseRAGProcessor,
            knowledge_doc: KnowledgeDocument,
            knowledge_base: KnowledgeBase
    ) -> list[Document]:
        # load file
        processing_rule = knowledge_base.data_process_rule
        text_docs = []
        with get_db() as session:
            if knowledge_doc.data_source_type == "file":
                stmt = select(FileResource).where(FileResource.id == knowledge_doc.file_id)
                file_detail = session.scalars(stmt).one_or_none()

                if file_detail:
                    extract_setting = ExtractionSetting(
                        extraction_source=ExtractionSourceType.FILE,
                        extraction_file=file_detail,
                    )
                    text_docs = rag_processor.extract(extract_setting, process_rule_mode=processing_rule["mode"])
            elif knowledge_doc.data_source_type == "db_table":
                extract_setting = ExtractionSetting(
                    extraction_source=ExtractionSourceType.DB_TABLE,
                    extraction_db='conversation_message'
                )
                text_docs = rag_processor.extract(extract_setting, process_rule_mode=processing_rule["mode"])
            # update document status to splitting and word count
            _knowledge_doc = session.query(KnowledgeDocument).filter_by(id=knowledge_doc.id).one_or_none()
            if _knowledge_doc:
                _knowledge_doc.rag_status = "extracting"
                _knowledge_doc.word_count = sum(len(doc.content) for doc in text_docs)
                _knowledge_doc.extracted_at = datetime.datetime.now()
                session.commit()
                knowledge_base.word_count += _knowledge_doc.word_count
                session.commit()

            # replace doc id to document model id
            for text_doc in text_docs:
                if text_doc.metadata is not None:
                    text_doc.metadata["knowledge_id"] = str(_knowledge_doc.id)

        return text_docs

    def _transform(
            self,
            rag_processor: BaseRAGProcessor,
            knowledge_doc: KnowledgeDocument,
            knowledge_base: KnowledgeBase,
            docs: list[Document],
    ) -> list[Document]:
        embedding_model_instance = self.model_manager.get_model_instance(
            model_name=knowledge_base.embedding_model, provider_name=knowledge_base.embedding_model_provider
        )
        documents = rag_processor.transform(
            documents=docs,
            embedding_model_instance=embedding_model_instance,
            split_rule=knowledge_base.data_process_rule,
            doc_language=knowledge_doc.doc_language,
        )

        return documents

    def _load_segments(self, knowledge_base: KnowledgeBase, documents: list[Document]):
        # save node to document segment
        with get_db() as session:
            docs = []
            for document in documents:
                hash_ = document.metadata["doc_hash"]
                # count_ = session.query(Document).filter(KnowledgeEmbeddings.hash == hash_).count()
                # if count_:
                #     continue
                doc = KnowledgeEmbeddings(
                    id=document.metadata["doc_id"],
                    document_id=document.metadata["knowledge_id"],
                    knowledge_base_id=knowledge_base.id,
                    content=document.content,
                    meta=document.metadata if document.metadata else {},
                    hash=hash_,
                    model_name=knowledge_base.embedding_model,
                    provider_name=knowledge_base.embedding_model_provider,
                )
                docs.append(doc)
            session.bulk_save_objects(docs)
            session.commit()

        with get_db() as session:
            _knowledge_base = session.query(KnowledgeBase).filter_by(id=knowledge_base.id).one_or_none()
            if _knowledge_base:
                _knowledge_base.rag_status = "segmenting"
                _knowledge_base.spited_at = datetime.datetime.now()
                _knowledge_base.cleaned_at = datetime.datetime.now()
                session.commit()

    def _load(self, rag_processor: BaseRAGProcessor, knowledge_base: KnowledgeBase, documents: list[Document]):
        """
        insert index and update document/segment status to completed
        """

        embedding_model_instance = self.model_manager.get_model_instance(
            model_name=knowledge_base.embedding_model,
            provider_name=knowledge_base.embedding_model_provider,
        )

        # chunk nodes by chunk size
        indexing_start_at = time.perf_counter()
        tokens = 0
        create_keyword_thread = None
        create_keyword_thread = threading.Thread(
            target=self._process_keyword_index,
            args=(knowledge_base.id, documents),  # type: ignore
        )
        create_keyword_thread.start()

        max_workers = 10
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []

            # Distribute documents into multiple groups based on the hash values of page_content
            # This is done to prevent multiple threads from processing the same document,
            # Thereby avoiding potential database insertion deadlocks
            document_groups: list[list[Document]] = [[] for _ in range(max_workers)]
            for document in documents:
                hash = document.metadata["doc_hash"]
                group_index = int(hash, 16) % max_workers
                document_groups[group_index].append(document)
            for chunk_documents in document_groups:
                if len(chunk_documents) == 0:
                    continue
                futures.append(
                    executor.submit(
                        self._process_chunk,
                        rag_processor,
                        chunk_documents,
                        knowledge_base,
                        embedding_model_instance,
                    )
                )

            for future in futures:
                tokens += future.result()

        indexing_end_at = time.perf_counter()

        with get_db() as session:
            _knowledge_doc = session.query(KnowledgeDocument).filter_by(id=knowledge_base.id).one_or_none()
            if _knowledge_doc:
                _knowledge_doc.rag_status = "completed"
                _knowledge_doc.indexed_at = datetime.datetime.now()
                _knowledge_doc.indexed_time = indexing_end_at - indexing_start_at
                _knowledge_doc.token_count = tokens
                session.commit()
                knowledge_base.token_count+= tokens
                session.commit()

    @staticmethod
    def _process_keyword_index(knowledge_base_id, documents):
        with get_db() as session:
            knowledge_base = session.query(KnowledgeBase).filter_by(id=knowledge_base_id).first()
            if not knowledge_base:
                raise ValueError("no knowledge_base found")
            keyword = Keyword(knowledge_base)
            keyword.add_texts(documents)

    def _process_chunk(self, rag_processor, chunk_documents, dataset, embedding_model_instance):
        # check document is paused
        tokens = 0
        if embedding_model_instance:
            page_content_list = [document.content for document in chunk_documents]
            tokens += sum(embedding_model_instance.get_text_embedding_num_tokens(page_content_list))

        # load index
        rag_processor.load(dataset, chunk_documents, with_keywords=True)

        return tokens
