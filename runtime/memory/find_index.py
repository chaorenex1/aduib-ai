from __future__ import annotations

import logging
import re
from collections import defaultdict
from hashlib import sha256
from typing import Literal

from component.vdb.specs import VectorStoreSpec
from component.vdb.vector_factory import Vector
from configs import config
from runtime.entities.document_entities import Document
from runtime.memory.apply.patch import parse_markdown_document
from runtime.memory.committed_tree import CommittedMemoryTree
from runtime.rag.embeddings import DefaultEmbeddingProvider
from service.memory.repository import MemoryMetadataRepository

from .find_types import (
    FIND_L0_LEVEL,
    FIND_L1_LEVEL,
    L0VectorHit,
    L1BranchHit,
    NavigationIndexSourceRow,
)

logger = logging.getLogger(__name__)


class MemoryFindIndex:
    @classmethod
    def refresh_scope_navigation_index(
        cls,
        task_id: str,
        scope_paths: list[str],
        expected_user_id: str | None = None,
    ) -> None:
        normalized_scope_paths = sorted(
            {
                normalized
                for item in scope_paths
                for normalized in [str(item).strip().strip("/")]
                if normalized
            }
        )
        if not normalized_scope_paths:
            return

        for scope_path in normalized_scope_paths:
            cls._validate_scope_user(path=scope_path, expected_user_id=expected_user_id)

        previous_rows = MemoryMetadataRepository.list_navigation_rows_for_scope(normalized_scope_paths)
        rows: list[NavigationIndexSourceRow] = []
        for scope_path in normalized_scope_paths:
            rows.extend(
                cls._collect_navigation_rows(
                    scope_path=scope_path,
                    task_id=task_id,
                    expected_user_id=expected_user_id,
                )
            )

        MemoryMetadataRepository.replace_navigation_index_records(
            scope_paths=normalized_scope_paths,
            records=[item.model_dump() for item in rows],
        )

        previous_doc_ids = cls._group_doc_ids(previous_rows)
        new_rows_by_group = cls._group_rows(rows)
        for group_key in sorted(set(previous_doc_ids) | set(new_rows_by_group)):
            user_id, level = group_key
            documents = cls._build_vector_documents(new_rows_by_group.get(group_key, []))
            cls._write_vector_documents(
                user_id=user_id,
                level=level,
                documents=documents,
                stale_doc_ids=previous_doc_ids.get(group_key, []),
            )

    @classmethod
    def delete_scope_navigation_index(cls, scope_paths: list[str]) -> None:
        normalized_scope_paths = sorted(
            {
                normalized
                for item in scope_paths
                for normalized in [str(item).strip().strip("/")]
                if normalized
            }
        )
        if not normalized_scope_paths:
            return

        previous_rows = MemoryMetadataRepository.list_navigation_rows_for_scope(normalized_scope_paths)
        MemoryMetadataRepository.delete_navigation_index_by_scope(normalized_scope_paths)
        for (user_id, level), doc_ids in cls._group_doc_ids(previous_rows).items():
            cls._write_vector_documents(user_id=user_id, level=level, documents=[], stale_doc_ids=doc_ids)

    @classmethod
    def search_l0(cls, user_id: str, query: str, include_types: list[str], top_k: int) -> list[L0VectorHit]:
        vector = cls._build_vector_store(user_id=user_id, level=FIND_L0_LEVEL)
        if not cls._collection_exists(vector):
            return []
        documents = vector.search_by_vector(
            query,
            user_id=user_id,
            top_k=top_k,
            score_threshold=config.MEMORY_FIND_L0_MIN_SCORE,
        )
        hits = [cls._document_to_l0_hit(item) for item in documents]
        return cls._post_filter_types(hits, include_types)

    @classmethod
    def load_l1_by_branch_paths(
        cls,
        user_id: str,
        branch_paths: list[str],
        include_types: list[str],
    ) -> list[L1BranchHit]:
        if not branch_paths:
            return []
        rows = MemoryMetadataRepository.list_l1_navigation_rows_by_branch_paths(
            user_id=user_id,
            branch_paths=branch_paths,
            include_types=include_types or None,
        )
        return [
            L1BranchHit(
                branch_path=item["branch_path"],
                file_path=item["file_path"],
                memory_type=item["memory_type"],
                content=item["abstract_text"],
                source_l0_score=0.0,
                updated_at=item.get("memory_updated_at"),
                tags=item.get("tags") or [],
            )
            for item in rows
            if item.get("abstract_text")
        ]

    @classmethod
    def _build_embedding_provider(cls) -> DefaultEmbeddingProvider:
        return DefaultEmbeddingProvider(model_name=f"{config.embedding_provider_name}/{config.embedding_model_name}")

    @classmethod
    def _build_vector_store(cls, user_id: str, level: Literal["l0", "l1"]) -> Vector:
        return Vector(
            spec=cls._build_vector_spec(user_id=user_id, level=level),
            embedding_provider=cls._build_embedding_provider(),
        )

    @classmethod
    def _build_vector_spec(cls, user_id: str, level: Literal["l0", "l1"]) -> VectorStoreSpec:
        return VectorStoreSpec(collection_name=cls._collection_name_for_user_level(user_id=user_id, level=level))

    @classmethod
    def _collection_name_for_user_level(cls, user_id: str, level: Literal["l0", "l1"]) -> str:
        normalized_user_id = re.sub(r"[^a-zA-Z0-9_]+", "_", str(user_id).strip()).strip("_") or "anonymous"
        return f"{config.MEMORY_FIND_VECTOR_COLLECTION_PREFIX}_{level}_{normalized_user_id}".lower()

    @classmethod
    def _collect_navigation_rows(
        cls,
        scope_path: str,
        task_id: str,
        expected_user_id: str | None = None,
    ) -> list[NavigationIndexSourceRow]:
        from runtime.memory.navigation.navigation_manager import NavigationManager

        _ = task_id
        tree = CommittedMemoryTree.build_tree(path=scope_path, include_dirs=True, include_content=True, max_depth=None)
        rows: list[NavigationIndexSourceRow] = []
        for item in tree.get("tree") or []:
            if item.get("type") != "file":
                continue
            file_path = str(item.get("path") or "")
            if not file_path.endswith(("/overview.md", "/summary.md")):
                continue
            metadata, body = parse_markdown_document(item.get("content") or "")
            content = str(body or "").strip()
            if not content:
                continue
            scope_type, resolved_user_id = NavigationManager._resolve_scope(file_path)
            if scope_type == "unknown" or not resolved_user_id:
                continue
            cls._validate_scope_user(path=file_path, expected_user_id=expected_user_id)
            memory_level = NavigationManager._resolve_memory_level(file_path)
            if memory_level not in {FIND_L0_LEVEL, FIND_L1_LEVEL}:
                continue
            updated_at = metadata.get("updated_at")
            rows.append(
                NavigationIndexSourceRow(
                    memory_id=metadata.get("memory_id") or f"mem_{sha256(file_path.encode('utf-8')).hexdigest()[:16]}",
                    user_id=resolved_user_id,
                    project_id=metadata.get("project_id"),
                    memory_type=NavigationManager._resolve_memory_type(file_path),
                    memory_level=memory_level,
                    branch_path=file_path.rsplit("/", 1)[0],
                    file_path=file_path,
                    abstract_text=content,
                    tags=list(metadata.get("tags") or []),
                    memory_updated_at=str(updated_at) if updated_at else None,
                    vector_doc_id=build_find_navigation_doc_id(
                        user_id=resolved_user_id,
                        file_path=file_path,
                        updated_at=str(updated_at) if updated_at else None,
                    ),
                )
            )
        return rows

    @staticmethod
    def _build_vector_documents(rows: list[NavigationIndexSourceRow]) -> list[Document]:
        return [
            Document(
                content=item.abstract_text,
                metadata={
                    "doc_id": item.vector_doc_id,
                    "user_id": item.user_id,
                    "project_id": item.project_id,
                    "memory_type": item.memory_type,
                    "memory_level": item.memory_level,
                    "branch_path": item.branch_path,
                    "file_path": item.file_path,
                    "updated_at": item.memory_updated_at,
                    "tags": item.tags,
                },
            )
            for item in rows
        ]

    @classmethod
    def _write_vector_documents(
        cls,
        user_id: str,
        level: Literal["l0", "l1"],
        documents: list[Document],
        stale_doc_ids: list[str],
    ) -> None:
        vector = cls._build_vector_store(user_id=user_id, level=level)
        if stale_doc_ids and cls._collection_exists(vector):
            vector.delete_by_ids(stale_doc_ids)
        if documents:
            vector.add_texts(documents)

    @staticmethod
    def _post_filter_types(rows: list[L0VectorHit], include_types: list[str]) -> list[L0VectorHit]:
        if not include_types:
            return rows
        allowed = {item.strip().lower() for item in include_types if item.strip()}
        return [item for item in rows if item.memory_type.lower() in allowed]

    @staticmethod
    def _document_to_l0_hit(document: Document) -> L0VectorHit:
        metadata = document.metadata or {}
        return L0VectorHit(
            branch_path=str(metadata.get("branch_path") or ""),
            file_path=str(metadata.get("file_path") or ""),
            memory_type=str(metadata.get("memory_type") or "unknown"),
            content=document.content,
            score=float(metadata.get("score") or 0.0),
            updated_at=str(metadata.get("updated_at")) if metadata.get("updated_at") is not None else None,
            tags=list(metadata.get("tags") or []),
        )

    @staticmethod
    def _collection_exists(vector: Vector) -> bool:
        processor = getattr(vector, "_vector_processor", None)
        client = getattr(processor, "client", None)
        collection_name = getattr(processor, "collection_name", None)
        has_collection = getattr(client, "has_collection", None)
        if callable(has_collection) and collection_name:
            return bool(has_collection(collection_name))
        return True

    @staticmethod
    def _group_rows(rows: list[NavigationIndexSourceRow]) -> dict[tuple[str, str], list[NavigationIndexSourceRow]]:
        grouped: dict[tuple[str, str], list[NavigationIndexSourceRow]] = defaultdict(list)
        for item in rows:
            grouped[(item.user_id, item.memory_level)].append(item)
        return grouped

    @staticmethod
    def _group_doc_ids(rows: list[dict]) -> dict[tuple[str, str], list[str]]:
        grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
        for item in rows:
            user_id = str(item.get("user_id") or "").strip()
            memory_level = str(item.get("memory_level") or "").strip()
            vector_doc_id = str(item.get("vector_doc_id") or "").strip()
            if user_id and memory_level and vector_doc_id:
                grouped[(user_id, memory_level)].append(vector_doc_id)
        return grouped

    @staticmethod
    def _validate_scope_user(*, path: str, expected_user_id: str | None) -> None:
        if not expected_user_id:
            return
        parts = [part for part in str(path).split("/") if part]
        resolved_user_id = parts[1] if len(parts) >= 2 and parts[0] == "users" else None
        if resolved_user_id != expected_user_id:
            raise ValueError(f"path user mismatch for {path}: {resolved_user_id} != {expected_user_id}")


def build_find_navigation_doc_id(user_id: str, file_path: str, updated_at: str | None) -> str:
    raw = f"find-nav::{user_id}::{file_path}::{updated_at or ''}"
    return sha256(raw.encode("utf-8")).hexdigest()[:32]
