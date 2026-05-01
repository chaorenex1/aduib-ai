from runtime.prompting._helpers import build_section
from runtime.prompting.contracts.context import PromptContext
from runtime.prompting.contracts.section import PromptSection

SOURCE = "runtime.prompting.layers.p1_modes.agent"


def build_agent_contract_section(context: PromptContext) -> PromptSection:
    content = (
        "Agent mode owns the execute-verify loop. Decide whether the next step needs direct action, a reusable skill, "
        "an MCP capability, or a delegated subagent, then verify the result before moving on."
    )
    return build_section(
        section_id="agent_contract",
        title="Agent Contract",
        channel="system",
        cache_policy="static",
        content=content,
        source=SOURCE,
    )
