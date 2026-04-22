from __future__ import annotations

import logging
from collections.abc import Generator
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from configs import config

from .base_storage import BaseStorage, StorageEntry, normalize_directory_path, normalize_storage_path

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
        except ClientError as error:
            if error.response["Error"]["Code"] == "404":
                self.client.create_bucket(Bucket=self.bucket_name)
            elif error.response["Error"]["Code"] == "403":
                pass
            else:
                raise

    @staticmethod
    def _is_not_found(error: ClientError) -> bool:
        return error.response["Error"]["Code"] in {"404", "NoSuchKey", "NotFound"}

    def _object_exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as error:
            if self._is_not_found(error):
                return False
            raise

    def _prefix_exists(self, prefix: str) -> bool:
        response = self.client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix, MaxKeys=1)
        return response.get("KeyCount", 0) > 0

    def _iter_objects(self, prefix: str):
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
            yield from page.get("Contents", [])

    def save(self, filename: str, data: Any):
        key = normalize_storage_path(filename)
        self.client.put_object(Bucket=self.bucket_name, Key=key, Body=data)

    def load(self, filename: str) -> bytes:
        key = normalize_storage_path(filename)
        response = self.client.get_object(Bucket=self.bucket_name, Key=key)
        return response["Body"].read()

    def load_stream(self, filename: str) -> Generator:
        key = normalize_storage_path(filename)
        response = self.client.get_object(Bucket=self.bucket_name, Key=key)
        yield from response["Body"].iter_chunks()

    def delete(self, filename: str):
        key = normalize_storage_path(filename)
        if not key:
            return

        deleted = False
        if self._object_exists(key):
            self.client.delete_object(Bucket=self.bucket_name, Key=key)
            deleted = True

        prefix = normalize_directory_path(key)
        if prefix and self._prefix_exists(prefix):
            keys = [{"Key": item["Key"]} for item in self._iter_objects(prefix)]
            for index in range(0, len(keys), 1000):
                self.client.delete_objects(Bucket=self.bucket_name, Delete={"Objects": keys[index : index + 1000]})
            deleted = True

        if not deleted:
            log.debug("Path %s not found in bucket %s", key, self.bucket_name)

    def download(self, filename: str, target_file_path: str):
        key = normalize_storage_path(filename)
        self.client.download_file(self.bucket_name, key, target_file_path)

    def size(self, filename: str) -> int:
        key = normalize_storage_path(filename)
        response = self.client.head_object(Bucket=self.bucket_name, Key=key)
        return response["ContentLength"]

    def exists(self, filename: str) -> bool:
        key = normalize_storage_path(filename)
        if not key:
            return True
        return self._object_exists(key) or self._prefix_exists(normalize_directory_path(key))

    def list_dir(self, path: str, recursive: bool = False) -> list[StorageEntry]:
        normalized_path = normalize_storage_path(path)
        prefix = normalize_directory_path(normalized_path)
        entries: dict[str, StorageEntry] = {}
        paginator = self.client.get_paginator("list_objects_v2")
        paginate_kwargs = {"Bucket": self.bucket_name, "Prefix": prefix}
        if not recursive:
            paginate_kwargs["Delimiter"] = "/"

        for page in paginator.paginate(**paginate_kwargs):
            for common_prefix in page.get("CommonPrefixes", []):
                dir_path = normalize_storage_path(common_prefix["Prefix"])
                if dir_path and dir_path != normalized_path:
                    entries[dir_path] = StorageEntry(path=dir_path, is_file=False, is_dir=True, size=None)

            for item in page.get("Contents", []):
                key = normalize_storage_path(item["Key"])
                if not key or key == normalized_path or key.endswith("/"):
                    continue

                if recursive:
                    relative = key[len(prefix) :] if prefix else key
                    parts = relative.split("/")
                    for index in range(len(parts) - 1):
                        dir_path = "/".join(part for part in [normalized_path, *parts[: index + 1]] if part)
                        entries[dir_path] = StorageEntry(path=dir_path, is_file=False, is_dir=True, size=None)

                entries[key] = StorageEntry(path=key, is_file=True, is_dir=False, size=item["Size"])

        return sorted(entries.values(), key=lambda entry: entry.path)
