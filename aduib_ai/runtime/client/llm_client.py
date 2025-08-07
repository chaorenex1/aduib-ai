import json
from typing import Union, Generator, Optional

from ollama import Message, Tool, ChatResponse
from openai import Stream
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from ..entities import LLMResult, LLMResultChunk, PromptMessage
from ..entities.message_entities import PromptMessageFunction
from ..entities.provider_entities import ProviderSDKType


class ModelClient:

    @staticmethod
    def completion_request(model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        model_parameters: Optional[dict] = None,
        tools: Optional[list[PromptMessageFunction]] = None,
        stop: Optional[list[str]] = None,
        stream: bool = True)->Union[LLMResult, Generator[LLMResultChunk, None, None]]:

        """
        Invoke LLM model
        :param model: model name
        :param credentials: model credentials
        :param prompt_messages: prompt messages
        :param model_parameters: model parameters
        :param tools: tools
        :param stop: stop words
        :param stream: stream response
        :param user: unique user id
        """
        sdk_type = credentials["sdk_type"]
        functions=[Tool(type="function", function=json.load(tool.function.model_dump())) for tool in tools] if tools else []
        if ProviderSDKType.OLLAMA.to_model_type() == sdk_type:
            base_url = credentials["base_url"] if "base_url" in credentials else "http://localhost:11434"
            from ollama import Client
            ollama = Client(host=base_url, headers={
                'api_key': credentials["api_key"] if "api_key" in credentials else None,
            })
            messages=[Message(role=message.role.value, content=message.content) for message in prompt_messages]
            response:ChatResponse = ollama.chat(model=model, messages=messages, tools=functions, stream=stream,
                               format="json" if model_parameters and "response_format" in model_parameters else None,
                               options=None, keep_alive=None)
            print(response)
        else:
            base_url = credentials["base_url"] if "base_url" in credentials else "http://localhost:11434"
            api_key= credentials["api_key"] if "api_key" in credentials else None
            from openai import OpenAI
            openai = OpenAI(api_key=api_key, base_url=base_url)
            messages=[{
                "role": message.role.value,
                "content": message.content
            } for message in prompt_messages]
            response:ChatCompletion | Stream[ChatCompletionChunk]=openai.chat.completions.create(
                model=model,
                messages=messages,
                stream=stream,
                tools=functions,
                stop=stop,
                temperature=model_parameters["temperature"] if model_parameters and "temperature" in model_parameters else 1,
                max_tokens=model_parameters["max_tokens"] if model_parameters and "max_tokens" in model_parameters else 1000,
                top_p=model_parameters["top_p"] if model_parameters and "top_p" in model_parameters else 1,
                frequency_penalty=model_parameters["frequency_penalty"] if model_parameters and "frequency_penalty" in model_parameters else 0,
                presence_penalty=model_parameters["presence_penalty"] if model_parameters and "presence_penalty" in model_parameters else 0,
            )
            print(response)
