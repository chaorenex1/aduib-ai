from enum import StrEnum


class VectorType(StrEnum):
    MILVUS = "milvus"
    PGVECTOR = "pgvector"
    PGVECTO_RS = "pgvecto-rs"