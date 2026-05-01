from runtime.prompting.contracts.section import PromptSection


class SystemRenderer:
    def render(self, sections: list[PromptSection]) -> str:
        blocks: list[str] = []
        for section in sections:
            blocks.append(f"## {section.title}\n{section.content}".strip())
        return "\n\n".join(blocks).strip()
