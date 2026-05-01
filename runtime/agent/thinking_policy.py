from runtime.entities.message_entities import ThinkingOptions


class ThinkingPolicyResolver:
    @classmethod
    def resolve(cls, *, mode: str, request, agent_name: str) -> str:
        thinking = getattr(request, "thinking", None)
        if thinking and getattr(thinking, "type", None):
            return str(thinking.type)
        if agent_name == "supervisor_agent_v3":
            request.thinking = ThinkingOptions(type="adaptive")
            return "adaptive"
        if mode == "agent":
            return "adaptive"
        return "disabled"
