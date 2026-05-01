from __future__ import annotations

from models import Permission, get_db
from service.agent.contracts import ToolPermissionView


class ToolPermissionService:
    @classmethod
    def get_effective_permissions(
        cls,
        *,
        agent_id: int,
        mode: str,
        surface: str,
        tool_names: list[str],
    ) -> ToolPermissionView:
        allowed_seed = list(dict.fromkeys(str(name) for name in tool_names if str(name).strip()))
        scope = [f"agent:{agent_id}", f"mode:{mode}", f"surface:{surface}"]
        reasons: list[str] = []

        with get_db() as session:
            rows = session.query(Permission).filter(Permission.agent_id == agent_id).all()

        explicit_allowed: list[str] = []
        explicit_denied: list[str] = []
        for row in rows:
            explicit_allowed.extend(str(name) for name in (row.allowed_tool_names or []))
            explicit_denied.extend(str(name) for name in (row.denied_tool_names or []))
            if row.reason:
                reasons.append(str(row.reason))

        if explicit_allowed:
            allowed_seed = [name for name in allowed_seed if name in set(explicit_allowed)]
        denied = sorted(set(explicit_denied))
        allowed = [name for name in allowed_seed if name not in denied]

        approval_required: list[str] = []
        if mode == "chat":
            denied = sorted(set(denied) | set(allowed))
            allowed = []
            reasons.append("chat mode contract disables tool execution")
        elif surface == "desktop":
            approval_required = list(allowed)
            reasons.append("desktop surface requires client-side approval/execution")

        return ToolPermissionView(
            allowed_tool_names=allowed,
            denied_tool_names=denied,
            approval_required_tool_names=approval_required,
            effective_scope=scope,
            reason=reasons,
        )

    @staticmethod
    def check_server_execution_allowed(*, permission: ToolPermissionView, tool_name: str) -> bool:
        return tool_name in permission.allowed_tool_names and tool_name not in permission.approval_required_tool_names

    @staticmethod
    def requires_client_approval(*, permission: ToolPermissionView, tool_name: str) -> bool:
        return tool_name in permission.approval_required_tool_names
