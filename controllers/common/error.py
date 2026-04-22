from controllers.common.base import ApiHttpException


class ApiNotCurrentlyAvailableError(ApiHttpException):
    def __init__(self):
        super().__init__(status_code=403, code="api_not_available", message="api key is not currently available")


class ServiceError(ApiHttpException):
    def __init__(self, message: str = "service error"):
        super().__init__(status_code=500, code="service_error", message=message)


class UnauthorizedError(ApiHttpException):
    def __init__(self, message: str = "unauthorized"):
        super().__init__(status_code=401, code="unauthorized", message=message)


class InnerError(Exception):
    code: int
    message: str

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
