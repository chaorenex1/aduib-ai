from runtime.prompting._helpers import build_section, get_extra
from runtime.prompting.contracts.context import PromptContext
from runtime.prompting.contracts.section import PromptSection

SOURCE = "runtime.prompting.layers.p0_platform.base"


def build_intro_section(context: PromptContext) -> PromptSection:
    platform_name = get_extra(context, "platform_name", "llm")
    runtime_name = get_extra(context, "runtime_name", "prompt-compiler")
    content = (
        f"You are operating inside {platform_name}. "
        f"This request is compiled by the {runtime_name} kernel for {context.mode} mode."
    )
    return build_section(
        section_id="intro",
        title="Intro",
        channel="system",
        cache_policy="static",
        content=content,
        source=SOURCE,
    )


def build_system_section(context: PromptContext) -> PromptSection:
    truth_policy = get_extra(context, "truth_policy", "Do not invent file reads, tool calls, or verification results.")
    instruction_policy = get_extra(
        context,
        "instruction_policy",
        "Follow higher-priority instructions, state uncertainty plainly, and keep reasoning grounded in evidence.",
    )
    return build_section(
        section_id="system",
        title="System",
        channel="system",
        cache_policy="static",
        content=f"{truth_policy}\n\n{instruction_policy}",
        source=SOURCE,
    )


def build_doing_tasks_section(context: PromptContext) -> PromptSection:
    work_style = get_extra(
        context,
        "work_style",
        (
            "Inspect the real code path first, then make the smallest correct change "
            "and verify it before claiming completion."
        ),
    )
    completion_bar = get_extra(
        context,
        "completion_bar",
        "A task is complete only when the requested outcome is implemented and supported by concrete verification.",
    )
    return build_section(
        section_id="doing_tasks",
        title="Doing Tasks",
        channel="system",
        cache_policy="static",
        content=f"{work_style}\n\n{completion_bar}",
        source=SOURCE,
    )


def build_actions_with_care_section(context: PromptContext) -> PromptSection:
    risk_policy = get_extra(
        context,
        "risk_policy",
        (
            "Treat destructive, irreversible, or production-affecting actions as high risk "
            "and prefer smaller reversible steps."
        ),
    )
    permission_policy = get_extra(
        context,
        "permission_policy",
        "When authority or confirmation is required, stop at the decision point and surface the exact risk.",
    )
    return build_section(
        section_id="actions_with_care",
        title="Actions With Care",
        channel="system",
        cache_policy="static",
        content=f"{risk_policy}\n\n{permission_policy}",
        source=SOURCE,
    )


def build_using_tools_section(context: PromptContext) -> PromptSection:
    tool_names = ", ".join(context.runtime_capabilities.tools) or "none"
    tool_policy = get_extra(
        context,
        "tool_result_policy",
        "Use tools only when they improve correctness, summarize the result, and avoid redundant calls.",
    )
    return build_section(
        section_id="using_tools",
        title="Using Tools",
        channel="system",
        cache_policy="session",
        content=f"Available tools: {tool_names}.\n\n{tool_policy}",
        source=SOURCE,
    )


def build_tone_style_section(context: PromptContext) -> PromptSection:
    default_tone = get_extra(context, "default_tone", "Concise, direct, and collaborative.")
    verbosity_policy = get_extra(
        context,
        "verbosity_policy",
        "Prefer evidence-dense answers over long narration; expand only when risk or ambiguity justifies it.",
    )
    return build_section(
        section_id="tone_style",
        title="Tone Style",
        channel="system",
        cache_policy="static",
        content=f"{default_tone}\n\n{verbosity_policy}",
        source=SOURCE,
    )


def build_output_efficiency_section(context: PromptContext) -> PromptSection:
    response_efficiency_policy = get_extra(
        context,
        "response_efficiency_policy",
        "Keep outputs structured and compact, but include the exact evidence needed to support implementation claims.",
    )
    return build_section(
        section_id="output_efficiency",
        title="Output Efficiency",
        channel="system",
        cache_policy="static",
        content=response_efficiency_policy,
        source=SOURCE,
    )
