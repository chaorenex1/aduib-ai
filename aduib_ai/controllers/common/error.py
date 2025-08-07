from aduib_ai.controllers.common.base import BaseHttpException


class ApiNotCurrentlyAvailableError(BaseHttpException):
    def __init__(self):
        super().__init__(error_code=403, error_msg="api key is not currently available")