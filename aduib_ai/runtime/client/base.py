import json
import logging
from typing import TypeVar, Generator

import requests
from pydantic import BaseModel

from controllers.common.error import InnerError

T = TypeVar("T", bound=(BaseModel | dict | list | bool | str))

logger = logging.getLogger(__name__)

class BaseClient:
    """
    Base class for clients
    """
    def _request(
        self,
        method: str,
        path: str,
        headers: dict | None = None,
        data: bytes | dict | str | None = None,
        params: dict | None = None,
        files: dict | None = None,
        stream: bool = False,
    ) -> requests.Response:
        """
        Make a request to  API.
        """
        url = path
        headers = headers or {}
        headers["Accept-Encoding"] = "gzip, deflate, br"

        if headers.get("Content-Type") == "application/json" and isinstance(data, dict):
            data = json.dumps(data)

        try:
            response = requests.request(
                method=method, url=str(url), headers=headers, data=data, params=params, stream=stream, files=files
            )
        except requests.exceptions.ConnectionError:
            logger.exception("Request to {} failed", extra={"url": url})
            raise InnerError(code=500, message="Request to {} failed".format(url))

        return response

    def _stream_request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        headers: dict | None = None,
        data: bytes | dict | None = None,
        files: dict | None = None,
    ) -> Generator[bytes, None, None]:
        """
        Make a stream request to the plugin daemon inner API
        """
        response = self._request(method, path, headers, data, params, files, stream=True)
        for line in response.iter_lines(chunk_size=1024 * 8):
            line = line.decode("utf-8").strip()
            if line.startswith("data:"):
                line = line[5:].strip()
            if line:
                yield line

    def _stream_request_with_model(
        self,
        method: str,
        path: str,
        type: type[T],
        headers: dict | None = None,
        data: bytes | dict | None = None,
        params: dict | None = None,
        files: dict | None = None,
    ) -> Generator[T, None, None]:
        """
        Make a stream request to the plugin daemon inner API and yield the response as a model.
        """
        for line in self._stream_request(method, path, params, headers, data, files):
            if line == "[DONE]":
                yield type(done=True)  # type: ignore
            else:
                yield type(**json.loads(line))  # type: ignore

    def _request_with_model(
        self,
        method: str,
        path: str,
        type: type[T],
        headers: dict | None = None,
        data: bytes | None = None,
        params: dict | None = None,
        files: dict | None = None,
    ) -> T:
        """
        Make a request to the plugin daemon inner API and return the response as a model.
        """
        response = self._request(method, path, headers, data, params, files)
        json = response.json()
        print(f"Response JSON: {json}")
        return type(**json)  # type: ignore