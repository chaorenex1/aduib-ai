from runtime.prompting._helpers import build_section
from runtime.prompting.contracts.context import PromptContext
from runtime.prompting.contracts.section import PromptSection

SOURCE = "runtime.prompting.layers.p3_session.document_working_set"


def build_tracked_documents_section(context: PromptContext) -> PromptSection | None:
    if not context.tracked_documents:
        return None
    content = [
        f"{item.document_id}: path={item.path}; role={item.role}"
        + (f"; summary={item.summary}" if item.summary else "")
        for item in context.tracked_documents
    ]
    return build_section(
        section_id="tracked_documents",
        title="Tracked Documents",
        channel="user_meta",
        cache_policy="session",
        content="\n".join(content),
        source=SOURCE,
    )


def build_document_summaries_section(context: PromptContext) -> PromptSection | None:
    items = [item for item in context.tracked_documents if item.summary]
    if not items:
        return None
    content = [f"{item.path}: {item.summary}" for item in items]
    return build_section(
        section_id="document_summaries",
        title="Document Summaries",
        channel="user_meta",
        cache_policy="session",
        content="\n".join(content),
        source=SOURCE,
    )


def build_active_focus_spans_section(context: PromptContext) -> PromptSection | None:
    if not context.active_focus_spans:
        return None
    content = []
    for span in context.active_focus_spans:
        bounds = []
        if span.start is not None:
            bounds.append(f"start={span.start}")
        if span.end is not None:
            bounds.append(f"end={span.end}")
        if span.label:
            bounds.append(f"label={span.label}")
        content.append(f"{span.document_id}: " + ", ".join(bounds or ["active"]))
    return build_section(
        section_id="active_focus_spans",
        title="Active Focus Spans",
        channel="user_meta",
        cache_policy="session",
        content="\n".join(content),
        source=SOURCE,
    )


def build_pending_operations_section(context: PromptContext) -> PromptSection | None:
    if not context.pending_operations:
        return None
    content = [
        f"{item.operation_id}: type={item.operation_type}; status={item.status}; {item.summary}"
        for item in context.pending_operations
    ]
    return build_section(
        section_id="pending_operations",
        title="Pending Operations",
        channel="user_meta",
        cache_policy="session",
        content="\n".join(content),
        source=SOURCE,
    )


def build_applied_operations_section(context: PromptContext) -> PromptSection | None:
    if not context.applied_operations:
        return None
    content = [
        f"{item.operation_id}: type={item.operation_type}; status={item.status}; {item.summary}"
        for item in context.applied_operations
    ]
    return build_section(
        section_id="applied_operations",
        title="Applied Operations",
        channel="user_meta",
        cache_policy="session",
        content="\n".join(content),
        source=SOURCE,
    )


def build_artifact_refs_section(context: PromptContext) -> PromptSection | None:
    if not context.artifact_refs:
        return None
    return build_section(
        section_id="artifact_refs",
        title="Artifact References",
        channel="user_meta",
        cache_policy="session",
        content="\n".join(context.artifact_refs),
        source=SOURCE,
    )
