from __future__ import annotations

import fnmatch
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable, Generator, Iterable
from dataclasses import dataclass
from typing import Any, Literal

from aduib_app import AduibAIApp
from configs import config

log = logging.getLogger(__name__)

DEFAULT_TEXT_ENCODING = "utf-8"


def normalize_storage_path(path: str) -> str:
    raw = str(path or "").replace("\\", "/").strip()
    if raw in {"", ".", "/"}:
        return ""

    parts = [part for part in raw.split("/") if part not in {"", "."}]
    return "/".join(parts)


def normalize_directory_path(path: str) -> str:
    normalized = normalize_storage_path(path)
    return f"{normalized}/" if normalized else ""


def _glob_search_root(pattern: str) -> str:
    wildcard_index = next((index for index, char in enumerate(pattern) if char in "*?["), None)
    if wildcard_index is None:
        return pattern.rsplit("/", 1)[0] if "/" in pattern else ""

    literal_prefix = pattern[:wildcard_index]
    if "/" not in literal_prefix:
        return ""
    return literal_prefix.rsplit("/", 1)[0]


@dataclass(frozen=True, slots=True)
class StorageEntry:
    path: str
    is_file: bool
    is_dir: bool
    size: int | None = None


@dataclass(frozen=True, slots=True)
class StorageSnapshotItem:
    path: str
    data: bytes


@dataclass(frozen=True, slots=True)
class StorageSnapshotRoot:
    path: str
    kind: Literal["file", "tree", "missing"]


@dataclass(frozen=True, slots=True)
class StorageSnapshot:
    roots: tuple[StorageSnapshotRoot, ...]
    items: tuple[StorageSnapshotItem, ...]


class BaseStorage(ABC):
    @abstractmethod
    def save(self, filename: str, data: Any):
        raise NotImplementedError()

    @abstractmethod
    def load(self, filename: str) -> bytes:
        raise NotImplementedError()

    @abstractmethod
    def load_stream(self, filename: str) -> Generator:
        raise NotImplementedError()

    @abstractmethod
    def delete(self, filename: str):
        raise NotImplementedError()

    @abstractmethod
    def exists(self, filename: str) -> bool:
        raise NotImplementedError()

    @abstractmethod
    def download(self, filename: str, target_file_path: str):
        raise NotImplementedError()

    @abstractmethod
    def size(self, filename: str) -> int:
        raise NotImplementedError()

    @abstractmethod
    def list_dir(self, path: str, recursive: bool = False) -> list[StorageEntry]:
        raise NotImplementedError()

    def read_text(self, filename: str, encoding: str = DEFAULT_TEXT_ENCODING) -> str:
        return self.load(filename).decode(encoding)

    def write_text_atomic(self, filename: str, content: str, encoding: str = DEFAULT_TEXT_ENCODING) -> None:
        self.save(filename, content.encode(encoding))

    def glob(self, pattern: str) -> list[StorageEntry]:
        normalized_pattern = normalize_storage_path(pattern)
        if not normalized_pattern:
            return self.list_dir("", recursive=True)

        if not any(char in normalized_pattern for char in "*?["):
            if not self.exists(normalized_pattern):
                return []

            try:
                return [
                    StorageEntry(
                        path=normalized_pattern,
                        is_file=True,
                        is_dir=False,
                        size=self.size(normalized_pattern),
                    )
                ]
            except Exception:
                return self.list_dir(normalized_pattern, recursive=True)

        search_root = _glob_search_root(normalized_pattern)
        candidate_patterns = [normalized_pattern]
        if "**/" in normalized_pattern:
            candidate_patterns.append(normalized_pattern.replace("**/", ""))
        return [
            entry
            for entry in self.list_dir(search_root, recursive=True)
            if any(fnmatch.fnmatch(entry.path, candidate_pattern) for candidate_pattern in candidate_patterns)
        ]

    def snapshot(self, paths: Iterable[str]) -> StorageSnapshot:
        snapshot_roots: list[StorageSnapshotRoot] = []
        snapshot_items: dict[str, StorageSnapshotItem] = {}

        for path in paths:
            normalized_path = normalize_storage_path(path)
            file_entries = [entry for entry in self.list_dir(normalized_path, recursive=True) if entry.is_file]

            if file_entries:
                snapshot_roots.append(StorageSnapshotRoot(path=normalized_path, kind="tree"))
                for entry in file_entries:
                    snapshot_items[entry.path] = StorageSnapshotItem(path=entry.path, data=self.load(entry.path))
                continue

            if normalized_path and self.exists(normalized_path):
                snapshot_roots.append(StorageSnapshotRoot(path=normalized_path, kind="file"))
                snapshot_items[normalized_path] = StorageSnapshotItem(
                    path=normalized_path,
                    data=self.load(normalized_path),
                )
                continue

            snapshot_roots.append(StorageSnapshotRoot(path=normalized_path, kind="missing"))

        return StorageSnapshot(
            roots=tuple(snapshot_roots),
            items=tuple(sorted(snapshot_items.values(), key=lambda item: item.path)),
        )

    def restore(self, snapshot: StorageSnapshot) -> None:
        item_map = {item.path: item for item in snapshot.items}

        for root in sorted(snapshot.roots, key=lambda entry: entry.path.count("/"), reverse=True):
            if root.kind == "missing":
                if root.path:
                    self.delete(root.path)
                continue

            if root.kind != "tree":
                continue

            prefix = normalize_directory_path(root.path)
            expected_paths = {path for path in item_map if not prefix or path == root.path or path.startswith(prefix)}
            current_entries = [entry for entry in self.list_dir(root.path, recursive=True) if entry.is_file]
            for entry in current_entries:
                if entry.path not in expected_paths:
                    self.delete(entry.path)

        for item in snapshot.items:
            self.save(item.path, item.data)

    def copy(self, source: str, target: str) -> None:
        normalized_source = normalize_storage_path(source)
        normalized_target = normalize_storage_path(target)
        tree_entries = [entry for entry in self.list_dir(normalized_source, recursive=True) if entry.is_file]

        if tree_entries:
            source_prefix = normalize_directory_path(normalized_source)
            for entry in tree_entries:
                relative_path = entry.path[len(source_prefix) :] if source_prefix else entry.path
                target_path = "/".join(part for part in [normalized_target, relative_path] if part)
                self.save(target_path, self.load(entry.path))
            return

        if not self.exists(normalized_source):
            raise FileNotFoundError(f"Storage path not found: {normalized_source}")

        self.save(normalized_target, self.load(normalized_source))

    def move(self, source: str, target: str) -> None:
        self.copy(source, target)
        self.delete(source)


