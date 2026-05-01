from runtime.prompting.contracts.compiled import RenderedMessage
from runtime.prompting.contracts.section import PromptSection


def _escape_boundary(text: str, tag_name: str) -> str:
    return text.replace(f"</{tag_name}>", f"<\\/{tag_name}>").replace(f"<{tag_name}", f"<_{tag_name}")


class UserMetaRenderer:
    def render(self, sections: list[PromptSection]) -> list[RenderedMessage]:
        messages: list[RenderedMessage] = []
        for section in sections:
            content_body = _escape_boundary(section.content, "user-meta")
            content = f'<user-meta section="{section.section_id}">\n# {section.title}\n{content_body}\n</user-meta>'
            messages.append(RenderedMessage(role="user", content=content, is_meta=True, source=section.section_id))
        return messages
