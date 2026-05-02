from .base import BaseServiceError


class ApiKeyNotFound(BaseServiceError):
    status_code = 404
    code = "api_key_not_found"


class ModelNotFound(BaseServiceError):
    status_code = 404
    code = "model_not_found"


class ModelProviderNotFound(BaseServiceError):
    status_code = 404
    code = "model_provider_not_found"


class FileNotFound(BaseServiceError):
    status_code = 404
    code = "file_not_found"


class UserNotFound(BaseServiceError):
    status_code = 404
    code = "user_not_found"


class UserAlreadyExists(BaseServiceError):
    status_code = 409
    code = "user_already_exists"


class InvalidCredentials(BaseServiceError):
    status_code = 401
    code = "invalid_credentials"


class UserDisabled(BaseServiceError):
    status_code = 403
    code = "user_disabled"


class RegistrationDisabled(BaseServiceError):
    status_code = 403
    code = "registration_disabled"


class InvalidRefreshToken(BaseServiceError):
    status_code = 401
    code = "invalid_refresh_token"


class RefreshTokenRevoked(BaseServiceError):
    status_code = 401
    code = "refresh_token_revoked"


class InsufficientPermissions(BaseServiceError):
    status_code = 403
    code = "insufficient_permissions"


class AgentNotFoundError(BaseServiceError):
    status_code = 404
    code = "agent_not_found"


class PlanStateError(ValueError):
    pass
