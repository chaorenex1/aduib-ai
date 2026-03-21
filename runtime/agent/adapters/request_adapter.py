from typing import Any

from runtime.agent.adapters.response_text_extractor import ResponseTextExtractor
from runtime.agent.memory.prompt_markup import sanitize_memory_markup
from runtime.entities import (
    AnthropicMessage,
    AnthropicMessageRequest,
    AnthropicMessageResponse,
    AnthropicTextBlock,
    AssistantPromptMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    LLMRequest,
    LLMResponse,
    PromptMessageRole,
    ResponseInputItem,
    ResponseOutput,
    ResponseOutputFunctionCallOutput,
    ResponseRequest,
    SystemPromptMessage,
    TextContentBlock,
    TextPromptMessageContent,
    UserPromptMessage,
)
from runtime.entities.anthropic_entities import AnthropicSystemBlock
from runtime.tool.base.tool import Tool


class RequestAdapter:
    def __init__(self, request: LLMRequest):
        self.request = request

    def latest_user_text(self) -> str:
        if isinstance(self.request, ChatCompletionRequest):
            for message in reversed(self.request.messages or []):
                if getattr(getattr(message, "role", None), "value", None) == "user":
                    return sanitize_memory_markup(ResponseTextExtractor.flatten_content(message.content))
            return ""
        if isinstance(self.request, AnthropicMessageRequest):
            for message in reversed(self.request.messages or []):
                if getattr(message, "role", None) == "user":
                    return sanitize_memory_markup(ResponseTextExtractor.flatten_content(message.content))
            return ""
        if isinstance(self.request, ResponseRequest):
            for item in reversed(self.ensure_response_input_list(self.request)):
                if getattr(item, "role", None) == "user":
                    return sanitize_memory_markup(ResponseTextExtractor.flatten_content(item.content))
        return ""

    def append_user_text(self, text: str) -> None:
        if isinstance(self.request, ChatCompletionRequest):
            self.request.messages = self.request.messages or []
            self.request.messages.append(UserPromptMessage(role=PromptMessageRole.USER, content=text))
        elif isinstance(self.request, AnthropicMessageRequest):
            self.request.messages = self.request.messages or []
            self.request.messages.append(AnthropicMessage(content=text, role="user"))
        elif isinstance(self.request, ResponseRequest):
            self.ensure_response_input_list(self.request).append(ResponseInputItem(content=text, role="user"))

    def append_assistant_text(self, text: str) -> None:
        if isinstance(self.request, ChatCompletionRequest):
            self.request.messages = self.request.messages or []
            self.request.messages.append(AssistantPromptMessage(content=text))
        elif isinstance(self.request, AnthropicMessageRequest):
            self.request.messages = self.request.messages or []
            self.request.messages.append(AnthropicMessage(role="assistant", content=[AnthropicTextBlock(text=text)]))
        elif isinstance(self.request, ResponseRequest):
            self.ensure_response_input_list(self.request).append(ResponseInputItem(role="assistant", content=text))

    def append_assistant_response(self, response: LLMResponse) -> None:
        if isinstance(self.request, ChatCompletionRequest) and isinstance(response, ChatCompletionResponse):
            self.request.messages = self.request.messages or []
            self.request.messages.append(response.message)
        elif isinstance(self.request, AnthropicMessageRequest) and isinstance(response, AnthropicMessageResponse):
            self.request.messages = self.request.messages or []
            self.request.messages.append(AnthropicMessage(role=response.role, content=response.content))
        elif isinstance(self.request, ResponseRequest) and isinstance(response, ResponseOutput):
            self.ensure_response_input_list(self.request).extend(
                self.normalize_response_output_to_input_items(response)
            )
        else:
            response_text = ResponseTextExtractor.from_response(response)
            if response_text:
                self.append_assistant_text(response_text)

    def prepend_system_prompt(self, prompt_template: str) -> None:
        prompt_template = str(prompt_template or "").strip()
        if not prompt_template:
            return

        if isinstance(self.request, ChatCompletionRequest):
            self.request.messages = self.request.messages or []
            existing_system_prompts = [
                ResponseTextExtractor.flatten_content(getattr(message, "content", None)).strip()
                for message in self.request.messages
                if (getattr(getattr(message, "role", None), "value", None) or getattr(message, "role", None))
                == "system"
            ]
            if prompt_template in existing_system_prompts:
                return
            self.request.messages.insert(
                0,
                SystemPromptMessage(role=PromptMessageRole.SYSTEM, content=prompt_template),
            )
            return

        if isinstance(self.request, AnthropicMessageRequest):
            if isinstance(self.request.system, str):
                existing_prompt = self.request.system.strip()
                if existing_prompt == prompt_template:
                    return
                self.request.system = f"{prompt_template}\n\n{existing_prompt}" if existing_prompt else prompt_template
                return

            if isinstance(self.request.system, list):
                existing_system_prompts = [
                    str(getattr(block, "text", "") or "").strip() for block in self.request.system
                ]
                if prompt_template in existing_system_prompts:
                    return
                self.request.system.insert(0, AnthropicSystemBlock(text=prompt_template))
                return

            self.request.system = prompt_template
            return

        if isinstance(self.request, ResponseRequest):
            existing_instructions = str(self.request.instructions or "").strip()
            if existing_instructions == prompt_template:
                return
            self.request.instructions = (
                f"{prompt_template}\n\n{existing_instructions}" if existing_instructions else prompt_template
            )

    def append_memory_block_to_latest_user(self, memory_block: str) -> None:
        injection = f"\n\n{memory_block}"
        if isinstance(self.request, ChatCompletionRequest):
            for message in reversed(self.request.messages or []):
                if getattr(getattr(message, "role", None), "value", None) != "user":
                    continue
                if isinstance(message.content, str) or message.content is None:
                    message.content = f"{ResponseTextExtractor.flatten_content(message.content)}{injection}".strip()
                elif isinstance(message.content, list):
                    message.content.append(TextPromptMessageContent(text=injection))
                return
        elif isinstance(self.request, AnthropicMessageRequest):
            for message in reversed(self.request.messages or []):
                if getattr(message, "role", None) != "user":
                    continue
                if isinstance(message.content, str):
                    message.content = f"{message.content}{injection}".strip()
                elif isinstance(message.content, list):
                    message.content.append(AnthropicTextBlock(text=injection))
                return
        elif isinstance(self.request, ResponseRequest):
            for item in reversed(self.ensure_response_input_list(self.request)):
                if getattr(item, "role", None) != "user":
                    continue
                if isinstance(item.content, str):
                    item.content = f"{item.content}{injection}".strip()
                elif isinstance(item.content, list):
                    item.content.append(TextContentBlock(text=injection))
                return

    def append_observation_prompt(self, text: str) -> None:
        self.append_user_text(text)

    def pop_last_message(self) -> None:
        if isinstance(self.request, ChatCompletionRequest) or isinstance(self.request, AnthropicMessageRequest):
            if self.request.messages:
                self.request.messages.pop()
        elif isinstance(self.request, ResponseRequest):
            input_items = self.ensure_response_input_list(self.request)
            if input_items:
                input_items.pop()

    def ensure_tools(self, tools: list[Tool]) -> None:
        real_tools = [tool for tool in (tools or []) if hasattr(tool, "entity")]
        if not real_tools:
            return
        if isinstance(self.request, ChatCompletionRequest):
            self.request.tools = [tool.entity.convert_to_openai_tool() for tool in real_tools]
        elif isinstance(self.request, AnthropicMessageRequest):
            self.request.tools = [tool.entity.convert_to_anthropic_tool() for tool in real_tools]
        elif isinstance(self.request, ResponseRequest):
            self.request.tools = [tool.entity.convert_to_response_tool() for tool in real_tools]

    @staticmethod
    def ensure_response_input_list(request: ResponseRequest) -> list[ResponseInputItem]:
        if isinstance(request.input, list):
            return request.input
        if request.input:
            request.input = [ResponseInputItem(role="user", content=request.input)]
        else:
            request.input = []
        return request.input

    @staticmethod
    def normalize_response_output_to_input_items(response: ResponseOutput | list[object]) -> list[ResponseInputItem]:
        def get_field(value: object, name: str, default: Any = None) -> Any:
            if isinstance(value, dict):
                return value.get(name, default)
            return getattr(value, name, default)

        output_items = response.output if isinstance(response, ResponseOutput) else response
        normalized_items: list[ResponseInputItem] = []

        for output_item in output_items or []:
            item_type = str(get_field(output_item, "type", "") or "")
            if item_type == "message":
                normalized_items.append(
                    ResponseInputItem(
                        role=str(get_field(output_item, "role", "assistant") or "assistant"),
                        content=get_field(output_item, "content", "") or "",
                    )
                )
                continue

            if item_type == "function_call_output":
                if isinstance(output_item, ResponseOutputFunctionCallOutput):
                    block = output_item.model_copy(deep=True)
                elif isinstance(output_item, dict):
                    block = ResponseOutputFunctionCallOutput(**output_item)
                else:
                    block = ResponseOutputFunctionCallOutput(
                        id=str(get_field(output_item, "id", "") or ""),
                        status=get_field(output_item, "status", "completed"),
                        call_id=str(get_field(output_item, "call_id", "") or ""),
                        output=str(get_field(output_item, "output", "") or ""),
                    )
                normalized_items.append(ResponseInputItem(role="assistant", content=[block]))
                continue

            text = ResponseTextExtractor.flatten_content(output_item)
            if text:
                normalized_items.append(ResponseInputItem(role="assistant", content=text))

        return normalized_items
