"""Unified memory runtime package."""

from .committed_tree import CommittedMemoryTree, MemoryTreeError

__all__ = [
    "CommittedMemoryTree",
    "MemoryFindIndex",
    "MemoryFindReranker",
    "MemoryFindRuntime",
    "MemoryTreeError",
]


def __getattr__(name: str):
    if name == "MemoryFindRuntime":
        from .find import MemoryFindRuntime

        return MemoryFindRuntime
    if name == "MemoryFindIndex":
        from .find_index import MemoryFindIndex

        return MemoryFindIndex
    if name == "MemoryFindReranker":
        from .find_rerank import MemoryFindReranker

        return MemoryFindReranker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
