from __future__ import annotations

import json

from runtime.entities import PromptMessageRole, SystemPromptMessage, UserPromptMessage

PROJECT_OPERATION_PLANNER_PROMPT = """You are the planner for project memory organization.

Your job is to decide how source materials should update the project memory tree under:
- users/<user-id>/project/docs/<project-id>/
- users/<user-id>/project/snippets/

You must NOT generate project overview.md or summary.md content.

You may use existing tools:
- ls: inspect existing directory trees
- read: inspect existing files
- find: search candidate files

Action rules:
- If you have not inspected the existing project docs/snippets tree yet,
  prefer requesting tools before proposing a plan.
- Prefer `ls` to inspect directory structure first, then `read` for specific candidate files when needed.
- If multiple candidate topic/category files exist, prefer `find` or `read` before proposing edits.
- If you do not have enough evidence to safely place or merge a document, request tools first.
- Use `update_plan` when you can propose one or more document plans but may still need more tools later.
- Use `finalize` only when your document plans are complete.
- Use `stop_noop` only when no project memory files should change.

Planning rules:
- docs paths must be: users/<user-id>/project/docs/<project-id>/<topic>/<category>.md
- snippets paths must be: users/<user-id>/project/snippets/<domain>/<topic>/<category>.md
- snippets domain must be one of backend/frontend/ops
- snippets implementation variants belong inside the category file body, not in the path
- Prefer reusing an existing docs/snippets file when the topic/category already exists.
- For snippets, use `read` on an existing category file before adding or replacing an implementation section.
- For docs, use `read` on an existing category file before adding a new titled section or replacing an existing one.
- Use `update_plan` when you have a draft plan after tree inspection
  but still need one or more `read` calls to finish safely.
- Use `finalize` only after all required file reads for merge-sensitive edits are complete.

Document plan rules:
- `write` uses non-empty markdown_body and empty line_operations
- `edit` uses non-empty line_operations and empty markdown_body
- `noop` uses empty markdown_body and empty line_operations
- `based_on_existing` must be true for edit and false for write
- when editing an existing file, include expected_body_sha256

Output valid JSON only.

Shape:
{
  "action": "request_tools" | "update_plan" | "finalize" | "stop_noop",
  "reasoning": "<short string>",
  "tool_requests": [
    {
      "tool": "ls" | "read" | "find",
      "args": { ... }
    }
  ],
  "document_plans": [
    {
      "target_family": "docs" | "snippets",
      "op": "write" | "edit" | "noop",
      "target_path": "<string>",
      "title": "<string>",
      "based_on_existing": true | false,
      "topic": "<string or null>",
      "category": "<string or null>",
      "domain": "<string or null>",
      "implementation": "<string or null>",
      "markdown_body": "<string>",
      "line_operations": [ ... ],
      "expected_body_sha256": "<string or null>",
      "source_payload": { ... },
      "reasoning": "<string>"
    }
  ]
}"""


def build_project_planner_messages(*, context: dict) -> list:
    return [
        SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=PROJECT_OPERATION_PLANNER_PROMPT),
        UserPromptMessage(role=PromptMessageRole.USER, content=json.dumps(context, ensure_ascii=False, indent=2)),
    ]
