from __future__ import annotations

import json
import logging

from runtime.entities.llm_entities import ChatCompletionRequest
from runtime.memory.base.contracts import (
    GenerateNavigationSummaryPhaseResult,
    MemoryWritePipelineContext,
    NavigationDocumentPlan,
    NavigationSummaryBranchPlan,
)
from runtime.model_manager import ModelManager

from .common import read_current_branch_files, read_existing_navigation_docs
from .prompts import build_navigation_summary_messages

logger = logging.getLogger(__name__)


def generate_navigation_summary(context: MemoryWritePipelineContext) -> dict:
    staged = context.phase_results.get("build_staged_write_set") or {}
    navigation_targets = staged.get("navigation_targets") or []
    mutation_lookup = {
        item.get("target_path"): item
        for item in staged.get("memory_mutations") or []
        if isinstance(item, dict) and item.get("target_path")
    }
    plans: list[NavigationSummaryBranchPlan] = []
    for target in navigation_targets:
        branch_path = str(target.get("branch_path") or "").strip()
        if not branch_path:
            continue
        existing_docs = read_existing_navigation_docs(branch_path)
        branch_files = read_current_branch_files(branch_path, mutation_lookup=mutation_lookup)
        raw = _invoke_navigation_model(
            messages=build_navigation_summary_messages(
                task_id=context.task_id,
                branch_path=branch_path,
                existing_overview_md=existing_docs.get("overview_md"),
                existing_summary_md=existing_docs.get("summary_md"),
                branch_files=branch_files,
            ),
            user=context.user_id,
        )
        payload = _load_json_payload(raw)
        plans.append(
            _normalize_navigation_plan(
                payload=payload,
                branch_path=branch_path,
                existing_overview_md=existing_docs.get("overview_md"),
                existing_summary_md=existing_docs.get("summary_md"),
            )
        )
    result = GenerateNavigationSummaryPhaseResult(
        task_id=context.task_id,
        navigation_mutations=plans,
    )
    return result.model_dump(mode="python", exclude_none=True)


def _invoke_navigation_model(*, messages: list, user: str | None) -> str:
    try:
        model_manager = ModelManager()
        model_instance = model_manager.get_planner_model_instance() or model_manager.get_default_model_instance("llm")
    except Exception as exc:
        logger.warning("navigation summary model unavailable: %s", exc)
        return ""
    if model_instance is None:
        return ""

    request = ChatCompletionRequest(
        model=model_instance.model,
        messages=messages,
        temperature=0.0,
        stream=False,
    )
    response = model_instance.invoke_llm_sync(
        prompt_messages=request,
        user=user,
    )
    return str(response.message.content or "").strip()


def _load_json_payload(raw_text: str) -> dict:
    text = str(raw_text or "").strip()
    if not text:
        raise ValueError("navigation summary output is empty")
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
    raise ValueError("navigation summary output is not valid JSON")


def _normalize_navigation_plan(
    *,
    payload: dict,
    branch_path: str,
    existing_overview_md: str | None,
    existing_summary_md: str | None,
) -> NavigationSummaryBranchPlan:
    plan = NavigationSummaryBranchPlan.model_validate(payload)
    if plan.branch_path != branch_path:
        raise ValueError(f"navigation summary branch_path mismatch: {plan.branch_path} != {branch_path}")
    _validate_document_plan(
        document_name="overview",
        plan=plan.overview,
        expected_path=f"{branch_path}/overview.md",
        existing_markdown=existing_overview_md,
    )
    _validate_document_plan(
        document_name="summary",
        plan=plan.summary,
        expected_path=f"{branch_path}/summary.md",
        existing_markdown=existing_summary_md,
    )
    return plan


def _validate_document_plan(
    *,
    document_name: str,
    plan: NavigationDocumentPlan,
    expected_path: str,
    existing_markdown: str | None,
) -> None:
    if plan.path != expected_path:
        raise ValueError(f"{document_name} path mismatch: {plan.path} != {expected_path}")
    if plan.op == "noop" and plan.markdown_body:
        raise ValueError(f"{document_name} noop must not include markdown_body")
    if existing_markdown is None and plan.op == "edit":
        raise ValueError(f"{document_name} cannot edit without existing markdown")
    if existing_markdown is not None and plan.op == "write":
        raise ValueError(f"{document_name} cannot write when existing markdown is present")
    if existing_markdown is None and plan.based_on_existing:
        raise ValueError(f"{document_name} cannot be based_on_existing without existing markdown")
    if existing_markdown is not None and plan.op in {"edit", "noop"} and not plan.based_on_existing:
        raise ValueError(f"{document_name} must declare based_on_existing when editing existing markdown")
