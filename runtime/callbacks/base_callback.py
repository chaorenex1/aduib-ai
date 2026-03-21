from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Optional, Union

from ..entities import ChatCompletionResponse, ChatCompletionResponseChunk, PromptMessage, PromptMessageFunction
from ..model_execution import AiModel


class Callback(ABC):
    """
    Base class for callbacks.
    """

    raise_error: bool = False

    @abstractmethod
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
        agent_id: Optional[int] = None,
        agent_session_id: Optional[int] = None,
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
        :param include_reasoning: include reasoning in the response
        :param user: unique user id
        """
        raise NotImplementedError()

    @abstractmethod
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
        agent_id: Optional[int] = None,
        agent_session_id: Optional[int] = None,
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
        :param include_reasoning: include reasoning in the response
        :param user: unique user id
        """
        raise NotImplementedError()

    @abstractmethod
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
        agent_id: Optional[int] = None,
        agent_session_id: Optional[int] = None,
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
        :param include_reasoning: include reasoning in the response
        :param user: unique user id
        """
        raise NotImplementedError()

    @abstractmethod
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
        agent_id: Optional[int] = None,
        agent_session_id: Optional[int] = None,
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
        :param include_reasoning: include reasoning in the response
        :param user: unique user id
        """
        raise NotImplementedError()

    def print_text(self, text: str, color: Optional[str] = None, end: str = "") -> None:
        """Print text with highlighting and no end characters."""
        print(text, end=end)
