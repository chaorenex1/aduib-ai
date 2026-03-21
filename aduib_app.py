from typing import Any

from fastapi import FastAPI


class AduibAIApp(FastAPI):
    app_home: str = "."
    workdir: str = "."
    config = None
    extensions: dict[str, Any] = {}
    pass
