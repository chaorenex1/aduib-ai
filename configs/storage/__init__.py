from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class StorageConfig(BaseSettings):
    STORAGE_TYPE: Literal[
        "s3",
        "local",
    ] = Field(
        description="Type of storage to use. Options: 'opendal', '(deprecated) local', 's3'.",
        default="s3",
    )

    STORAGE_LOCAL_PATH: str = Field(
        description="Path for local storage when STORAGE_TYPE is set to 'local'.",
        default="llm",
        deprecated=True,
    )
