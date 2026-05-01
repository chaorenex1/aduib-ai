from runtime.entities.anthropic_entities import AnthropicMessage, AnthropicMessageRequest, AnthropicSystemBlock
from runtime.prompting.contracts.compiled import CompiledPrompt


class AnthropicMessagesPromptAdapter:
    def apply(self, request: AnthropicMessageRequest, compiled: CompiledPrompt) -> AnthropicMessageRequest:
        if compiled.system_text.strip():
            if isinstance(request.system, str):
                request.system = (
                    f"{compiled.system_text}\n\n{request.system}".strip() if request.system else compiled.system_text
                )
            elif isinstance(request.system, list):
                request.system = [AnthropicSystemBlock(text=compiled.system_text), *request.system]
            else:
                request.system = compiled.system_text

        request.messages = request.messages or []
        user_meta = [AnthropicMessage(role="user", content=item.content) for item in compiled.user_meta_messages]
        attachments = [AnthropicMessage(role="user", content=item.content) for item in compiled.attachment_messages]
        history = list(request.messages)
        latest_user = None
        if history and getattr(history[-1], "role", None) == "user":
            latest_user = history[-1]
            history = history[:-1]
        request.messages = [*user_meta, *history, *attachments, *([latest_user] if latest_user is not None else [])]
        return request
