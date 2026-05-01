from runtime.prompting.contracts.section import PromptSection


class PrecedenceResolver:
    def merge_system_sections(self, *section_groups: list[PromptSection]) -> list[PromptSection]:
        return self.dedupe_sections([section for group in section_groups for section in group])

    def merge_user_meta_sections(self, *section_groups: list[PromptSection]) -> list[PromptSection]:
        return self.dedupe_sections([section for group in section_groups for section in group])

    def dedupe_sections(self, sections: list[PromptSection]) -> list[PromptSection]:
        ordered_ids: list[str] = []
        merged: dict[str, PromptSection] = {}
        for section in sections:
            if section.section_id not in merged:
                ordered_ids.append(section.section_id)
            merged[section.section_id] = section
        return [merged[section_id] for section_id in ordered_ids]
