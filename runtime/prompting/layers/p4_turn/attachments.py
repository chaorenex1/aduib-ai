from runtime.prompting._helpers import build_attachment, get_extra
from runtime.prompting.contracts.attachment import PromptAttachment
from runtime.prompting.contracts.context import PromptContext

SOURCE = "runtime.prompting.layers.p4_turn.attachments"


def build_memory_attachment(context: PromptContext) -> PromptAttachment | None:
    content = get_extra(context, "memory_attachment")
    return build_attachment(
        attachment_id="memory",
        attachment_type="memory",
        content=content,
        source=SOURCE,
        priority=90,
        dedupe_key="memory",
    )


def build_nested_memory_attachments(context: PromptContext) -> list[PromptAttachment]:
    attachments = []
    for index, item in enumerate(get_extra(context, "nested_memories", [])):
        attachment = build_attachment(
            attachment_id=f"nested_memory_{index}",
            attachment_type="nested_memory",
            content=item,
            source=SOURCE,
            priority=80,
            dedupe_key=f"nested_memory:{index}",
        )
        if attachment:
            attachments.append(attachment)
    return attachments


def build_relevant_memories_attachment(context: PromptContext) -> PromptAttachment | None:
    content = get_extra(context, "relevant_memories")
    return build_attachment(
        attachment_id="relevant_memories",
        attachment_type="relevant_memories",
        content=content,
        source=SOURCE,
        priority=85,
        dedupe_key="relevant_memories",
    )


def build_skill_listing_attachment(context: PromptContext) -> PromptAttachment | None:
    content = get_extra(context, "skill_listing")
    return build_attachment(
        attachment_id="skill_listing",
        attachment_type="skill_listing",
        content=content,
        source=SOURCE,
        priority=40,
        dedupe_key="skill_listing",
    )


def build_skill_discovery_attachment(context: PromptContext) -> PromptAttachment | None:
    content = get_extra(context, "skill_discovery")
    return build_attachment(
        attachment_id="skill_discovery",
        attachment_type="skill_discovery",
        content=content,
        source=SOURCE,
        priority=45,
        dedupe_key="skill_discovery",
    )


def build_invoked_skills_attachment(context: PromptContext) -> PromptAttachment | None:
    content = get_extra(context, "invoked_skills")
    return build_attachment(
        attachment_id="invoked_skills",
        attachment_type="invoked_skills",
        content=content,
        source=SOURCE,
        priority=50,
        dedupe_key="invoked_skills",
    )


def build_mcp_instructions_delta_attachment(context: PromptContext) -> PromptAttachment | None:
    content = get_extra(context, "mcp_instructions_delta")
    return build_attachment(
        attachment_id="mcp_instructions_delta",
        attachment_type="mcp_instructions_delta",
        content=content,
        source=SOURCE,
        priority=60,
        dedupe_key="mcp_instructions_delta",
    )


def build_diagnostics_attachment(context: PromptContext) -> PromptAttachment | None:
    content = get_extra(context, "diagnostics")
    return build_attachment(
        attachment_id="diagnostics",
        attachment_type="diagnostics",
        content=content,
        source=SOURCE,
        priority=100,
        dedupe_key="diagnostics",
    )


def build_document_excerpt_attachments(context: PromptContext) -> list[PromptAttachment]:
    attachments = []
    for index, item in enumerate(get_extra(context, "document_excerpts", [])):
        attachment = build_attachment(
            attachment_id=f"document_excerpt_{index}",
            attachment_type="document_excerpt",
            content=item,
            source=SOURCE,
            priority=70,
            dedupe_key=f"document_excerpt:{index}",
        )
        if attachment:
            attachments.append(attachment)
    return attachments


def build_document_change_attachment(context: PromptContext) -> PromptAttachment | None:
    content = get_extra(context, "document_change")
    return build_attachment(
        attachment_id="document_change",
        attachment_type="document_change",
        content=content,
        source=SOURCE,
        priority=65,
        dedupe_key="document_change",
    )


def build_queued_command_attachment(context: PromptContext) -> PromptAttachment | None:
    content = get_extra(context, "queued_command")
    return build_attachment(
        attachment_id="queued_command",
        attachment_type="queued_command",
        content=content,
        source=SOURCE,
        priority=90,
        dedupe_key="queued_command",
    )


def build_task_notification_attachment(context: PromptContext) -> PromptAttachment | None:
    content = get_extra(context, "task_notification")
    return build_attachment(
        attachment_id="task_notification",
        attachment_type="task_notification",
        content=content,
        source=SOURCE,
        priority=90,
        dedupe_key="task_notification",
    )


def build_plan_reminder_attachment(context: PromptContext) -> PromptAttachment | None:
    content = get_extra(context, "plan_reminder")
    return build_attachment(
        attachment_id="plan_reminder",
        attachment_type="plan_reminder",
        content=content,
        source=SOURCE,
        priority=75,
        dedupe_key="plan_reminder",
    )


def build_team_mailbox_attachment(context: PromptContext) -> PromptAttachment | None:
    content = get_extra(context, "team_mailbox")
    return build_attachment(
        attachment_id="team_mailbox",
        attachment_type="team_mailbox",
        content=content,
        source=SOURCE,
        priority=95,
        dedupe_key="team_mailbox",
    )


def build_permission_delta_attachment(context: PromptContext) -> PromptAttachment | None:
    content = get_extra(context, "permission_delta")
    return build_attachment(
        attachment_id="permission_delta",
        attachment_type="permission_delta",
        content=content,
        source=SOURCE,
        priority=85,
        dedupe_key="permission_delta",
    )


def build_capability_delta_attachment(context: PromptContext) -> PromptAttachment | None:
    content = get_extra(context, "capability_delta")
    return build_attachment(
        attachment_id="capability_delta",
        attachment_type="capability_delta",
        content=content,
        source=SOURCE,
        priority=85,
        dedupe_key="capability_delta",
    )
