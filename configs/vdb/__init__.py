from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class VectorStoreConfig(BaseSettings):
    VECTOR_STORE: Optional[str] = Field(
        description="Type of vector store to use for efficient similarity search."
        " Set to None if not using a vector store.",
        default=None,
    )
