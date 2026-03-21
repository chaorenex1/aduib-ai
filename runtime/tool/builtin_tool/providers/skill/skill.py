from typing import Any

from runtime.tool.builtin_tool.tool import BuiltinTool
from runtime.tool.entities import ToolInvokeResult


class SkillTool(BuiltinTool):
    """
    A tool to invoke skill capabilities.
    """

    async def _invoke(self, tool_parameters: dict[str, Any], message_id: str | None = None) -> ToolInvokeResult:
        """Dispatch a skill request to the loaded skill runtime."""

        try:
            action = self._resolve_action(tool_parameters)
            data = await self._dispatch(tool_parameters, action)
        except ValueError as exc:
            return ToolInvokeResult(name=self.entity.name, success=False, error=str(exc))

        return data

    async def _dispatch(self, tool_parameters: dict[str, Any], action: str) -> ToolInvokeResult:
        skill_controller = self._get_skill_controller(tool_parameters)
        skill_name = tool_parameters.get("skill_name")

        if action == "instructions":
            payload = await skill_controller.get_tool("get_skill_instructions").invoke({"skill_name": skill_name})
        elif action == "reference":
            payload = await skill_controller.get_tool("get_skill_reference").invoke(
                {"skill_name": skill_name, "reference_path": tool_parameters.get("reference_path")}
            )
        elif action == "script":
            payload = await skill_controller.get_tool("get_skill_script").invoke(
                {"skill_name": skill_name, "script_path": tool_parameters.get("script_path")}
            )
        else:
            raise ValueError(f"Unsupported skill action: {action}")

        return next(payload)

    @staticmethod
    def _get_skill_controller(tool_parameters: dict[str, Any]):
        from runtime.tool.skill.tool_provider import SKILLToolController
        from runtime.tool.tool_manager import ToolManager

        tool_manager: ToolManager = tool_parameters.get("tool_manager")
        skill_controller: SKILLToolController = tool_manager.get_skill_controller()
        return skill_controller

    @staticmethod
    def _resolve_action(tool_parameters: dict[str, Any]) -> str:
        raw_action = tool_parameters.get("action")
        if raw_action is None:
            if tool_parameters.get("reference_path"):
                return "reference"
            if tool_parameters.get("script_path"):
                return "script"
            return "instructions"

        if not isinstance(raw_action, str) or not raw_action.strip():
            raise ValueError("'action' must be a non-empty string")

        normalized = raw_action.strip().lower()
        aliases = {
            "instruction": "instructions",
            "instructions": "instructions",
            "describe": "instructions",
            "reference": "reference",
            "script": "script",
            "run-script": "script",
        }
        action = aliases.get(normalized)
        if action is None:
            raise ValueError("action must be one of: instructions, reference, script")
        return action
