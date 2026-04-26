from __future__ import annotations

from typing import Any

from component.storage.base_storage import storage_manager
from configs import config
from runtime.memory.apply.patch import parse_markdown_document
from runtime.memory.project.contracts import ProjectMemoryScope


class ProjectMemoryContextBuilder:
    """
    Placeholder context collector for project-memory inference.

    This is intentionally isolated from the manager so future LLM-based
    topic/category inference can evolve without reworking controller/task
    plumbing.
    """

    def build_docs_context(
        self,
        *,
        scope: ProjectMemoryScope,
        item: dict[str, Any],
    ) -> dict[str, Any]:
        existing_topics: dict[str, list[dict[str, str]]] = {}
        scoped_docs_root = self._to_scoped_path(scope.project_docs_path)
        if self._storage_exists(scoped_docs_root):
            for entry in storage_manager.list_dir(scoped_docs_root, recursive=True):
                if not entry.is_file or not entry.path.endswith(".md"):
                    continue
                relative = entry.path.replace(scoped_docs_root.strip("/"), "", 1).strip("/")
                parts = [part for part in relative.split("/") if part]
                if len(parts) != 2:
                    continue
                topic, filename = parts
                category = filename.rsplit(".", 1)[0]
                title = category
                body_summary = ""
                try:
                    metadata, body = parse_markdown_document(storage_manager.read_text(entry.path))
                    title = str(metadata.get("title") or title).strip()
                    body_summary = body[:200].strip()
                except Exception:
                    pass
                existing_topics.setdefault(topic, []).append(
                    {
                        "category": category,
                        "title": title,
                        "body_summary": body_summary,
                    }
                )
        return {
            "project_docs_path": scope.project_docs_path,
            "item": item,
            "existing_topics": existing_topics,
        }

    def build_snippets_context(
        self,
        *,
        scope: ProjectMemoryScope,
        item: dict[str, Any],
    ) -> dict[str, Any]:
        existing_domains: dict[str, dict[str, list[dict[str, str]]]] = {}
        scoped_snippets_root = self._to_scoped_path(scope.snippets_path)
        if self._storage_exists(scoped_snippets_root):
            for entry in storage_manager.list_dir(scoped_snippets_root, recursive=True):
                if not entry.is_file or not entry.path.endswith(".md"):
                    continue
                relative = entry.path.replace(scoped_snippets_root.strip("/"), "", 1).strip("/")
                parts = [part for part in relative.split("/") if part]
                if len(parts) != 3:
                    continue
                domain, topic, filename = parts
                category = filename.rsplit(".", 1)[0]
                title = category
                body_summary = ""
                implementation_sections: list[str] = []
                try:
                    metadata, body = parse_markdown_document(storage_manager.read_text(entry.path))
                    title = str(metadata.get("title") or title).strip()
                    body_summary = body[:200].strip()
                    implementation_sections = self._extract_implementation_sections(body)
                except Exception:
                    pass
                existing_domains.setdefault(domain, {}).setdefault(topic, []).append(
                    {
                        "category": category,
                        "title": title,
                        "body_summary": body_summary,
                        "implementation_sections": implementation_sections,
                    }
                )
        return {
            "snippets_path": scope.snippets_path,
            "item": item,
            "existing_domains": existing_domains,
        }

    @staticmethod
    def _to_scoped_path(relative_path: str) -> str:
        return "/".join(part for part in [config.MEMORY_TREE_ROOT_DIR, relative_path] if part)

    @staticmethod
    def _storage_exists(path: str) -> bool:
        try:
            return storage_manager.exists(path)
        except RuntimeError:
            return False

    @staticmethod
    def _extract_implementation_sections(body: str) -> list[str]:
        sections: list[str] = []
        for line in str(body or "").splitlines():
            text = line.strip()
            if text.startswith("## "):
                sections.append(text[3:].strip())
        return sections
