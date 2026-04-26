from __future__ import annotations

import json

from runtime.entities import PromptMessageRole, SystemPromptMessage, UserPromptMessage
from runtime.memory.project.examples import DOCS_INFERENCE_EXAMPLES, SNIPPET_INFERENCE_EXAMPLES

DOCS_CLASSIFICATION_PROMPT = """Infer a stable project-docs topic and category.

Rules:
- Output `topic` and `category`, not a full path.
- Reuse existing project-doc topics/categories when possible.
- `topic` is the long-lived subject cluster.
- `category` is the document type within that topic.
- Use existing document summaries to avoid near-duplicate categories.
- Prefer updating an existing `topic/category` file when the material adds detail to the same category.
- The file body should support multiple titled sections under the same category file.
- Avoid inventing a new category when the material is just another subtopic or example of the same category.
- Do not output arbitrary directories.
- Prefer stable topic reuse over creating near-duplicate topics.
- Return JSON only.
"""


SNIPPETS_CLASSIFICATION_PROMPT = """Infer a stable project-snippet domain, topic, and category.

Rules:
- Domain must be one of: backend, frontend, ops.
- Output `domain`, `topic`, and `category`, not a full path.
- `category` is the algorithm/pattern/approach file.
- Implementation variants belong inside the file body, not in the path.
- Also output `implementation` as the variant label that should become a section inside the category file.
- Reuse an existing category file when the algorithm/pattern is the same, even if the implementation differs.
- Never create a different category solely because the implementation backend differs.
- Prefer reusing an existing category file and adding/updating the implementation section inside it.
- Reuse existing domain/topic/category when possible.
- Return JSON only.
"""


def build_docs_classification_messages(*, context: dict) -> list:
    payload = {"examples": DOCS_INFERENCE_EXAMPLES, "context": context}
    return [
        SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=DOCS_CLASSIFICATION_PROMPT),
        UserPromptMessage(role=PromptMessageRole.USER, content=json.dumps(payload, ensure_ascii=False, indent=2)),
    ]


def build_snippets_classification_messages(*, context: dict) -> list:
    payload = {"examples": SNIPPET_INFERENCE_EXAMPLES, "context": context}
    return [
        SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=SNIPPETS_CLASSIFICATION_PROMPT),
        UserPromptMessage(role=PromptMessageRole.USER, content=json.dumps(payload, ensure_ascii=False, indent=2)),
    ]
