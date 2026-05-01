from runtime.entities.llm_entities import LLMRequest
from runtime.prompting.contracts.compiled import CompiledPrompt
from runtime.prompting.contracts.trace import PromptTrace
from runtime.prompting.integration.common import compile_prompt


def build_plan_first_turn(
    *, request: LLMRequest, session_state: dict[str, object] | None = None, extras: dict[str, object] | None = None
) -> tuple[CompiledPrompt, PromptTrace]:
    return compile_prompt(mode="plan", phase="first_turn", request=request, session_state=session_state, extras=extras)


def build_plan_continued_turn(
    *, request: LLMRequest, session_state: dict[str, object] | None = None, extras: dict[str, object] | None = None
) -> tuple[CompiledPrompt, PromptTrace]:
    return compile_prompt(
        mode="plan", phase="continued_turn", request=request, session_state=session_state, extras=extras
    )
