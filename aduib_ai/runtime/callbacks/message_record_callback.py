from typing import Union, Optional, Sequence

from models import ConversationMessage
from runtime.callbacks.base_callback import Callback
from runtime.entities import PromptMessage, PromptMessageTool, ChatCompletionResponse, ChatCompletionResponseChunk
from runtime.providers.base import AiModel
from service.conversation_message_service import ConversationMessageService


class MessageRecordCallback(Callback):
    def on_new_chunk(self, llm_instance: AiModel, chunk: ChatCompletionResponseChunk, model: str, credentials: dict,
                     prompt_messages: Sequence[PromptMessage], model_parameters: dict,
                     tools: Optional[list[PromptMessageTool]] = None, stop: Optional[Sequence[str]] = None,
                     stream: bool = True, include_reasoning: bool = False, user: Optional[str] = None):
        pass

    def on_after_invoke(self, llm_instance: AiModel, result: ChatCompletionResponse, model: str, credentials: dict,
                        prompt_messages: Sequence[PromptMessage], model_parameters: dict,
                        tools: Optional[list[PromptMessageTool]] = None, stop: Optional[Sequence[str]] = None,
                        stream: bool = True, include_reasoning: bool = False, user: Optional[str] = None) -> None:
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
        message_id = model_parameters.get('message_id')
        if not message_id:
            return
        message_content:str =""
        if isinstance(result.message.content, str):
            message_content = result.message.content
        elif isinstance(result.message.content, list):
            message_content = ''.join([content.data for content in result.message.content])

        ConversationMessageService.add_conversation_message(
            ConversationMessage(
                message_id=message_id,
                model_name=model,
                provider_name=llm_instance.provider_name,
                role=result.message.role.value,
                content=message_content,
                system_prompt="",
                usage=result.usage.model_dump_json(exclude_none=True),
                state="success",)
        )

    def on_invoke_error(self, llm_instance: AiModel, ex: Exception, model: str, credentials: dict,
                        prompt_messages: list[PromptMessage], model_parameters: dict,
                        tools: Optional[list[PromptMessageTool]] = None, stop: Optional[Sequence[str]] = None,
                        stream: bool = True, include_reasoning: bool = False, user: Optional[str] = None) -> None:
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
        message_id = model_parameters.get('message_id')
        if not message_id:
            return
        ConversationMessageService.update_conversation_message_state(
            message_id=message_id,
            state="failed",
        )

    def on_before_invoke(self, llm_instance: AiModel, model: str, credentials: dict,
                         prompt_messages: Union[list[PromptMessage], str], model_parameters: dict,
                         tools: Optional[list[PromptMessageTool]] = None, stop: Optional[Sequence[str]] = None,
                         stream: bool = True, include_reasoning: bool = False, user: Optional[str] = None) -> None:
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
        role:str = ""
        system_prompt:str = ""
        content:str = ""
        if isinstance(prompt_messages, list) and prompt_messages:
            role= prompt_messages[-1].role.value
            if prompt_messages[-1].content:
                content = prompt_messages[-1].content
            system_prompt= prompt_messages[0].content if prompt_messages[0].role.value == "system" else ""
        elif isinstance(prompt_messages, str):
            role = "user"
            content = prompt_messages

        ConversationMessageService.add_conversation_message(
            ConversationMessage(
                message_id=model_parameters.get('message_id'),
                model_name=model,
                provider_name=llm_instance.provider_name,
                role=role,
                content=content,
                system_prompt=system_prompt,
            )
        )