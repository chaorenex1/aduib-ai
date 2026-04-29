"""Unified memory runtime package."""

from .committed_tree import CommittedMemoryTree, MemoryTreeError

__all__ = [
    "CommittedMemoryTree",
    "MemoryFindIndex",
    "MemoryFindReranker",
    "MemoryFindRuntime",
    "MemorySearchL2Reader",
    "MemorySearchPromptBuilder",
    "MemorySearchReranker",
    "MemorySearchRuntime",
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
    if name == "MemorySearchRuntime":
        from .search import MemorySearchRuntime

        return MemorySearchRuntime
    if name == "MemorySearchPromptBuilder":
        from .search_prompt import MemorySearchPromptBuilder

        return MemorySearchPromptBuilder
    if name == "MemorySearchL2Reader":
        from .search_l2 import MemorySearchL2Reader

        return MemorySearchL2Reader
    if name == "MemorySearchReranker":
        from .search_rerank import MemorySearchReranker

        return MemorySearchReranker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
