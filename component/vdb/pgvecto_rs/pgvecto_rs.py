import json
import logging
from typing import Any

from pgvecto_rs.sqlalchemy import VECTOR  # type: ignore
from sqlalchemy import Float, select, func, bindparam, desc
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from component.vdb.base_vector import BaseVector
from component.vdb.vector_factory import AbstractVectorFactory
from component.vdb.vector_type import VectorType
from models import get_db, KnowledgeEmbeddings, KnowledgeBase
from runtime.entities.document_entities import Document
from runtime.rag.embeddings.embeddings import Embeddings

logger = logging.getLogger(__name__)


class PGVectoRS(BaseVector):
    def __init__(self, collection_name: str, dim: int):
        super().__init__(collection_name)
        self.dim = dim
        self._collection_name = collection_name or KnowledgeEmbeddings.__tablename__
        self._table = KnowledgeEmbeddings
        self._distance_op = "<=>"

    def get_type(self) -> str:
        return VectorType.PGVECTO_RS

    def save(self, texts: list[Document], embeddings: list[list[float]], **kwargs):
        self.create_collection(len(embeddings[0]))
        self.add_texts(texts, embeddings)

    def create_collection(self, dimension: int):
        # lock_name = f"vector_lock_{self._collection_name}"
        # from component.cache.redis_cache import redis_client
        # with redis_client.lock(lock_name, timeout=20):
        #     collection_exist_cache_key = f"vector_{self._collection_name}"
        #     if redis_client.get(collection_exist_cache_key):
        #         return
        #     with get_db() as session:
        #         alter_statement = sql_text(f"""
        #             ALTER TABLE {self._collection_name} ALTER COLUMN vector TYPE VECTOR({dimension}) USING vector::vector({dimension});
        #         """)
        #         session.execute(alter_statement)
        #         session.commit()
        #     redis_client.set(collection_exist_cache_key, 1, ex=3600)
        ...  # PGVector with SQLAlchemy creates the table automatically if it does not exist.

    def add_texts(self, documents: list[Document], embeddings: list[list[float]], **kwargs):
        pks = []
        with get_db() as session:
            for document, embedding in zip(documents, embeddings):
                pk = document.metadata["doc_id"]
                update_stmt = sql_text(
                    f"""UPDATE {self._collection_name} SET content = :content, meta = :metadata, vector = :vector WHERE id = :id;""")
                session.execute(update_stmt,
                                {"id": pk, "content": document.content, "metadata": json.dumps(document.metadata),
                                 "vector": f"[{','.join(map(str, embedding))}]"})
                pks.append(pk)
            session.commit()

        return pks

    def get_ids_by_metadata_field(self, key: str, value: str):
        result = None
        with get_db() as session:
            select_statement = sql_text(
                f"SELECT id FROM {self._collection_name} WHERE meta->>'{key}' = '{value}'; "
            )
            result = session.execute(select_statement).fetchall()
        if result:
            return [item[0] for item in result]
        else:
            return None

    def delete_by_metadata_field(self, key: str, value: str):
        ids = self.get_ids_by_metadata_field(key, value)
        if ids:
            with get_db() as session:
                select_statement = sql_text(f"DELETE FROM {self._collection_name} WHERE id = ANY(:ids)")
                session.execute(select_statement, {"ids": ids})
                session.commit()

    def delete_by_ids(self, ids: list[str]):
        with get_db() as session:
            select_statement = sql_text(
                f"SELECT id FROM {self._collection_name} WHERE meta->>'doc_id' = ANY (:doc_ids); "
            )
            result = session.execute(select_statement, {"doc_ids": ids}).fetchall()
        if result:
            ids = [item[0] for item in result]
            if ids:
                with Session(self._client) as session:
                    select_statement = sql_text(f"DELETE FROM {self._collection_name} WHERE id = ANY(:ids)")
                    session.execute(select_statement, {"ids": ids})
                    session.commit()

    def delete_all(self):
        with get_db() as session:
            session.execute(sql_text(f"DROP TABLE IF EXISTS {self._collection_name}"))
            session.commit()

    def exists(self, id: str) -> bool:
        with get_db() as session:
            select_statement = sql_text(
                f"SELECT id FROM {self._collection_name} WHERE meta->>'doc_id' = '{id}' limit 1; "
            )
            result = session.execute(select_statement).fetchall()
        return len(result) > 0

    def search_by_vector(self, query_vector: list[float], **kwargs: Any) -> list[Document]:
        with get_db() as session:
            stmt = (
                select(
                    self._table,
                    self._table.vector.op(self._distance_op, return_type=Float)(
                        query_vector,
                    ).label("distance"),
                )
                .limit(kwargs.get("top_k", 4))
                .order_by("distance")
            )
            knowledge_ids_filter = kwargs.get("knowledge_ids_filter")
            if knowledge_ids_filter:
                stmt = stmt.where(self._table.meta["knowledge_id"].in_(knowledge_ids_filter))
            res = session.execute(stmt)
            results = [(row[0], row[1]) for row in res]

        # Organize results.
        docs = []
        for record, dis in results:
            meta = record.meta
            score = 1 - dis
            meta["score"] = score
            score_threshold = float(kwargs.get("score_threshold") or 0.0)
            if score >= score_threshold:
                doc = Document(content=record.content, metadata=meta)
                docs.append(doc)
        return docs

    def search_by_full_text(self, query: str, **kwargs: Any) -> list[Document]:
        with get_db() as session:
            stmt = (
                select(
                    self._table,
                    func.ts_rank(
                        func.to_jieba_tsvector(self._table.content),
                        func.to_jieba_tsquery(bindparam("query"))
                    ).label("rank"),
                )
                .where(func.ts_rank(
                    func.to_jieba_tsvector(self._table.content),
                    func.to_jieba_tsquery(bindparam("query"))
                ) > 0)
                .limit(kwargs.get("top_k", 4))
                .order_by(desc("rank"))
            )

            knowledge_ids_filter = kwargs.get("knowledge_ids_filter")
            if knowledge_ids_filter:
                stmt = stmt.where(self._table.meta["knowledge_id"].astext.in_(knowledge_ids_filter))
            # stmt = (
            #     select(
            #         self._table,
            #         self._table.content.op("@@")(sql_text(f"to_jieba_tsquery('{query}')")).label("rank"),
            #     )
            #     .where(self._table.content.op("@@")(sql_text(f"to_jieba_tsquery('{query}')")))
            #     .limit(kwargs.get("top_k", 4))
            #     .order_by(sql_text("rank DESC"))
            # )
            # knowledge_ids_filter = kwargs.get("knowledge_ids_filter")
            # if knowledge_ids_filter:
            #     stmt = stmt.where(self._table.meta["knowledge_id"].in_(knowledge_ids_filter))
            res = session.execute(stmt, {"query": query})
            results = [row[0] for row in res]

        docs = [Document(content=record.content, metadata=record.meta) for record in results]
        return docs


class PGVectoRSFactory(AbstractVectorFactory):
    def init_vector(self, knowledge: KnowledgeBase, attributes: list, embeddings: Embeddings) -> PGVectoRS:
        dim = len(embeddings.embed_query("pgvecto_rs"))

        return PGVectoRS(
            collection_name=KnowledgeEmbeddings.__tablename__,
            dim=dim,
        )
