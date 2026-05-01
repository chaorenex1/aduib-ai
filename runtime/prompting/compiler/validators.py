from runtime.prompting.contracts.attachment import PromptAttachment
from runtime.prompting.contracts.context import PromptContext
from runtime.prompting.contracts.section import PromptSection


class PromptCompilerValidator:
    def validate_context(self, context: PromptContext) -> None:
        if not context.current_date:
            raise ValueError("PromptContext.current_date is required")
        if not context.latest_user_text and context.mode in {"plan", "agent", "team"}:
            # Allow empty text for tool follow-up turns, but keep the contract explicit.
            return

    def validate_sections(self, sections: list[PromptSection]) -> None:
        seen: set[str] = set()
        for section in sections:
            if section.section_id in seen:
                raise ValueError(f"Duplicate prompt section id: {section.section_id}")
            seen.add(section.section_id)

    def validate_attachments(self, attachments: list[PromptAttachment]) -> None:
        seen: set[str] = set()
        for attachment in attachments:
            if attachment.attachment_id in seen:
                raise ValueError(f"Duplicate prompt attachment id: {attachment.attachment_id}")
            seen.add(attachment.attachment_id)
