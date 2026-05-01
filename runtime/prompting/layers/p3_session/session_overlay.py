from runtime.prompting._helpers import build_section, dump_data, get_extra
from runtime.prompting.contracts.context import PromptContext
from runtime.prompting.contracts.section import PromptSection

SOURCE = "runtime.prompting.layers.p3_session.session_overlay"


def build_workspace_rules_section(context: PromptContext) -> PromptSection | None:
    rules = get_extra(context, "workspace_rules")
    if not rules:
        return None
    return build_section(
        section_id="workspace_rules",
        title="Workspace Rules",
        channel="system",
        cache_policy="session",
        content=rules,
        source=SOURCE,
    )


def build_memory_state_section(context: PromptContext) -> PromptSection | None:
    memory_state = get_extra(context, "memory_state")
    if not memory_state:
        return None
    return build_section(
        section_id="memory_state",
        title="Memory State",
        channel="system",
        cache_policy="session",
        content=dump_data(memory_state),
        source=SOURCE,
    )


def build_runtime_capabilities_section(context: PromptContext) -> PromptSection | None:
    capabilities = {
        "tools": context.runtime_capabilities.tools,
        "skills": context.runtime_capabilities.skills,
        "mcp_servers": context.runtime_capabilities.mcp_servers,
        "subagent_types": context.runtime_capabilities.subagent_types,
        "execution_topology": get_extra(context, "execution_topology"),
    }
    if not any(value for value in capabilities.values()):
        return None
    return build_section(
        section_id="runtime_capabilities",
        title="Runtime Capabilities",
        channel="system",
        cache_policy="session",
        content=dump_data(capabilities),
        source=SOURCE,
    )


def build_permission_state_section(context: PromptContext) -> PromptSection | None:
    if not context.permission_mode and not get_extra(context, "high_risk_gate"):
        return None
    content = {
        "permission_mode": context.permission_mode,
        "high_risk_gate": get_extra(context, "high_risk_gate"),
    }
    return build_section(
        section_id="permission_state",
        title="Permission State",
        channel="system",
        cache_policy="session",
        content=dump_data(content),
        source=SOURCE,
    )
