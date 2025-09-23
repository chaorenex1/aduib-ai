from typing import Any

from component.cache.redis_cache import redis_client
from models import KnowledgeBase, get_db
from models.document import KnowledgeKeywords, KnowledgeEmbeddings
from runtime.entities.document_entities import Document
from runtime.rag.keyword.jieba import JiebaKeyword


class Keyword:
    def __init__(self, knowledge: KnowledgeBase):
        self._knowledge = knowledge
        self._keyword_processor = JiebaKeyword()

    def create(self, texts: list[Document], **kwargs):
        self.add_texts(texts, **kwargs)

    def add_texts(self, texts: list[Document], **kwargs):
        lock_name = f"keyword_indexing_lock_{self._knowledge.id}"
        with redis_client.lock(lock_name, timeout=600):
            for text in texts:
                keywords = self._keyword_processor.extract_keywords(text=text.content, **kwargs)
                if len(keywords) > 0:
                    knowledge_id = text.metadata.get("knowledge_id")
                    keyword_list = []
                    with get_db() as session:
                        for kw in keywords:
                            kw__count = (
                                session.query(KnowledgeKeywords)
                                .filter(
                                    KnowledgeKeywords.document_id == knowledge_id,
                                    KnowledgeKeywords.keyword == kw,
                                )
                                .count()
                            )
                            if kw__count == 0:
                                keyword_list.append(
                                    KnowledgeKeywords(
                                        knowledge_id=self._knowledge.id,
                                        document_id=knowledge_id,
                                        keyword=kw,
                                    )
                                )
                        session.bulk_save_objects(keyword_list)
                        session.commit()

    def text_exists(self, id: str) -> bool:
        lock_name = f"keyword_indexing_lock_{self._knowledge.id}"
        with redis_client.lock(lock_name, timeout=600):
            with get_db() as session:
                count = session.query(KnowledgeKeywords).filter(KnowledgeKeywords.document_id == id).count()
                return count > 0

    def delete_by_ids(self, ids: list[str]):
        lock_name = f"keyword_indexing_lock_{self._knowledge.id}"
        with redis_client.lock(lock_name, timeout=600):
            with get_db() as session:
                session.query(KnowledgeKeywords).filter(KnowledgeKeywords.document_id.in_(ids)).delete()
                session.commit()

    def delete(self):
        lock_name = f"keyword_indexing_lock_{self._knowledge.id}"
        with redis_client.lock(lock_name, timeout=600):
            with get_db() as session:
                session.query(KnowledgeKeywords).delete()
                session.commit()

    def search(self, query: str, **kwargs: Any) -> list[Document]:
        lock_name = f"keyword_indexing_lock_{self._knowledge.id}"
        with redis_client.lock(lock_name, timeout=600):
            keywords = self._keyword_processor.extract_keywords(text=query, **kwargs)
            if len(keywords) == 0:
                return []

            with get_db() as session:
                results = (
                    session.query(KnowledgeKeywords.document_id, KnowledgeKeywords.keyword)
                    .filter(KnowledgeKeywords.keyword.in_(keywords))
                    .all()
                )

            doc_ids = []
            for doc_id, keyword in results:
                doc_ids.append(doc_id)

            documents = []
            for doc_id in doc_ids:
                with get_db() as session:
                    for document in (
                        session.query(KnowledgeEmbeddings).filter(KnowledgeEmbeddings.document_id == doc_id).all()
                    ):
                        doc = Document(content=document.content, metadata=document.metadata)
                        documents.append(doc)

            return documents
