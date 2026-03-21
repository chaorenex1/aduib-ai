from __future__ import annotations

from runtime.entities.protocol_entities import ExternalProtocol
from runtime.protocol.egress import (
    AnthropicToOpenAIEgressAdapter,
    AnthropicToResponsesEgressAdapter,
    EgressAdapter,
    IdentityEgressAdapter,
    OpenAIToAnthropicEgressAdapter,
    OpenAIToResponsesEgressAdapter,
    ResponsesToAnthropicEgressAdapter,
    ResponsesToOpenAIEgressAdapter,
)
from runtime.protocol.ingress import (
    AnthropicToOpenAIIngressAdapter,
    AnthropicToResponsesIngressAdapter,
    IdentityIngressAdapter,
    IngressAdapter,
    OpenAIToAnthropicIngressAdapter,
    OpenAIToResponsesIngressAdapter,
    ResponsesToAnthropicIngressAdapter,
    ResponsesToOpenAIIngressAdapter,
)


class ProtocolAdapterRegistry:
    """Lookup table for request and response protocol adapters."""

    _ingress_adapters: dict[tuple[ExternalProtocol, ExternalProtocol], IngressAdapter] = {
        (ExternalProtocol.OPENAI_CHAT, ExternalProtocol.OPENAI_CHAT): IdentityIngressAdapter(ExternalProtocol.OPENAI_CHAT),
        (
            ExternalProtocol.ANTHROPIC_MESSAGES,
            ExternalProtocol.ANTHROPIC_MESSAGES,
        ): IdentityIngressAdapter(ExternalProtocol.ANTHROPIC_MESSAGES),
        (
            ExternalProtocol.OPENAI_RESPONSES,
            ExternalProtocol.OPENAI_RESPONSES,
        ): IdentityIngressAdapter(ExternalProtocol.OPENAI_RESPONSES),
        (ExternalProtocol.OPENAI_CHAT, ExternalProtocol.ANTHROPIC_MESSAGES): OpenAIToAnthropicIngressAdapter(),
        (ExternalProtocol.ANTHROPIC_MESSAGES, ExternalProtocol.OPENAI_CHAT): AnthropicToOpenAIIngressAdapter(),
        (ExternalProtocol.OPENAI_CHAT, ExternalProtocol.OPENAI_RESPONSES): OpenAIToResponsesIngressAdapter(),
        (ExternalProtocol.OPENAI_RESPONSES, ExternalProtocol.OPENAI_CHAT): ResponsesToOpenAIIngressAdapter(),
        (ExternalProtocol.ANTHROPIC_MESSAGES, ExternalProtocol.OPENAI_RESPONSES): AnthropicToResponsesIngressAdapter(),
        (ExternalProtocol.OPENAI_RESPONSES, ExternalProtocol.ANTHROPIC_MESSAGES): ResponsesToAnthropicIngressAdapter(),
    }

    _egress_adapters: dict[tuple[ExternalProtocol, ExternalProtocol], EgressAdapter] = {
        (ExternalProtocol.OPENAI_CHAT, ExternalProtocol.OPENAI_CHAT): IdentityEgressAdapter(ExternalProtocol.OPENAI_CHAT),
        (
            ExternalProtocol.ANTHROPIC_MESSAGES,
            ExternalProtocol.ANTHROPIC_MESSAGES,
        ): IdentityEgressAdapter(ExternalProtocol.ANTHROPIC_MESSAGES),
        (
            ExternalProtocol.OPENAI_RESPONSES,
            ExternalProtocol.OPENAI_RESPONSES,
        ): IdentityEgressAdapter(ExternalProtocol.OPENAI_RESPONSES),
        (ExternalProtocol.ANTHROPIC_MESSAGES, ExternalProtocol.OPENAI_CHAT): AnthropicToOpenAIEgressAdapter(),
        (ExternalProtocol.OPENAI_CHAT, ExternalProtocol.ANTHROPIC_MESSAGES): OpenAIToAnthropicEgressAdapter(),
        (ExternalProtocol.OPENAI_RESPONSES, ExternalProtocol.OPENAI_CHAT): ResponsesToOpenAIEgressAdapter(),
        (ExternalProtocol.OPENAI_CHAT, ExternalProtocol.OPENAI_RESPONSES): OpenAIToResponsesEgressAdapter(),
        (ExternalProtocol.ANTHROPIC_MESSAGES, ExternalProtocol.OPENAI_RESPONSES): AnthropicToResponsesEgressAdapter(),
        (ExternalProtocol.OPENAI_RESPONSES, ExternalProtocol.ANTHROPIC_MESSAGES): ResponsesToAnthropicEgressAdapter(),
    }

    @classmethod
    def get_ingress_adapter(
        cls,
        source_protocol: ExternalProtocol,
        target_protocol: ExternalProtocol,
    ) -> IngressAdapter:
        return cls._ingress_adapters[(source_protocol, target_protocol)]

    @classmethod
    def get_egress_adapter(
        cls,
        source_protocol: ExternalProtocol,
        target_protocol: ExternalProtocol,
    ) -> EgressAdapter:
        return cls._egress_adapters[(source_protocol, target_protocol)]
