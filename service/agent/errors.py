from service.error.base import BaseServiceError


class AgentServiceError(BaseServiceError):
    code = "agent_service_error"


class AgentNotFoundError(AgentServiceError):
    status_code = 404
    code = "agent_not_found"


class AgentSessionNotFoundError(AgentServiceError):
    status_code = 404
    code = "agent_session_not_found"


class AgentSessionConflictError(AgentServiceError):
    status_code = 409
    code = "agent_session_conflict"


class AgentValidationError(AgentServiceError):
    status_code = 400
    code = "agent_validation_error"


class AgentAccessDeniedError(AgentServiceError):
    status_code = 403
    code = "agent_access_denied"
