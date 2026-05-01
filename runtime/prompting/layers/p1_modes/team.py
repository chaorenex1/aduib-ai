from runtime.prompting._helpers import build_section
from runtime.prompting.contracts.context import PromptContext
from runtime.prompting.contracts.section import PromptSection

SOURCE = "runtime.prompting.layers.p1_modes.team"


def build_team_contract_section(context: PromptContext) -> PromptSection:
    content = (
        "Team mode is coordinator-first. Split work into bounded lanes, collect worker outputs, "
        "and synthesize the final result "
        "without losing task ownership or verification discipline."
    )
    return build_section(
        section_id="team_contract",
        title="Team Contract",
        channel="system",
        cache_policy="static",
        content=content,
        source=SOURCE,
    )
