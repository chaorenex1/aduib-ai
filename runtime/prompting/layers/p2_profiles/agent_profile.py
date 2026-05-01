from runtime.prompting._helpers import build_section, get_extra
from runtime.prompting.contracts.context import PromptContext
from runtime.prompting.contracts.profile import PromptProfile
from runtime.prompting.contracts.section import PromptSection

SOURCE = "runtime.prompting.layers.p2_profiles.agent_profile"


def build_profile_identity_section(context: PromptContext, profile: PromptProfile) -> PromptSection:
    agent_name = get_extra(context, "agent_name")
    title = profile.title if not agent_name else f"{profile.title} ({agent_name})"
    description = profile.description or "Use the active profile to shape task decisions."
    return build_section(
        section_id="profile_identity",
        title="Profile Identity",
        channel="system",
        cache_policy="session",
        content=f"{title}\n\n{description}",
        source=SOURCE,
    )


def build_profile_rules_section(context: PromptContext, profile: PromptProfile) -> PromptSection | None:
    blocks: list[str] = []
    if profile.system_blocks:
        blocks.extend(profile.system_blocks)
    prompt_template = get_extra(context, "prompt_template")
    if prompt_template:
        blocks.append(str(prompt_template).strip())
    if not blocks:
        return None
    return build_section(
        section_id="profile_rules",
        title="Profile Rules",
        channel="system",
        cache_policy="session",
        content="\n\n".join(block for block in blocks if block),
        source=SOURCE,
    )


def build_workflow_charter_section(context: PromptContext, profile: PromptProfile) -> PromptSection | None:
    charter = get_extra(context, "workflow_charter") or profile.workflow_charter
    if not charter:
        return None
    return build_section(
        section_id="workflow_charter",
        title="Workflow Charter",
        channel="system",
        cache_policy="session",
        content=charter,
        source=SOURCE,
    )


def build_profile_output_contract_section(context: PromptContext, profile: PromptProfile) -> PromptSection | None:
    output_contract = get_extra(context, "output_contract") or profile.output_contract_name
    if not output_contract:
        return None
    return build_section(
        section_id="profile_output_contract",
        title="Profile Output Contract",
        channel="system",
        cache_policy="session",
        content=f"Follow the active output contract: {output_contract}.",
        source=SOURCE,
    )


def build_profile_examples_section(context: PromptContext, profile: PromptProfile) -> PromptSection | None:
    examples = profile.examples
    if not examples:
        return None
    return build_section(
        section_id="profile_examples",
        title="Profile Examples",
        channel="system",
        cache_policy="session",
        content="\n\n".join(examples),
        source=SOURCE,
    )
