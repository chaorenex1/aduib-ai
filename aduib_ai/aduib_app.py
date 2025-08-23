from typing import Any

from fastapi import FastAPI


class AduibAIApp(FastAPI):
    config = None
    extensions: dict[str, Any] = {}
    pass