import json
import logging
from typing import Optional, Sequence, Union

from .base_callback import Callback
from ..entities import PromptMessage, ChatCompletionResponseChunk, ChatCompletionResponse, \
    PromptMessageFunction
from ..model_execution.base import AiModel

logger = logging.getLogger(__name__)


class LoggingCallback(Callback):
    def on_before_invoke(
        self,
        llm_instance: AiModel,
        model: str,
        credentials: dict,
        prompt_messages: Union[list[PromptMessage],str],
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
        self.print_text("\n[on_llm_before_invoke]\n", color="blue")
        self.print_text(f"Model: {model}\n", color="blue")
        self.print_text("Parameters:\n", color="blue")
        for key, value in model_parameters.items():
            self.print_text(f"\t{key}: {value}\n", color="blue")

        if stop:
            self.print_text(f"\tstop: {stop}\n", color="blue")

        if tools:
            self.print_text("\tTools:\n", color="blue")
            for tool in tools:
                self.print_text(f"\t\t{tool.function.name}\n", color="blue")

        self.print_text(f"Stream: {stream}\n", color="blue")
        self.print_text(f"Include reasoning: {include_reasoning}\n", color="blue")
        if user:
            self.print_text(f"User: {user}\n", color="blue")

        self.print_text("Prompt messages:\n", color="blue")
        if isinstance(prompt_messages, str):
            self.print_text(f"\t{prompt_messages}\n", color="blue")
        else:
            for prompt_message in prompt_messages:
                if prompt_message.name:
                    self.print_text(f"\tname: {prompt_message.name}\n", color="blue")

                self.print_text(f"\trole: {prompt_message.role.value}\n", color="blue")
                self.print_text(f"\tcontent: {prompt_message.content}\n", color="blue")

        if stream:
            self.print_text("\n[on_llm_new_chunk]")

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
        """
        On new chunk callback

        :param llm_instance: LLM instance
        :param chunk: chunk
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
        # if not config.DEBUG:
        #     return
        # if chunk.choices and len(chunk.choices)>0:
        #     self.print_text("\n[on_llm_new_chunk]\n", color="blue")
        #     self.print_text(f"Content: {chunk.choices[0].delta.content}\n", color="blue")

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
        self.print_text("\n[on_llm_after_invoke]\n", color="yellow")
        self.print_text(f"Content: {result.message.content}\n", color="yellow")

        if result.message.tool_calls:
            self.print_text("Tool calls:\n", color="yellow")
            for tool_call in result.message.tool_calls:
                self.print_text(f"\t{tool_call.id}\n", color="yellow")
                self.print_text(f"\t{tool_call.function.name}\n", color="yellow")
                self.print_text(f"\t{json.dumps(tool_call.function.arguments)}\n", color="yellow")

        self.print_text(f"Model: {result.model}\n", color="yellow")
        self.print_text(f"Usage: {result.usage}\n", color="yellow")
        self.print_text(f"System Fingerprint: {result.system_fingerprint}\n", color="yellow")

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
        self.print_text("\n[on_llm_invoke_error]\n", color="red")
        logger.exception(ex)