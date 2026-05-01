from runtime.entities.llm_entities import ChatCompletionRequest
from runtime.entities.message_entities import PromptMessageRole, SystemPromptMessage, UserPromptMessage
from runtime.prompting.contracts.compiled import CompiledPrompt


class OpenAIChatPromptAdapter:
    def apply(self, request: ChatCompletionRequest, compiled: CompiledPrompt) -> ChatCompletionRequest:
        request.messages = request.messages or []
        existing_system = [
            message
            for message in request.messages
            if (getattr(getattr(message, "role", None), "value", None) or getattr(message, "role", None)) == "system"
        ]
        history = [
            message
            for message in request.messages
            if (getattr(getattr(message, "role", None), "value", None) or getattr(message, "role", None)) != "system"
        ]
        latest_user = None
        if (
            history
            and (getattr(getattr(history[-1], "role", None), "value", None) or getattr(history[-1], "role", None))
            == "user"
        ):
            latest_user = history[-1]
            history = history[:-1]

        messages = []
        if compiled.system_text.strip():
            messages.append(SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=compiled.system_text))
        messages.extend(existing_system)
        messages.extend(
            UserPromptMessage(role=PromptMessageRole.USER, content=item.content) for item in compiled.user_meta_messages
        )
        messages.extend(history)
        messages.extend(
            UserPromptMessage(role=PromptMessageRole.USER, content=item.content)
            for item in compiled.attachment_messages
        )
        if latest_user is not None:
            messages.append(latest_user)
        request.messages = messages
        return request
