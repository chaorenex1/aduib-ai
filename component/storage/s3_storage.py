import logging
from typing import Generator, Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from configs import config
from .base_storage import BaseStorage

log = logging.getLogger(__name__)


class S3Storage(BaseStorage):
    def __init__(self):
        super().__init__()
        self.bucket_name = config.S3_BUCKET_NAME
        log.info("Using ak and sk for S3")

        self.client = boto3.client(
            "s3",
            aws_secret_access_key=config.S3_SECRET_KEY,
            aws_access_key_id=config.S3_ACCESS_KEY,
            endpoint_url=config.S3_ENDPOINT,
            region_name=config.S3_REGION,
            config=Config(
                s3={"addressing_style": config.S3_ADDRESS_STYLE},
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                self.client.create_bucket(Bucket=self.bucket_name)
            elif e.response["Error"]["Code"] == "403":
                pass
            else:
                raise

    def load(self, filename: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket_name, Key=filename)
        return response["Body"].read()

    def load_stream(self, filename: str) -> Generator:
        response = self.client.get_object(Bucket=self.bucket_name, Key=filename)
        yield from response["Body"].iter_chunks()

    def save(self, filename: str, data: Any):
        self.client.put_object(Bucket=self.bucket_name, Key=filename, Body=data)

    def delete(self, filename: str):
        self.client.delete_object(Bucket=self.bucket_name, Key=filename)

    def download(self, filename: str, target_file_path: str):
        self.client.download_file(self.bucket_name, filename, target_file_path)

    def size(self, filename: str) -> int:
        response = self.client.head_object(Bucket=self.bucket_name, Key=filename)
        return response["ContentLength"]

    def exists(self, filename: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=filename)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise
