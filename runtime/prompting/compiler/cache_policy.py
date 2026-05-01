from runtime.prompting.contracts.compiled import CacheSegments
from runtime.prompting.contracts.section import PromptSection


class CachePolicyPlanner:
    def split(self, system_sections: list[PromptSection]) -> CacheSegments:
        segments = CacheSegments()
        for section in system_sections:
            if section.cache_policy == "static":
                segments.stable_system_sections.append(section.section_id)
            elif section.cache_policy == "session":
                segments.session_system_sections.append(section.section_id)
            else:
                segments.volatile_system_sections.append(section.section_id)
        return segments
