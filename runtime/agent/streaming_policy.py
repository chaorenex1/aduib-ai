class StreamingPolicyResolver:
    @classmethod
    def resolve(cls, *, request) -> str:
        return "streaming" if bool(getattr(request, "stream", False)) else "non_streaming"
