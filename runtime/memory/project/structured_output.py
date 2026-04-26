from __future__ import annotations

import json
from typing import Any

from runtime.memory.base.contracts import PlannerToolRequest
from runtime.memory.project.contracts import ProjectDocumentPlan, ProjectPlannerAction


def load_json_payload(raw_text: str) -> dict[str, Any]:
    text = str(raw_text or "").strip()
    if not text:
        raise ValueError("project planner output is empty")
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
    raise ValueError("project planner output is not a JSON object")


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
