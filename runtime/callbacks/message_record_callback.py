import json
from typing import Union, Optional, Sequence

from libs.context import validate_api_key_in_internal
from models import ConversationMessage
from runtime.callbacks.base_callback import Callback
from runtime.entities import PromptMessage, ChatCompletionResponse, ChatCompletionResponseChunk, PromptMessageFunction
from runtime.model_execution import AiModel
from service import ConversationMessageService
from utils import AsyncUtils


class MessageRecordCallback(Callback):
    """Message record callback for logging conversation messages to the database."""

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
        system_prompt = prompt_messages[0].content if prompt_messages[0].role.value == "system" else ""
        message_content: str = ""
        if isinstance(result.message.content, str):
            message_content = result.message.content
        elif isinstance(result.message.content, list):
            message_content = "".join([content.data for content in result.message.content])

        # remove <think> and </think> including the content between them
        if message_content.startswith("<think>") and message_content.endswith("</think>"):
            import re
            message_content = re.sub(r"<think>.*?</think>", "", message_content, flags=re.DOTALL)
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
        ConversationMessageService.add_conversation_message(
            message
        )
        # from event.event_manager import event_manager_context

        # event_manager = event_manager_context.get()
        # from concurrent import futures

        # with futures.ThreadPoolExecutor() as executor:
        #     executor.submit(event_manager.emit, event="qa_rag_from_conversation_message", message=message)
        # await event_manager.emit(event="qa_rag_from_conversation_message", message=message)
        # AsyncUtils.run_async_gen(event_manager.emit(event="qa_rag_from_conversation_message", message=message))

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
        role: str = ""
        system_prompt: str = ""
        content: str = ""
        if isinstance(prompt_messages, list) and prompt_messages:
            role = prompt_messages[-1].role.value
            if prompt_messages[-1].content:
                c = prompt_messages[-1].content
                if isinstance(c, str):
                    content = c
                else:
                    content = "".join([ct.data or ct.text for ct in c])
            system_prompt = prompt_messages[0].content if prompt_messages[0].role.value == "system" else ""
        elif isinstance(prompt_messages, str):
            role = "user"
            content = prompt_messages

        conversation_message = ConversationMessage(
            message_id=model_parameters.get("message_id"),
            model_name=model,
            provider_name=llm_instance.provider_name,
            role=role,
            content=content,
            system_prompt=system_prompt,
        )
        ConversationMessageService.add_conversation_message(
            conversation_message
        )
        # from event.event_manager import event_manager_context
        #
        # event_manager = event_manager_context.get()
        # from concurrent import futures
        # with futures.ThreadPoolExecutor() as executor:
        #     executor.submit(event_manager.emit, event="qa_rag_from_conversation_message", message=conversation_message)

        # AsyncUtils.run_async_gen(
        #     event_manager.emit(event="qa_rag_from_conversation_message", message=conversation_message)
        # )
