from __future__ import annotations

import json
from typing import Any

from runtime.entities import PromptMessageRole, SystemPromptMessage, UserPromptMessage
from runtime.memory.apply.patch import compute_content_sha256, parse_markdown_document
from runtime.memory.base.contracts import NavigationBranchFileState

NAVIGATION_SUMMARY_PROMPT = """You are the navigation-summary planner for one memory branch.

Your task is to produce the next navigation change plan for exactly one branch.

Documents:
- overview.md
- summary.md

Important editing model:
- `write` means create a missing document with a full markdown body.
- `edit` means modify the EXISTING markdown body using minimal `line_operations`.
- `noop` means keep the document unchanged.

Body-editing scope:
- `line_operations` apply ONLY to the markdown body.
- Do NOT edit frontmatter.
- Do NOT regenerate the whole document for `edit`.
- Prefer the smallest reliable patch.
- If you cannot locate the change confidently, return `noop`.

Rules:
- Work on exactly one branch.
- Use the current final branch files as the factual source.
- For existing documents, prefer `edit` or `noop`.
- For missing documents, prefer `write` or `noop`.
- `path` must stay inside the provided branch.
- `overview.path` must equal `<branch_path>/overview.md`.
- `summary.path` must equal `<branch_path>/summary.md`.

Operation rules:
- For `write`:
  - `markdown_body` must be non-empty
  - `line_operations` must be empty
  - `based_on_existing` must be false
- For `edit`:
  - `markdown_body` must be empty
  - `line_operations` must be non-empty
  - `based_on_existing` must be true
  - `expected_body_sha256` must equal the provided body sha
- For `noop`:
  - `markdown_body` must be empty
  - `line_operations` must be empty

Line operation rules:
- Use only:
  - `replace_range`
  - `delete_range`
  - `insert_after`
  - `insert_before`
  - `append_eof`
- Prefer `anchor_text` for stability.
- Use 1-based body line numbers.
- Avoid near-full-document replacement unless absolutely necessary.

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
    "based_on_existing": true | false,
    "markdown_body": "<string>",
    "line_operations": [
      {
        "kind": "replace_range" | "delete_range" | "insert_after" | "insert_before" | "append_eof",
        "start_line": <integer or null>,
        "end_line": <integer or null>,
        "anchor_text": "<string or null>",
        "old_text": "<string or null>",
        "new_text": "<string or null>",
        "reasoning": "<short string>"
      }
    ],
    "expected_body_sha256": "<string or null>",
    "reasoning": "<short string>"
  },
  "summary": {
    "op": "write" | "edit" | "noop",
    "path": "<branch_path>/summary.md",
    "based_on_existing": true | false,
    "markdown_body": "<string>",
    "line_operations": [],
    "expected_body_sha256": "<string or null>",
    "reasoning": "<short string>"
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
        "existing_overview": _build_existing_navigation_payload(
            path=f"{branch_path}/overview.md",
            markdown=existing_overview_md,
        ),
        "existing_summary": _build_existing_navigation_payload(
            path=f"{branch_path}/summary.md",
            markdown=existing_summary_md,
        ),
        "branch_files": [item.model_dump(mode="python", exclude_none=True) for item in branch_files],
    }
    return [
        SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=NAVIGATION_SUMMARY_PROMPT),
        UserPromptMessage(
            role=PromptMessageRole.USER,
            content=json.dumps(payload, ensure_ascii=False, indent=2),
        ),
    ]


def _build_existing_navigation_payload(*, path: str, markdown: str | None) -> dict[str, Any] | None:
    if markdown is None:
        return None
    _metadata, body = parse_markdown_document(markdown)
    return {
        "path": path,
        "body_sha256": compute_content_sha256(body),
        "body_lines": [
            {"line": index, "text": line}
            for index, line in enumerate(str(body or "").splitlines(), start=1)
        ],
    }
