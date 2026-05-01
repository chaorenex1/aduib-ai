from __future__ import annotations

from runtime.entities.anthropic_entities import AnthropicMessage, AnthropicTextBlock, AnthropicToolResultBlock
from service.agent.contracts import AgentApprovalDecision, AgentToolResult


class InputNormalizer:
    @staticmethod
    def normalize_user_text(user_text: str) -> AnthropicMessage:
        return AnthropicMessage(role="user", content=str(user_text).strip())

    @staticmethod
    def normalize_client_tool_results(tool_results: list[AgentToolResult]) -> AnthropicMessage:
        blocks = [
            AnthropicToolResultBlock(
                tool_use_id=item.tool_use_id,
                content=item.output,
                is_error=item.is_error,
            )
            for item in tool_results
        ]
        return AnthropicMessage(role="user", content=blocks)

    @staticmethod
    def normalize_approval_decision(approval_decision: AgentApprovalDecision) -> AnthropicMessage:
        decision = "approved" if approval_decision.approved else "denied"
        reason = f" Reason: {approval_decision.reason}." if approval_decision.reason else ""
        return AnthropicMessage(
            role="user",
            content=[
                AnthropicTextBlock(
                    text=(
                        f"Tool approval decision for {approval_decision.tool_name} "
                        f"({approval_decision.tool_use_id}): {decision}.{reason}"
                    )
                )
            ],
        )
