from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class S3StorageConfig(BaseSettings):
    """
    Configuration settings for S3-compatible object storage
    """

    S3_ENDPOINT: Optional[str] = Field(
        description="s3 endpoint url",
        default=None,
    )

    S3_REGION: Optional[str] = Field(
        description="s3 region",
        default=None,
    )

    S3_BUCKET_NAME: Optional[str] = Field(
        description="s3 bucket name",
        default=None,
    )

    S3_ACCESS_KEY: Optional[str] = Field(
        description="s3 access key",
        default=None,
    )

    S3_SECRET_KEY: Optional[str] = Field(
        description="s3 secret key",
        default=None,
    )

    S3_ADDRESS_STYLE: str = Field(
        description="S3 addressing style: 'auto', 'path', or 'virtual'",
        default="auto",
    )
