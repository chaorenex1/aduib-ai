from typing import Any, Union, Generator

from runtime.tool.builtin_tool.tool import BuiltinTool
from runtime.tool.entities import ToolInvokeResult


class CurrentWeather(BuiltinTool):
    """
    CurrentWeather is a built-in tool that provides current weather information for a given location.
    """

    def _invoke(self, tool_parameters: dict[str, Any], message_id: str | None = None) -> Union[
        ToolInvokeResult, Generator[ToolInvokeResult, None, None]]:

        location = tool_parameters.get("location")

        return ToolInvokeResult(
            name=self.entity.name,
            success=True,
            data="The current weather in {} is 25°C with clear skies.".format(location),
            meta={
                "location": location
            }
        )
