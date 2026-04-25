from __future__ import annotations

from component.storage.base_storage import storage_manager
from runtime.memory.committed_tree import CommittedMemoryTree
from runtime.memory.prepare_context.common import (
    AGENT_PREFETCH_PATH_TEMPLATES,
    SUMMARY_FILE_MAX_CHARS,
    SUMMARY_FILENAMES,
    USER_PREFETCH_PATH_TEMPLATES,
    describe_summary_file,
    directory_entry_from_raw,
    to_scoped_storage_path,
)
from runtime.memory.prepare_context.types import (
    BranchSummaryRecord,
    DirectoryTreeResult,
    DirectoryViewRecord,
    FileReadRecord,
    PrefetchTreeNode,
    PreparedPrefetchContext,
)


class StaticPrefetchBuilder:
    def __init__(self, *, user_id: str | None, agent_id: str | None) -> None:
        self.user_id = user_id
        self.agent_id = agent_id

    def build(self) -> PreparedPrefetchContext:
        branch_paths = self._prefetch_branch_paths()
        directory_views = [self._build_directory_view(path) for path in branch_paths]
        file_reads = self._read_branch_summary_files(branch_paths)
        branch_summaries = self._build_branch_summaries(file_reads)
        return PreparedPrefetchContext(
            directory_views=directory_views,
            file_reads=file_reads,
            already_read_paths=sorted({item.path for item in file_reads}),
            directory_tree=DirectoryTreeResult(
                roots=[
                    root
                    for view in directory_views
                    if view.exists and view.directory_tree is not None
                    for root in view.directory_tree.roots
                ]
            ),
            branch_summaries=branch_summaries,
        )

    def _prefetch_branch_paths(self) -> list[str]:
        paths: list[str] = []
        if self.user_id:
            paths.extend(path.format(user_id=self.user_id) for path in USER_PREFETCH_PATH_TEMPLATES)
        if self.agent_id:
            paths.extend(path.format(agent_id=self.agent_id) for path in AGENT_PREFETCH_PATH_TEMPLATES)
        return paths

    def _build_directory_view(self, path: str) -> DirectoryViewRecord:
        raw_view = CommittedMemoryTree.list_entries(
            path=path,
            recursive=False,
            include_files=True,
            include_dirs=True,
            max_results=50,
        )
        exists = storage_manager.exists(to_scoped_storage_path(path))
        directory_tree = DirectoryTreeResult(roots=[self._build_directory_subtree(path)]) if exists else None
        return DirectoryViewRecord(
            path=str(raw_view.get("path") or path),
            entries=[directory_entry_from_raw(item) for item in raw_view.get("entries") or []],
            total=int(raw_view.get("total") or 0),
            truncated=bool(raw_view.get("truncated")),
            committed_view=bool(raw_view.get("committed_view", True)),
            exists=exists,
            directory_tree=directory_tree,
        )

    def _build_directory_subtree(self, root_path: str) -> PrefetchTreeNode:
        raw_tree = CommittedMemoryTree.list_entries(
            path=root_path,
            recursive=True,
            include_files=False,
            include_dirs=True,
            max_results=200,
        )
        root = PrefetchTreeNode(path=root_path)
        for entry in sorted(raw_tree.get("entries") or [], key=lambda item: str(item.get("path") or "")):
            entry_path = str(entry.get("path") or "").strip()
            if not entry_path or entry_path == root_path or str(entry.get("type") or "") != "dir":
                continue
            if not entry_path.startswith(f"{root_path}/"):
                continue
            self._insert_tree_path(root, entry_path)
        return root

    def _insert_tree_path(self, root: PrefetchTreeNode, entry_path: str) -> None:
        current = root
        current_path = root.path
        relative_parts = [part for part in entry_path[len(root.path) :].strip("/").split("/") if part]
        for part in relative_parts:
            current_path = f"{current_path}/{part}"
            child = next((item for item in current.children if item.path == current_path), None)
            if child is None:
                child = PrefetchTreeNode(path=current_path)
                current.children.append(child)
                current.children.sort(key=lambda item: item.path)
            current = child

    def _read_branch_summary_files(self, branch_paths: list[str]) -> list[FileReadRecord]:
        reads: list[FileReadRecord] = []
        for branch_path in branch_paths:
            for filename in SUMMARY_FILENAMES:
                summary_record = self._read_summary_file(branch_path=branch_path, filename=filename)
                if summary_record is not None:
                    reads.append(summary_record)
        return reads

    def _read_summary_file(self, *, branch_path: str, filename: str) -> FileReadRecord | None:
        file_path = f"{branch_path}/{filename}"
        if not storage_manager.exists(to_scoped_storage_path(file_path)):
            return None
        raw_read = CommittedMemoryTree.read_file(
            path=file_path,
            max_chars=SUMMARY_FILE_MAX_CHARS,
            include_metadata=True,
        )
        branch_path_value, scope_type, memory_type, summary_level = describe_summary_file(file_path)
        return FileReadRecord(
            path=str(raw_read.get("path") or file_path),
            content=str(raw_read.get("content") or ""),
            line_start=raw_read.get("line_start"),
            line_end=raw_read.get("line_end"),
            truncated=bool(raw_read.get("truncated")),
            committed_view=bool(raw_read.get("committed_view", True)),
            metadata=raw_read.get("metadata") or {},
            branch_path=branch_path_value,
            scope_type=scope_type,
            memory_type=memory_type,
            summary_level=summary_level,
        )

    def _build_branch_summaries(self, file_reads: list[FileReadRecord]) -> list[BranchSummaryRecord]:
        summaries = [
            BranchSummaryRecord(
                branch_path=item.branch_path,
                scope_type=item.scope_type,
                memory_type=item.memory_type,
                summary_level=item.summary_level,
                file_path=item.path,
                content=item.content,
            )
            for item in file_reads
            if item.summary_level is not None
        ]
        return sorted(summaries, key=lambda item: (item.branch_path, item.summary_level, item.file_path))
