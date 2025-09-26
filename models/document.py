import datetime

from pgvecto_rs.sqlalchemy import VECTOR
from sqlalchemy import Column, DateTime, Integer, String, text, UUID, Index, func, TEXT
from sqlalchemy.dialects.postgresql import JSONB

from models import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"), comment="id")
    created_at = Column(DateTime, default=datetime.datetime.now(), comment="create time")
    updated_at = Column(DateTime, default=datetime.datetime.now(), comment="update time")
    deleted = Column(Integer, default=0, comment="delete flag")
    name = Column(String(255), nullable=False, comment="name")
    rag_type = Column(String, index=True, nullable=False, comment="rag type")
    data_process_rule = Column(JSONB, nullable=True, comment="data process rule")
    embedding_model = Column(String(255), nullable=False, comment="embedding model name")
    embedding_model_provider = Column(String(255), nullable=False, comment="embedding provider name")
    rerank_model = Column(String(255), nullable=True, comment="rerank model name", server_default=text("''"))
    rerank_model_provider = Column(
        String(255), nullable=True, comment="rerank provider name", server_default=text("''")
    )
    reranking_rule = Column(JSONB, nullable=True, comment="reranking rule", server_default=text("'{}'"))
    word_count = Column(Integer, nullable=True, server_default=text("0"), comment="word count")
    token_count = Column(Integer, nullable=True, server_default=text("0"), comment="token count")
    default_base = Column(Integer, nullable=True, server_default=text("0"), comment="default knowledge base")


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_document"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"), comment="id")
    knowledge_base_id = Column(UUID(as_uuid=True), index=True, nullable=False, comment="knowledge_base_id")
    created_at = Column(DateTime, default=datetime.datetime.now(), comment="create time")
    updated_at = Column(DateTime, default=datetime.datetime.now(), comment="update time")
    deleted = Column(Integer, default=0, comment="delete flag")
    title = Column(String(255), nullable=False, comment="name")
    file_id = Column(String, index=True, nullable=True, comment="file id")
    message_id = Column(String, index=True, nullable=True, comment="message id")
    content = Column(TEXT, nullable=False, comment="content", server_default=text("''"))
    doc_language = Column(String(50), nullable=False, comment="knowledge language")
    doc_from = Column(String(255), nullable=True, comment="document from", server_default=text("''"))
    rag_type = Column(String, index=True, nullable=False, comment="rag type")
    data_source_type = Column(String, index=True, nullable=False, comment="data source type")
    rag_status = Column(String(50), nullable=True, comment="rag status")
    error_message = Column(String(255), nullable=True, comment="error message", server_default=text("''"))
    stop_at = Column(DateTime, nullable=True, comment="stop at")
    word_count = Column(Integer, nullable=True, server_default=text("0"), comment="word count")
    extracted_at = Column(DateTime, nullable=True, comment="extracted at")
    spited_at = Column(DateTime, nullable=True, comment="split at")
    cleaned_at = Column(DateTime, nullable=True, comment="cleaned at")
    indexed_at = Column(DateTime, nullable=True, comment="embedded at")
    indexed_time = Column(Integer, nullable=True, server_default=text("0"), comment="indexed times")
    token_count = Column(Integer, nullable=True, server_default=text("0"), comment="token count")

    __table_args__ = (
        Index("idx_knowledge_document_content", func.to_tsvector(text("'jieba_cfg'"), content), postgresql_using="gin"),
    )


"""
index = Index(
    "emb_idx_2",
    Item.embedding,
    postgresql_using="vectors",
    postgresql_with={
        "options": f"$${IndexOption(index=Hnsw()).dumps()}$$"
    },
    postgresql_ops={"embedding": "vector_l2_ops"},
)
"""


class KnowledgeEmbeddings(Base):
    __tablename__ = "knowledge_embeddings"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"), comment="id")
    knowledge_base_id = Column(UUID(as_uuid=True), index=True, nullable=False, comment="knowledge_base_id")
    document_id = Column(UUID(as_uuid=True), index=True, nullable=False, comment="document_id")
    content = Column(TEXT, nullable=False, comment="content", server_default=text("''"))
    vector = Column(VECTOR(4096), nullable=True, comment="embedding vector")
    meta = Column(JSONB, nullable=False, comment="metadata", server_default=text("'{}'"))
    hash = Column(String(64), nullable=False, comment="content hash")
    __table_args__ = (
        Index(
            "idx_knowledge_embeddings_content", func.to_tsvector(text("'jieba_cfg'"), content), postgresql_using="gin"
        ),
        Index(
            "idx_knowledge_embeddings_vector",
            vector,
            postgresql_using="vectors",
            postgresql_with={
                "options": """$$optimizing.optimizing_threads = 30
                                segment.max_growing_segment_size = 2000
                                segment.max_sealed_segment_size = 30000000
                                [indexing.hnsw]
                                m=30
                                ef_construction=500$$"""
            },
            postgresql_ops={"vector": "vector_l2_ops"},
        ),
    )


class KnowledgeKeywords(Base):
    __tablename__ = "knowledge_keywords"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"), comment="id")
    knowledge_id = Column(UUID(as_uuid=True), index=True, nullable=False, comment="knowledge_id")
    document_id = Column(UUID(as_uuid=True), index=True, nullable=False, comment="doc_id")
    keyword = Column(String(255), index=True, nullable=True, comment="keyword")
    created_at = Column(DateTime, default=datetime.datetime.now(), comment="create time")
    updated_at = Column(DateTime, default=datetime.datetime.now(), comment="update time")
    deleted = Column(Integer, default=0, comment="delete flag")
