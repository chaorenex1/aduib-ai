from runtime.prompting.contracts.attachment import PromptAttachment
from runtime.prompting.contracts.compiled import RenderedMessage


def _escape_boundary(text: str, tag_name: str) -> str:
    return text.replace(f"</{tag_name}>", f"<\\/{tag_name}>").replace(f"<{tag_name}", f"<_{tag_name}")


class AttachmentRenderer:
    def render(self, attachments: list[PromptAttachment]) -> list[RenderedMessage]:
        rendered: list[RenderedMessage] = []
        for attachment in sorted(attachments, key=lambda item: (-item.priority, item.attachment_id)):
            content_body = _escape_boundary(attachment.content, "attachment")
            content = (
                f'<attachment id="{attachment.attachment_id}" type="{attachment.attachment_type}">\n'
                f"{content_body}\n"
                "</attachment>"
            )
            rendered.append(RenderedMessage(role="user", content=content, is_meta=True, source=attachment.source))
        return rendered
