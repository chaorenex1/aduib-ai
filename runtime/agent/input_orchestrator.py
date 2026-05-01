from __future__ import annotations

from runtime.agent.adapters.request_adapter import RequestAdapter
from runtime.agent.input_normalizer import InputNormalizer
from runtime.entities.anthropic_entities import AnthropicMessageRequest
from service.agent.contracts import AgentMessagesCommand, AgentMessageTurnCommand, ResolvedAgentInput


class InputOrchestrator:
    @classmethod
    def build_from_messages(cls, request: AgentMessagesCommand) -> ResolvedAgentInput:
        latest_input = request.request.messages[-1]
        return ResolvedAgentInput(
            request=request.request.model_copy(deep=True),
            latest_input=latest_input,
            latest_user_text=RequestAdapter(request.request).latest_user_text(),
        )

    @classmethod
    def build_from_message_turn(
        cls,
        request: AgentMessageTurnCommand,
        *,
        history_messages,
    ) -> ResolvedAgentInput:
        if request.user_text is not None and request.user_text.strip():
            latest_input = InputNormalizer.normalize_user_text(request.user_text)
        elif request.tool_results:
            latest_input = InputNormalizer.normalize_client_tool_results(request.tool_results)
        else:
            latest_input = InputNormalizer.normalize_approval_decision(request.approval_decision)

        payload = AnthropicMessageRequest(
            model=request.model,
            messages=[*history_messages, latest_input],
            system=request.system,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
            top_k=request.top_k,
            stream=request.stream,
            stop_sequences=request.stop_sequences,
            thinking=request.thinking,
            output_config=request.output_config,
            metadata=request.metadata,
        )
        return ResolvedAgentInput(
            request=payload,
            latest_input=latest_input,
            latest_user_text=RequestAdapter(payload).latest_user_text(),
        )
