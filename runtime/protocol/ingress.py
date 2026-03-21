from __future__ import annotations

from abc import ABC, abstractmethod

from runtime.entities.protocol_entities import AnyProtocolRequest, ExternalProtocol
from runtime.protocol._openai_anthropic import anthropic_to_openai, openai_to_anthropic
from runtime.protocol._openai_responses import openai_to_responses, responses_to_openai


class IngressAdapter(ABC):
    """Converts an ingress request into the provider-facing request shape."""

    source_protocol: ExternalProtocol
    target_protocol: ExternalProtocol

    @abstractmethod
    def adapt(self, req: AnyProtocolRequest) -> AnyProtocolRequest:
        raise NotImplementedError


class IdentityIngressAdapter(IngressAdapter):
    def __init__(self, protocol: ExternalProtocol) -> None:
        self.source_protocol = protocol
        self.target_protocol = protocol

    def adapt(self, req: AnyProtocolRequest) -> AnyProtocolRequest:
        return req


class OpenAIToAnthropicIngressAdapter(IngressAdapter):
    source_protocol = ExternalProtocol.OPENAI_CHAT
    target_protocol = ExternalProtocol.ANTHROPIC_MESSAGES

    def adapt(self, req: AnyProtocolRequest) -> AnyProtocolRequest:
        return openai_to_anthropic(req)


class AnthropicToOpenAIIngressAdapter(IngressAdapter):
    source_protocol = ExternalProtocol.ANTHROPIC_MESSAGES
    target_protocol = ExternalProtocol.OPENAI_CHAT

    def adapt(self, req: AnyProtocolRequest) -> AnyProtocolRequest:
        return anthropic_to_openai(req)


class OpenAIToResponsesIngressAdapter(IngressAdapter):
    source_protocol = ExternalProtocol.OPENAI_CHAT
    target_protocol = ExternalProtocol.OPENAI_RESPONSES

    def adapt(self, req: AnyProtocolRequest) -> AnyProtocolRequest:
        return openai_to_responses(req)


class ResponsesToOpenAIIngressAdapter(IngressAdapter):
    source_protocol = ExternalProtocol.OPENAI_RESPONSES
    target_protocol = ExternalProtocol.OPENAI_CHAT

    def adapt(self, req: AnyProtocolRequest) -> AnyProtocolRequest:
        return responses_to_openai(req)


class AnthropicToResponsesIngressAdapter(IngressAdapter):
    source_protocol = ExternalProtocol.ANTHROPIC_MESSAGES
    target_protocol = ExternalProtocol.OPENAI_RESPONSES

    def adapt(self, req: AnyProtocolRequest) -> AnyProtocolRequest:
        return openai_to_responses(anthropic_to_openai(req))


class ResponsesToAnthropicIngressAdapter(IngressAdapter):
    source_protocol = ExternalProtocol.OPENAI_RESPONSES
    target_protocol = ExternalProtocol.ANTHROPIC_MESSAGES

    def adapt(self, req: AnyProtocolRequest) -> AnyProtocolRequest:
        return openai_to_anthropic(responses_to_openai(req))
