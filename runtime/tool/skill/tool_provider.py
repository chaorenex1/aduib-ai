
from runtime.tool.base.tool_provider import ToolController
from runtime.tool.skill.tool import SkillTool


class SKILLToolController(ToolController):
    """
    A controller for managing skill tool
    This controller provides methods to access and manage skill tool
    """

    tools: list[SkillTool] = []
    _skills_instance = None

    def __init__(self, app_home: str = "") -> None:
        super().__init__()
        self._app_home = app_home
        self._skills_instance = None
        self.tools = self.load_tools()

    def get_tool(self, tool_name: str) -> SkillTool:
        """
        Get a specific skill tool by its name.
        This method should be implemented to return the tool instance.
        """
        for tool in self.tools:
            if tool.entity.name == tool_name:
                return tool
        return None

    def get_tools(self, filter_names: list[str] = None) -> list[SkillTool]:
        """
        don't use this method directly
        """
        return []

    def get_tool_schema(self, tool_name: str) -> dict:
        """
        Get the schema of a specific skill tool.
        This method should be implemented to return the schema of the specified tool.
        """
        for tool in self.tools:
            if tool.entity.name == tool_name:
                return tool.entity.model_json_schema()
        raise ValueError(f"Tool {tool_name} not found.")

    def load_tools(self) -> list[SkillTool]:
        """
        Load all skill tools.
        This method should be implemented to return a list of all skill tools.
        """
        from pathlib import Path

        from runtime.agent.skill import LocalSkills, Skills

        loaders = []
        providers_path = Path(__file__).parent / "providers"
        if providers_path.exists() and any((p / "SKILL.md").exists() for p in providers_path.iterdir() if p.is_dir()):
            loaders.append(LocalSkills(str(providers_path), validate=True))
        if self._app_home:
            user_skill_path = Path(self._app_home) / "skill"
            if user_skill_path.exists():
                loaders.append(LocalSkills(str(user_skill_path), validate=False))
        if not loaders:
            return []
        self._skills_instance = Skills(loaders)
        return self._skills_instance.get_tools()

    def get_skills_instance(self):
        return self._skills_instance
