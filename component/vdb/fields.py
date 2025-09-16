from enum import Enum


class Field(Enum):
    CONTENT_KEY = "content"
    METADATA_KEY = "metadata"
    VECTOR = "vector"
    SPARSE_VECTOR = "sparse_vector"
    TEXT_KEY = "text"
    PRIMARY_KEY = "id"