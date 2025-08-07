from fastapi import HTTPException


class BaseHttpException(HTTPException):
    error_code = 0
    error_msg = ""
    def __init__(self, error_code: int, error_msg: str):
        super().__init__(status_code=error_code, detail=error_msg)
        self.error_code = error_code
        self.error_msg = error_msg