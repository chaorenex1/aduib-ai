from .base import BaseServiceError


class ApiKeyNotFound(BaseServiceError):
    pass


class ModelNotFound(BaseServiceError):
    pass


class ModelProviderNotFound(BaseServiceError):
    pass


class FileNotFound(BaseServiceError):
    pass


class UserNotFound(BaseServiceError):
    pass


class UserAlreadyExists(BaseServiceError):
    pass


class InvalidCredentials(BaseServiceError):
    pass


class UserDisabled(BaseServiceError):
    pass


class RegistrationDisabled(BaseServiceError):
    pass


class InsufficientPermissions(BaseServiceError):
    pass


class AgentNotFoundError(BaseServiceError):
    pass


class PlanStateError(ValueError):
    pass
