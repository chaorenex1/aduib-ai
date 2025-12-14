import json
import re
from typing import Union, Optional, Sequence

from event.event_manager import event_manager_context
from libs.context import validate_api_key_in_internal
from models import ConversationMessage
from runtime.callbacks.base_callback import Callback
from runtime.entities import PromptMessage, ChatCompletionResponse, ChatCompletionResponseChunk, PromptMessageFunction, \
    TextPromptMessageContent
from runtime.model_execution import AiModel
from service import ConversationMessageService
from utils import jsonable_encoder, AsyncUtils


class MessageRecordCallback(Callback):
    """Message record callback for logging conversation messages to the database."""

    def __init__(self):
        """Initialize the callback."""
        super().__init__()

    def _get_system_prompt(self, prompt_messages: Sequence[PromptMessage]) -> str:
        """Extract system prompt from prompt messages."""
        if prompt_messages and prompt_messages[0].role.value == "system":
            return prompt_messages[0].content or ""
        return ""

    def _extract_content_from_list(self, content_list: list) -> str:
        """Extract content from a list of message content items."""
        message_content = ""
        for c in content_list:
            if isinstance(c, TextPromptMessageContent):
                if c.text:
                    message_content += c.text
                if c.data:
                    message_content += c.data
            else:
                message_content += json.dumps(c)
        return message_content

    def _remove_thinking_tags(self, content: str) -> str:
        """Remove <think> tags and their content from the message."""
        if content.startswith("<think>"):
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        return content

    def _emit_event(self, message: ConversationMessage) -> None:
        """Emit event for conversation message processing."""
        event_manager = event_manager_context.get()
        # Use AsyncUtils to properly run the async coroutine
        AsyncUtils.run_async_gen(
            event_manager.emit(event="qa_rag_from_conversation_message", message=message)
        )

    def on_new_chunk(
            self,
            llm_instance: AiModel,
            chunk: ChatCompletionResponseChunk,
            model: str,
            credentials: dict,
            prompt_messages: Sequence[PromptMessage],
            model_parameters: dict,
            tools: Optional[list[PromptMessageFunction]] = None,
            stop: Optional[Sequence[str]] = None,
            stream: bool = True,
            include_reasoning: bool = False,
            user: Optional[str] = None,
    ):
        pass

    def on_after_invoke(
            self,
            llm_instance: AiModel,
            result: ChatCompletionResponse,
            model: str,
            credentials: dict,
            prompt_messages: Sequence[PromptMessage],
            model_parameters: dict,
            tools: Optional[list[PromptMessageFunction]] = None,
            stop: Optional[Sequence[str]] = None,
            stream: bool = True,
            include_reasoning: bool = False,
            user: Optional[str] = None,
    ) -> None:
        """
        After invoke callback

        :param llm_instance: LLM instance
        :param result: result
        :param model: model name
        :param credentials: model credentials
        :param prompt_messages: prompt messages
        :param model_parameters: model parameters
        :param tools: tools for tool calling
        :param stop: stop words
        :param stream: is stream response
        :param include_reasoning: include reasoning in the prompt
        :param user: unique user id
        """
        if not validate_api_key_in_internal():
            return

        message_id = model_parameters.get("message_id")
        if not message_id:
            return

        # Extract system prompt
        system_prompt = self._get_system_prompt(prompt_messages)

        # Extract message content
        message_content = ""
        if isinstance(result.message.content, str):
            message_content = result.message.content
        elif isinstance(result.message.content, list):
            message_content = self._extract_content_from_list(result.message.content)

        # Remove thinking tags if present
        message_content = self._remove_thinking_tags(message_content)

        # Create conversation message
        message = ConversationMessage(
            message_id=message_id,
            model_name=model,
            provider_name=llm_instance.provider_name,
            model_parameters=json.dumps(model_parameters),
            role=result.message.role.value,
            content=message_content,
            system_prompt=system_prompt,
            usage=result.usage.model_dump_json(exclude_none=True),
            state="success",
        )

        # Emit event for async processing
        self._emit_event(message)

    def on_invoke_error(
            self,
            llm_instance: AiModel,
            ex: Exception,
            model: str,
            credentials: dict,
            prompt_messages: list[PromptMessage],
            model_parameters: dict,
            tools: Optional[list[PromptMessageFunction]] = None,
            stop: Optional[Sequence[str]] = None,
            stream: bool = True,
            include_reasoning: bool = False,
            user: Optional[str] = None,
    ) -> None:
        """
        Invoke error callback

        :param llm_instance: LLM instance
        :param ex: exception
        :param model: model name
        :param credentials: model credentials
        :param prompt_messages: prompt messages
        :param model_parameters: model parameters
        :param tools: tools for tool calling
        :param stop: stop words
        :param stream: is stream response
        :param include_reasoning: include reasoning in the prompt
        :param user: unique user id
        """
        if not validate_api_key_in_internal():
            return
        message_id = model_parameters.get("message_id")
        if not message_id:
            return
        ConversationMessageService.update_conversation_message_state(
            message_id=message_id,
            state="failed",
        )

    def on_before_invoke(
            self,
            llm_instance: AiModel,
            model: str,
            credentials: dict,
            prompt_messages: Union[list[PromptMessage], str],
            model_parameters: dict,
            tools: Optional[list[PromptMessageFunction]] = None,
            stop: Optional[Sequence[str]] = None,
            stream: bool = True,
            include_reasoning: bool = False,
            user: Optional[str] = None,
    ) -> None:
        """
        Before invoke callback

        :param llm_instance: LLM instance
        :param model: model name
        :param credentials: model credentials
        :param prompt_messages: prompt messages
        :param model_parameters: model parameters
        :param tools: tools for tool calling
        :param stop: stop words
        :param stream: is stream response
        :param include_reasoning: include reasoning in the prompt
        :param user: unique user id
        """
        if not validate_api_key_in_internal():
            return

        role = ""
        system_prompt = ""
        content = ""

        # Handle list of prompt messages
        if isinstance(prompt_messages, list) and prompt_messages:
            role = prompt_messages[-1].role.value

            # Extract content from last message
            if prompt_messages[-1].content:
                c = prompt_messages[-1].content
                if isinstance(c, str):
                    content = c
                elif isinstance(c, list):
                    try:
                        content = "".join([ct.data or ct.text for ct in c if ct.data or ct.text])
                    except Exception:
                        content = json.dumps(jsonable_encoder(c, exclude_none=True))

            # Extract system prompt
            system_prompt = self._get_system_prompt(prompt_messages)

        # Handle string prompt messages
        elif isinstance(prompt_messages, str):
            role = "user"
            content = prompt_messages

        # Create conversation message
        conversation_message = ConversationMessage(
            message_id=model_parameters.get("message_id"),
            model_name=model,
            provider_name=llm_instance.provider_name,
            role=role,
            content=content,
            system_prompt=system_prompt,
        )

        # Emit event for async processing
        self._emit_event(conversation_message)

