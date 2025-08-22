from datetime import datetime, UTC
from typing import Any, Union, Generator

from pytz import timezone as pytz_timezone

from runtime.tool.builtin_tool.tool import BuiltinTool
from runtime.tool.entities import ToolInvokeResult


class CurrentTimeTool(BuiltinTool):
    """
    A tool to get the current time.
    """

    def _invoke(self, tool_parameters: dict[str, Any], message_id: str | None = None) -> Union[
        ToolInvokeResult, Generator[ToolInvokeResult, None, None]]:
        """
        invoke tools
        """
        # get timezone
        tz = tool_parameters.get("timezone", "UTC")
        fm = tool_parameters.get("format") or "%Y-%m-%d %H:%M:%S %Z"
        if tz == "UTC":
            return ToolInvokeResult(
                data=datetime.now(UTC).strftime(fm),
                meta={
                    "timezone": tz,
                    "format": fm,
                }
            )

        try:
            tz = pytz_timezone(tz)
        except Exception:
            return ToolInvokeResult(
                data=f"Invalid timezone: {tz}",
                success=False,
                meta={
                    "timezone": tz,
                    "format": fm,
                }
            )
        return ToolInvokeResult(
            data=datetime.now(tz).strftime(fm),
            meta={
                "timezone": tz.zone,
                "format": fm,
            }
        )
