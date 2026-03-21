from collections.abc import Generator
from typing import Any, Union

from ..base.tool import Tool, ToolInvokeResult
from ..entities import ToolEntity, ToolProviderType


class SkillTool(Tool):
    """
    The base class of a Skill tool.
    """

    def __init__(self, entity: ToolEntity):
        super().__init__(entity)
        self.entity = entity

    def tool_provider_type(self) -> ToolProviderType:
        """
        Get the tool provider type.

        :return: The tool provider type, which is always ToolProviderType.SKILL
        """
        return ToolProviderType.SKILL

    async def _invoke(
        self, tool_parameters: dict[str, Any], message_id: str | None = None
    ) -> Union[ToolInvokeResult, Generator[ToolInvokeResult, None, None]]:
        """
        Invoke the tool with the given parameters.
        """
        if not self.entity.entrypoint:
            return ToolInvokeResult(error="No entrypoint defined for skill tool")
        try:
            result = self.entity.entrypoint(**tool_parameters)
            return ToolInvokeResult(name=self.entity.name, data=result, success=True)
        except Exception as exc:
            return ToolInvokeResult(name=self.entity.name, error=str(exc), success=False)
