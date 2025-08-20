from typing import Union, Generator

from fastapi import Request

from controllers.common.error import InnerError
from controllers.params import ChatCompletionRequest, CompletionRequest
from utils.encoders import jsonable_encoder
from .base import BaseClient
from ..entities import ChatCompletionResponse, ChatCompletionResponseChunk


class ModelClient(BaseClient):

    def completion_request(self,prompt_messages: Union[ChatCompletionRequest, CompletionRequest],
        credentials: dict,
        raw_request: Request,
        stream:bool)->Union[ChatCompletionResponse, Generator[ChatCompletionResponseChunk, None, None]]:

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
        base_url = credentials["api_base"]
        api_key = credentials["api_key"]
        path = base_url + raw_request.url.path
        user_agent = raw_request.headers.get("User-Agent")
        if isinstance(prompt_messages, ChatCompletionRequest) and stream:
            response = self._stream_request_with_model(method="post",
                                                          path=path,
                                                          type=ChatCompletionResponseChunk,
                                                          data=jsonable_encoder(obj=prompt_messages,exclude_none=True),
                                                          headers={"User-Agent": user_agent,"Content-Type": "application/json","X-Api-Key": api_key},
            )
            try:
                yield from response
            except InnerError as e:
                raise ValueError(e.message+str(e.code)) from e
        else:
            response = self._request_with_model(method="post",
                                                path=path,
                                                type=ChatCompletionResponse,
                                                data=jsonable_encoder(prompt_messages),
                                                headers={"User-Agent": user_agent,"Content-Type": "application/json","X-Api-Key": api_key},
            )
            return response
