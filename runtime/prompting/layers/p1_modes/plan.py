from runtime.prompting._helpers import build_section
from runtime.prompting.contracts.context import PromptContext
from runtime.prompting.contracts.section import PromptSection

SOURCE = "runtime.prompting.layers.p1_modes.plan"


def build_plan_contract_section(context: PromptContext) -> PromptSection:
    content = (
        "Plan mode clarifies goals, constraints, risks, and verification shape before implementation. "
        "Prefer producing an explicit plan artifact and keep execution suggestions "
        "bounded to what the approved plan requires."
    )
    return build_section(
        section_id="plan_contract",
        title="Plan Contract",
        channel="system",
        cache_policy="static",
        content=content,
        source=SOURCE,
    )
