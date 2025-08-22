import logging

from runtime.tool.base.tool_provider import ToolController
from runtime.tool.builtin_tool.tool_provider import BuiltinToolController
from runtime.tool.entities import ToolProviderType

logger = logging.getLogger(__name__)

class ToolManager:
    """
    ToolManager is responsible for managing tool providers and their controllers.
    """
    providers: dict[str, ToolController] = {}

    def __init__(self):
        self.providers = {
            ToolProviderType.BUILTIN: BuiltinToolController()
        }

    def get_builtin_tool_controller(self):
        return self.providers[ToolProviderType.BUILTIN]

    def get_tool_controller(self, provider_type: ToolProviderType) -> ToolController:
        """
        Get tool controller by provider type

        :param provider_type: tool provider type
        :return: tool controller
        """
        if provider_type not in self.providers:
            raise ValueError(f"Tool provider {provider_type} not found")
        return self.providers[provider_type]

    def register_tool_controller(self, provider_type: ToolProviderType, controller: ToolController):
        """
        Register a tool controller for a specific provider type

        :param provider_type: tool provider type
        :param controller: tool controller instance
        """
        if provider_type in self.providers:
            raise ValueError(f"Tool provider {provider_type} already registered")
        self.providers[provider_type] = controller
        logger.info(f"Registered tool controller for provider {provider_type}")

    def unregister_tool_controller(self, provider_type: ToolProviderType):
        """
        Unregister a tool controller for a specific provider type
        :param provider_type: tool provider type
        """
        if provider_type not in self.providers:
            raise ValueError(f"Tool provider {provider_type} not registered")
        del self.providers[provider_type]
        logger.info(f"Unregistered tool controller for provider {provider_type}")

    def list_tool_providers(self) -> list[str]:
        """
        List all registered tool providers

        :return: list of tool provider types
        """
        return list(self.providers.keys())