from runtime.prompting._helpers import build_section
from runtime.prompting.contracts.context import PromptContext
from runtime.prompting.contracts.section import PromptSection

SOURCE = "runtime.prompting.layers.p1_modes.chat"


def build_chat_contract_section(context: PromptContext) -> PromptSection:
    content = (
        "Chat mode is answer-first. Default to analysis, explanation, and scoped advice. "
        "Do not start execution workflows, tool chains, or subagent orchestration "
        "unless the request explicitly changes mode."
    )
    return build_section(
        section_id="chat_contract",
        title="Chat Contract",
        channel="system",
        cache_policy="static",
        content=content,
        source=SOURCE,
    )
