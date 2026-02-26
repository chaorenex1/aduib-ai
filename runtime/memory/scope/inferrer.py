from __future__ import annotations

from typing import Any, Optional

from runtime.memory.scope.hierarchy import MemoryScopeLevel, ScopeNode, ScopePath


class ScopeInferrer:
    """Infer scope path from content and optional context."""

    def __init__(
        self,
        project_keywords: Optional[dict[str, str]] = None,
        module_keywords: Optional[dict[str, str]] = None,
    ) -> None:
        self.project_keywords = dict(project_keywords or {})
        self.module_keywords = dict(module_keywords or {})

        self.project_names: dict[str, str] = {}
        self.module_names: dict[str, str] = {}
        self.module_projects: dict[str, str] = {}

        for _, project_id in self.project_keywords.items():
            self.project_names.setdefault(project_id, project_id)
        for _, module_id in self.module_keywords.items():
            self.module_names.setdefault(module_id, module_id)

    def infer(self, content: str, user_id: str, context: Optional[dict[str, Any]] = None) -> ScopePath:
        """Infer scope with priority: explicit context > module keyword > project keyword > work/life > personal."""

        context = context or {}

        module_id = self._context_value(context, "module_id")
        if module_id:
            return self._build_module_scope_from_context(user_id, module_id, context)

        project_id = self._context_value(context, "project_id")
        if project_id:
            project_name = self._context_value(context, "project_name") or self.project_names.get(
                project_id, "Project"
            )
            return ScopePath.project(user_id, project_id, project_name)

        module_hit = self._detect_module(content)
        if module_hit:
            module_id, module_name, project_id, project_name = module_hit
            return ScopePath.module(user_id, project_id, project_name, module_id, module_name)

        project_hit = self._detect_project(content)
        if project_hit:
            project_id, project_name = project_hit
            return ScopePath.project(user_id, project_id, project_name)

        if self._is_work_related(content):
            return ScopePath.work(user_id)

        if self._is_life_related(content):
            return self._life_scope(user_id)

        return ScopePath.personal(user_id)

    def register_project(self, keyword: str, project_id: str, project_name: str) -> None:
        self.project_keywords[keyword] = project_id
        self.project_names[project_id] = project_name

    def register_module(
        self,
        keyword: str,
        module_id: str,
        module_name: str,
        project_id: str,
        project_name: str,
    ) -> None:
        self.module_keywords[keyword] = module_id
        self.module_names[module_id] = module_name
        self.module_projects[module_id] = project_id
        self.project_names[project_id] = project_name

    def _detect_project(self, content: str) -> Optional[tuple[str, str]]:
        normalized = self._normalize_text(content)
        for keyword, project_id in self.project_keywords.items():
            if not keyword:
                continue
            if keyword.lower() in normalized:
                project_name = self.project_names.get(project_id, project_id)
                return project_id, project_name
        return None

    def _detect_module(self, content: str) -> Optional[tuple[str, str, str, str]]:
        normalized = self._normalize_text(content)
        for keyword, module_id in self.module_keywords.items():
            if not keyword:
                continue
            if keyword.lower() in normalized:
                module_name = self.module_names.get(module_id, module_id)
                project_id = self.module_projects.get(module_id, "default")
                project_name = self.project_names.get(project_id, "Project")
                return module_id, module_name, project_id, project_name
        return None

    @staticmethod
    def _is_work_related(content: str) -> bool:
        keywords = [
            "工作",
            "项目",
            "会议",
            "需求",
            "任务",
            "代码",
            "bug",
            "部署",
            "上线",
            "api",
            "数据库",
            "服务器",
        ]
        normalized = ScopeInferrer._normalize_text(content)
        return any(keyword in normalized for keyword in keywords)

    @staticmethod
    def _is_life_related(content: str) -> bool:
        keywords = [
            "生活",
            "家务",
            "购物",
            "旅行",
            "日常",
            "租房",
            "家庭",
            "健康",
            "运动",
        ]
        normalized = ScopeInferrer._normalize_text(content)
        return any(keyword in normalized for keyword in keywords)

    def _build_module_scope_from_context(self, user_id: str, module_id: str, context: dict[str, Any]) -> ScopePath:
        module_name = self._context_value(context, "module_name") or self.module_names.get(module_id, module_id)
        project_id = self._context_value(context, "project_id") or self.module_projects.get(module_id, "default")
        project_name = self._context_value(context, "project_name") or self.project_names.get(project_id, "Project")
        return ScopePath.module(user_id, project_id, project_name, module_id, module_name)

    @staticmethod
    def _life_scope(user_id: str) -> ScopePath:
        return ScopePath(
            user_id=user_id,
            nodes=[
                ScopeNode(level=MemoryScopeLevel.PERSONAL, id=user_id, name="Personal"),
                ScopeNode(level=MemoryScopeLevel.LIFE, id="life", name="Life"),
            ],
        )

    @staticmethod
    def _context_value(context: dict[str, Any], key: str) -> Optional[str]:
        value = context.get(key)
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip() or None
        return str(value).strip() or None

    @staticmethod
    def _normalize_text(text: str) -> str:
        return (text or "").lower()
