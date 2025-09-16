from enum import StrEnum


class StorageType(StrEnum):
    """Storage type enum."""

    LOCAL = "local"
    S3 = "s3"
