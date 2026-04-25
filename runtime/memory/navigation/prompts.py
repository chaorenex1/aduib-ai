from __future__ import annotations

import json

from runtime.entities import PromptMessageRole, SystemPromptMessage, UserPromptMessage
from runtime.memory.base.contracts import NavigationBranchFileState

NAVIGATION_SUMMARY_PROMPT = """You are the navigation-summary generator
for a memory branch.

Your task is to produce the next L0/L1 navigation documents for one branch.

Definitions:
- L0 = overview.md
- L1 = summary.md

You are given:
- the branch path
- the current final branch files after memory writes have already been applied
- the existing overview.md content if it already exists
- the existing summary.md content if it already exists

Rules:
- Work on exactly one branch per call.
- Use the current final branch files as the primary factual source.
- If `existing_overview_md` exists, you MUST use it as an edit baseline/reference.
- If `existing_summary_md` exists, you MUST use it as an edit baseline/reference.
- If an existing navigation document is present, prefer `edit` or `noop`; do not rewrite blindly.
- If an existing navigation document is absent, prefer `write` or `noop`.
- `overview.path` must equal `<branch_path>/overview.md`.
- `summary.path` must equal `<branch_path>/summary.md`.
- If `op` is `noop`, `markdown_body` must be an empty string.
- Never output paths outside the provided branch.
- Never invent files or facts that are not grounded in the provided branch files.

Output ONLY valid JSON.
No markdown.
No code fences.
No explanation outside the JSON object.

Required output shape:
{
  "branch_path": "<string>",
  "overview": {
    "op": "write" | "edit" | "noop",
    "path": "<branch_path>/overview.md",
    "markdown_body": "<string>",
    "based_on_existing": true | false
  },
  "summary": {
    "op": "write" | "edit" | "noop",
    "path": "<branch_path>/summary.md",
    "markdown_body": "<string>",
    "based_on_existing": true | false
  }
}"""


def build_navigation_summary_messages(
    *,
    task_id: str,
    branch_path: str,
    existing_overview_md: str | None,
    existing_summary_md: str | None,
    branch_files: list[NavigationBranchFileState],
) -> list:
    payload = {
        "task_id": task_id,
        "branch_path": branch_path,
        "existing_overview_md": existing_overview_md,
        "existing_summary_md": existing_summary_md,
        "branch_files": [item.model_dump(mode="python", exclude_none=True) for item in branch_files],
    }
    return [
        SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=NAVIGATION_SUMMARY_PROMPT),
        UserPromptMessage(
            role=PromptMessageRole.USER,
            content=json.dumps(payload, ensure_ascii=False, indent=2),
        ),
    ]
