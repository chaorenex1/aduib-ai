# from contextvars import ContextVar
#
# from event.event_manager import EventManager
# #
# from libs.contextVar_wrapper import ContextVarWrappers
# from models.api_key import ApiKey
#
# api_key_context: ContextVarWrappers[ApiKey]=ContextVarWrappers(ContextVar("api_key"))
# trace_id_context: ContextVarWrappers[str]=ContextVarWrappers(ContextVar("trace_id"))
# event_manager_context: ContextVarWrappers[EventManager]=ContextVarWrappers(ContextVar("event_manager"))
from .context import get_app, get_current_user_id

__all__ = ["get_app", "get_current_user_id"]
