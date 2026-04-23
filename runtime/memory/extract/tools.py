from __future__ import annotations

from typing import Any

from runtime.memory.committed_tree import CommittedMemoryTree

SUPPORTED_PLANNER_TOOLS = ("ls", "read", "find")


def execute_planner_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    tool_name = str(name or "").strip().lower()
    if tool_name == "ls":
        return CommittedMemoryTree.list_entries(
            path=str(args.get("path") or ""),
            recursive=bool(args.get("recursive", False)),
            include_files=bool(args.get("include_files", True)),
            include_dirs=bool(args.get("include_dirs", True)),
            max_results=int(args.get("max_results") or 50),
        )
    if tool_name == "read":
        return CommittedMemoryTree.read_file(
            path=str(args.get("path") or ""),
            start_line=args.get("start_line"),
            end_line=args.get("end_line"),
            max_chars=int(args.get("max_chars") or 8_000),
            include_metadata=True,
        )
    if tool_name == "find":
        return CommittedMemoryTree.search_content(
            query=str(args.get("query") or ""),
            path=str(args.get("path") or ""),
            glob_pattern=args.get("glob_pattern"),
            max_results=int(args.get("max_results") or 10),
        )
    raise ValueError(f"unsupported planner tool: {name}")
