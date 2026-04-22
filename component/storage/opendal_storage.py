from __future__ import annotations

import logging
import os
from collections.abc import Generator
from pathlib import Path

import opendal
from dotenv import dotenv_values

from .base_storage import BaseStorage, StorageEntry, normalize_directory_path, normalize_storage_path

logger = logging.getLogger(__name__)


def _get_opendal_kwargs(*, scheme: str, env_file_path: str = ".env", prefix: str = "OPENDAL_"):
    kwargs = {}
    config_prefix = prefix + scheme.upper() + "_"
    for key, value in os.environ.items():
        if key.startswith(config_prefix):
            kwargs[key[len(config_prefix) :].lower()] = value

    file_env_vars: dict = dotenv_values(env_file_path) or {}
    for key, value in file_env_vars.items():
        if key.startswith(config_prefix) and key[len(config_prefix) :].lower() not in kwargs and value:
            kwargs[key[len(config_prefix) :].lower()] = value

    return kwargs


class OpenDALStorage(BaseStorage):
    def __init__(self, scheme: str, **kwargs):
        kwargs = kwargs or _get_opendal_kwargs(scheme=scheme)
        self.scheme = scheme

        if scheme == "fs":
            root = kwargs.get("root", "storage")
            Path(root).mkdir(parents=True, exist_ok=True)

        self.op = opendal.Operator(scheme=scheme, **kwargs)  # type: ignore
        retry_layer = opendal.layers.RetryLayer(max_times=3, factor=2.0, jitter=True)
        self.op = self.op.layer(retry_layer)
        logger.debug("Created opendal operator for scheme %s", scheme)

    def _ensure_parent_dir(self, path: str) -> None:
        parent = normalize_storage_path(path).rsplit("/", 1)[0] if "/" in normalize_storage_path(path) else ""
        if not parent:
            return

        try:
            self.op.create_dir(path=normalize_directory_path(parent))
        except Exception:
            logger.debug("Skip create_dir for %s", parent, exc_info=True)

    def save(self, filename: str, data: bytes) -> None:
        normalized_path = normalize_storage_path(filename)
        self._ensure_parent_dir(normalized_path)
        self.op.write(path=normalized_path, bs=data)
        logger.debug("Saved file %s", normalized_path)

    def load(self, filename: str) -> bytes:
        normalized_path = normalize_storage_path(filename)
        if not self.exists(normalized_path):
            raise FileNotFoundError("File not found")

        content: bytes = self.op.read(path=normalized_path)
        logger.debug("Loaded file %s", normalized_path)
        return content

    def load_stream(self, filename: str) -> Generator:
        normalized_path = normalize_storage_path(filename)
        if not self.exists(normalized_path):
            raise FileNotFoundError("File not found")

        batch_size = 4096
        file = self.op.open(path=normalized_path, mode="rb")
        while chunk := file.read(batch_size):
            yield chunk
        logger.debug("Loaded file stream %s", normalized_path)

    def download(self, filename: str, target_filepath: str):
        normalized_path = normalize_storage_path(filename)
        if not self.exists(normalized_path):
            raise FileNotFoundError("File not found")

        with Path(target_filepath).open("wb") as file:
            file.write(self.op.read(path=normalized_path))
        logger.debug("Downloaded file %s to %s", normalized_path, target_filepath)

    def exists(self, filename: str) -> bool:
        normalized_path = normalize_storage_path(filename)
        if not normalized_path:
            return True

        try:
            return bool(self.op.exists(path=normalized_path)) or bool(
                list(self.op.list(path=normalize_directory_path(normalized_path)))
            )
        except Exception:
            return False

    def delete(self, filename: str):
        normalized_path = normalize_storage_path(filename)
        if not normalized_path:
            return

        try:
            metadata = self.op.stat(path=normalized_path)
            if metadata.mode.is_dir():
                self.op.remove_all(path=normalize_directory_path(normalized_path))
            else:
                self.op.delete(path=normalized_path)
            logger.debug("Deleted path %s", normalized_path)
            return
        except Exception:
            pass

        directory_path = normalize_directory_path(normalized_path)
        try:
            if list(self.op.list(path=directory_path)):
                self.op.remove_all(path=directory_path)
                logger.debug("Deleted directory tree %s", directory_path)
                return
        except Exception:
            logger.debug("Skip delete for %s", normalized_path, exc_info=True)

        logger.debug("Path %s not found, skip delete", normalized_path)

    def size(self, filename: str) -> int:
        normalized_path = normalize_storage_path(filename)
        if not self.exists(normalized_path):
            raise FileNotFoundError("File not found")

        return self.op.stat(path=normalized_path).content_length

    def list_dir(self, path: str, recursive: bool = False) -> list[StorageEntry]:
        normalized_path = normalize_storage_path(path)
        directory_path = normalize_directory_path(normalized_path)
        iterator = self.op.scan(path=directory_path) if recursive else self.op.list(path=directory_path)
        entries: dict[str, StorageEntry] = {}

        for entry in iterator:
            raw_path = getattr(entry, "path", "")
            entry_path = normalize_storage_path(raw_path)
            if not entry_path or entry_path == normalized_path:
                continue

            try:
                metadata = self.op.stat(path=raw_path)
                is_dir = metadata.mode.is_dir()
                size = None if is_dir else metadata.content_length
            except Exception:
                is_dir = raw_path.endswith("/")
                size = None

            entries[entry_path] = StorageEntry(
                path=entry_path,
                is_file=not is_dir,
                is_dir=is_dir,
                size=size,
            )

        return sorted(entries.values(), key=lambda item: item.path)
