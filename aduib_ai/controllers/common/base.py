import inspect
import logging
import traceback
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel
from configs import config

from utils import jsonable_encoder

logger = logging.getLogger(__name__)


class BaseHttpException(HTTPException):
    error_code = 0
    error_msg = ""
    def __init__(self, error_code: int, error_msg: str):
        super().__init__(status_code=error_code, detail=error_msg)
        self.error_code = error_code
        self.error_msg = error_msg



class BaseResponse(BaseModel):
    """
    Base response class for all responses
    """
    code: int
    msg: str
    data: dict[str, Any]= None
    def __init__(self, code: int = 0, msg: str = "success", data=None):
        super().__init__(code=code, msg=msg, data=data if data is not None else {})
        if data is None:
            data = {}
        self.code = code
        self.msg = msg
        self.data = data

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "msg": self.msg,
            "data": self.data
        }
    @classmethod
    def ok(cls, data: Any | None = None) -> "BaseResponse":
        return cls(code=0, msg="success", data=jsonable_encoder(obj=data, exclude_none=True) if data is not None else {})

    @classmethod
    def error(cls, error_code: int, error_msg: str) -> "BaseResponse":
        return cls(code=error_code, msg=error_msg, data={})




def catch_exceptions(func):
    """A decorator to catch exceptions and return a standardized error response."""
    import functools
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        except BaseHttpException as e:
            return BaseResponse.error(e.error_code, e.error_msg)
        except Exception as e:
            logger.error(f"Exception in {func.__name__}:{func.__doc__}: {e}")
            if config.DEBUG:
                traceback.print_exc()
            return BaseResponse.error(500, str(e))
    return wrapper