class StorageManager:
    def __init__(self):
        self.storage_instance: BaseStorage | None = None

    def init_storage(self, app: AduibAIApp):
        storage = self.get_storage_instance(config.STORAGE_TYPE, app)
        self.storage_instance = storage()

    @staticmethod
    def get_storage_instance(storage_type: str, app: AduibAIApp) -> Callable[[], BaseStorage]:
        match storage_type:
            case "local":
                from .opendal_storage import OpenDALStorage

                storage_path = (
                    config.STORAGE_LOCAL_PATH if config.STORAGE_LOCAL_PATH else app.app_home + "/" + storage_type
                )
                return lambda: OpenDALStorage(scheme="fs", root=storage_path)
            case "s3":
                from .s3_storage import S3Storage

                return S3Storage
            case _:
                raise ValueError(f"Unsupported storage type: {storage_type}")

    def _get_storage(self) -> BaseStorage:
        if self.storage_instance is None:
            raise RuntimeError("Storage manager has not been initialized")
        return self.storage_instance

    def _call_storage(self, operation: str, *args, **kwargs):
        storage = self._get_storage()
        try:
            return getattr(storage, operation)(*args, **kwargs)
        except Exception:
            log.exception("Failed to %s on storage target %s", operation, args[0] if args else "<storage>")
            raise

    def save(self, filename: str, data: Any):
        self._call_storage("save", filename, data)

    def load(self, filename: str, stream: bool = False) -> bytes | Generator:
        operation = "load_stream" if stream else "load"
        return self._call_storage(operation, filename)

    def delete(self, filename: str):
        self._call_storage("delete", filename)

    def exists(self, filename: str) -> bool:
        return self._call_storage("exists", filename)

    def download(self, filename: str, target_file_path: str):
        self._call_storage("download", filename, target_file_path)

    def size(self, filename: str) -> int:
        return self._call_storage("size", filename)

    def read_text(self, filename: str, encoding: str = DEFAULT_TEXT_ENCODING) -> str:
        return self._call_storage("read_text", filename, encoding)

    def write_text_atomic(self, filename: str, content: str, encoding: str = DEFAULT_TEXT_ENCODING) -> None:
        self._call_storage("write_text_atomic", filename, content, encoding)

    def list_dir(self, path: str, recursive: bool = False) -> list[StorageEntry]:
        return self._call_storage("list_dir", path, recursive)

    def glob(self, pattern: str) -> list[StorageEntry]:
        return self._call_storage("glob", pattern)

    def snapshot(self, paths: Iterable[str]) -> StorageSnapshot:
        return self._call_storage("snapshot", paths)

    def restore(self, snapshot: StorageSnapshot) -> None:
        self._call_storage("restore", snapshot)

    def copy(self, source: str, target: str) -> None:
        self._call_storage("copy", source, target)

    def move(self, source: str, target: str) -> None:
        self._call_storage("move", source, target)


storage_manager = StorageManager()


def init_storage(app: AduibAIApp):
    storage_manager.init_storage(app)
    app.extensions["storage_manager"] = storage_manager
