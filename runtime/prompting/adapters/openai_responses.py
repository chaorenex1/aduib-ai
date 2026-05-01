from runtime.agent.adapters.request_adapter import RequestAdapter
from runtime.entities.response_entities import ResponseInputItem, ResponseRequest
from runtime.prompting.contracts.compiled import CompiledPrompt


class OpenAIResponsesPromptAdapter:
    def apply(self, request: ResponseRequest, compiled: CompiledPrompt) -> ResponseRequest:
        if compiled.system_text.strip():
            request.instructions = (
                f"{compiled.system_text}\n\n{request.instructions}".strip()
                if request.instructions
                else compiled.system_text
            )

        existing_items = RequestAdapter.ensure_response_input_list(request)
        user_meta = [ResponseInputItem(role="user", content=item.content) for item in compiled.user_meta_messages]
        attachments = [ResponseInputItem(role="user", content=item.content) for item in compiled.attachment_messages]
        history = list(existing_items)
        latest_user = None
        if history and getattr(history[-1], "role", None) == "user":
            latest_user = history[-1]
            history = history[:-1]
        request.input = [*user_meta, *history, *attachments, *([latest_user] if latest_user is not None else [])]
        return request
