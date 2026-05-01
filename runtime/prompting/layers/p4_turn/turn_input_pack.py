from runtime.prompting._helpers import build_section, dump_data, get_extra
from runtime.prompting.contracts.context import PromptContext
from runtime.prompting.contracts.section import PromptSection

SOURCE = "runtime.prompting.layers.p4_turn.turn_input_pack"


def build_current_date_section(context: PromptContext) -> PromptSection:
    return build_section(
        section_id="current_date",
        title="Current Date",
        channel="user_meta",
        cache_policy="volatile",
        content=context.current_date,
        source=SOURCE,
    )


def build_session_goal_section(context: PromptContext) -> PromptSection | None:
    if not context.session_goal:
        return None
    return build_section(
        section_id="session_goal",
        title="Session Goal",
        channel="user_meta",
        cache_policy="session",
        content=context.session_goal,
        source=SOURCE,
    )


def build_turn_goal_section(context: PromptContext) -> PromptSection | None:
    if not context.turn_goal:
        return None
    return build_section(
        section_id="turn_goal",
        title="Turn Goal",
        channel="user_meta",
        cache_policy="volatile",
        content=context.turn_goal,
        source=SOURCE,
    )


def build_language_section(context: PromptContext) -> PromptSection | None:
    if not context.language:
        return None
    return build_section(
        section_id="language",
        title="Language",
        channel="system",
        cache_policy="session",
        content=f"Respond in {context.language} unless the user asks to switch.",
        source=SOURCE,
    )


def build_output_style_section(context: PromptContext) -> PromptSection | None:
    if not context.output_style:
        return None
    return build_section(
        section_id="output_style",
        title="Output Style",
        channel="system",
        cache_policy="session",
        content=context.output_style,
        source=SOURCE,
    )


def build_env_info_section(context: PromptContext) -> PromptSection | None:
    env_info = get_extra(context, "env_info")
    if not env_info:
        return None
    return build_section(
        section_id="env_info",
        title="Environment Info",
        channel="system",
        cache_policy="session",
        content=dump_data(env_info),
        source=SOURCE,
    )


def build_session_guidance_section(context: PromptContext) -> PromptSection | None:
    guidance = get_extra(context, "session_guidance")
    if not guidance:
        return None
    return build_section(
        section_id="session_guidance",
        title="Session Guidance",
        channel="system",
        cache_policy="session",
        content=dump_data(guidance),
        source=SOURCE,
    )


def build_scratchpad_section(context: PromptContext) -> PromptSection | None:
    scratchpad_path = get_extra(context, "scratchpad_path")
    if not scratchpad_path:
        return None
    return build_section(
        section_id="scratchpad",
        title="Scratchpad",
        channel="system",
        cache_policy="session",
        content=f"Use scratchpad files under: {scratchpad_path}",
        source=SOURCE,
    )


def build_token_budget_section(context: PromptContext) -> PromptSection | None:
    token_budget = get_extra(context, "token_budget")
    if not token_budget:
        return None
    return build_section(
        section_id="token_budget",
        title="Token Budget",
        channel="system",
        cache_policy="volatile",
        content=dump_data(token_budget),
        source=SOURCE,
    )


def build_brief_section(context: PromptContext) -> PromptSection | None:
    brief_enabled = get_extra(context, "brief_enabled")
    if not brief_enabled:
        return None
    return build_section(
        section_id="brief",
        title="Brief Mode",
        channel="system",
        cache_policy="volatile",
        content="Keep the response brief unless correctness or risk requires more detail.",
        source=SOURCE,
    )


def build_frc_section(context: PromptContext) -> PromptSection | None:
    frc = get_extra(context, "frc")
    if not frc:
        return None
    return build_section(
        section_id="frc",
        title="Function Result Clearing",
        channel="system",
        cache_policy="session",
        content=dump_data(frc),
        source=SOURCE,
    )


def build_summarize_tool_results_section(context: PromptContext) -> PromptSection | None:
    summarize = get_extra(context, "summarize_tool_results")
    if not summarize:
        return None
    content = (
        summarize
        if isinstance(summarize, str)
        else "Summarize important tool results before they scroll out of context."
    )
    return build_section(
        section_id="summarize_tool_results",
        title="Summarize Tool Results",
        channel="system",
        cache_policy="session",
        content=content,
        source=SOURCE,
    )


def build_plan_state_section(context: PromptContext) -> PromptSection | None:
    plan_state = get_extra(context, "plan_state")
    if not plan_state:
        return None
    return build_section(
        section_id="plan_state",
        title="Plan State",
        channel="user_meta",
        cache_policy="volatile",
        content=dump_data(plan_state),
        source=SOURCE,
    )


def build_team_context_section(context: PromptContext) -> PromptSection | None:
    team_context = get_extra(context, "team_context")
    if not team_context:
        return None
    return build_section(
        section_id="team_context",
        title="Team Context",
        channel="user_meta",
        cache_policy="volatile",
        content=dump_data(team_context),
        source=SOURCE,
    )


def build_recent_decisions_section(context: PromptContext) -> PromptSection | None:
    if not context.recent_decisions:
        return None
    return build_section(
        section_id="recent_decisions",
        title="Recent Decisions",
        channel="user_meta",
        cache_policy="session",
        content="\n".join(context.recent_decisions),
        source=SOURCE,
    )


def build_mcp_instructions_section(context: PromptContext) -> PromptSection | None:
    instructions = get_extra(context, "mcp_instructions")
    if not instructions:
        return None
    return build_section(
        section_id="mcp_instructions",
        title="MCP Instructions",
        channel="system",
        cache_policy="volatile",
        content=dump_data(instructions),
        source=SOURCE,
    )
