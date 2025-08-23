from contextvars import ContextVar

from libs.contextVar_wrapper import ContextVarWrappers
from models import ApiKey

api_key_context: ContextVarWrappers[ApiKey]=ContextVarWrappers(ContextVar("api_key"))
trace_id_context: ContextVarWrappers[str]=ContextVarWrappers(ContextVar("trace_id"))

__all__ = [
    "api_key_context",
    "trace_id_context",
]