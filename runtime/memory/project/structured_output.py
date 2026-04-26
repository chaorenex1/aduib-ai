from __future__ import annotations

import json
from typing import Any

from runtime.memory.base.contracts import PlannerToolRequest
from runtime.memory.project.contracts import ProjectDocumentPlan, ProjectPlannerAction
from runtime.memory.project.enums import ProjectSnippetDomain


def load_json_payload(raw_text: str) -> dict[str, Any]:
    text = str(raw_text or "").strip()
    if not text:
        raise ValueError("project inference output is empty")
    candidates = [text]
    start_index = text.find("{")
    end_index = text.rfind("}")
    if start_index != -1 and end_index != -1 and end_index > start_index:
        candidates.append(text[start_index : end_index + 1])
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise ValueError("project inference output is not a JSON object")


def normalize_docs_inference(value: dict[str, Any]) -> dict[str, str]:
    topic = str(value.get("topic") or "").strip()
    category = str(value.get("category") or "").strip()
    if not topic or not category:
        raise ValueError("docs inference requires topic and category")
    return {
        "topic": topic,
        "category": category,
        "strategy": str(value.get("strategy") or "llm").strip() or "llm",
    }


def normalize_snippets_inference(value: dict[str, Any]) -> dict[str, str]:
    domain = str(value.get("domain") or "").strip().lower()
    topic = str(value.get("topic") or "").strip()
    category = str(value.get("category") or "").strip()
    implementation = str(value.get("implementation") or "").strip()
    if domain not in {item.value for item in ProjectSnippetDomain}:
        raise ValueError("snippets inference requires a valid domain")
    if not topic or not category:
        raise ValueError("snippets inference requires topic and category")
    if not implementation:
        raise ValueError("snippets inference requires implementation")
    return {
        "domain": domain,
        "topic": topic,
        "category": category,
        "implementation": implementation,
        "strategy": str(value.get("strategy") or "llm").strip() or "llm",
    }


def normalize_project_planner_action(value: dict[str, Any]) -> ProjectPlannerAction:
    payload = dict(value)
    tool_requests = payload.get("tool_requests") or []
    payload["tool_requests"] = [
        PlannerToolRequest.model_validate(item) for item in tool_requests if isinstance(item, dict)
    ]
    document_plans = payload.get("document_plans") or []
    payload["document_plans"] = [
        ProjectDocumentPlan.model_validate(item) for item in document_plans if isinstance(item, dict)
    ]
    return ProjectPlannerAction.model_validate(payload)
