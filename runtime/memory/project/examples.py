DOCS_INFERENCE_EXAMPLES: list[dict[str, object]] = [
    {
        "title": "Architecture overview",
        "topic": "architecture",
        "category": "overall-design",
    },
    {
        "title": "Architecture request flow",
        "topic": "architecture",
        "category": "workflow",
    },
]

SNIPPET_INFERENCE_EXAMPLES: list[dict[str, object]] = [
    {
        "title": "Token bucket limiter with local memory",
        "domain": "backend",
        "topic": "rate-limiting",
        "category": "token-bucket",
        "implementation": "local-memory",
    },
    {
        "title": "Token bucket limiter with redis",
        "domain": "backend",
        "topic": "rate-limiting",
        "category": "token-bucket",
        "implementation": "redis",
    },
    {
        "title": "Leaky bucket limiter",
        "domain": "backend",
        "topic": "rate-limiting",
        "category": "leaky-bucket",
        "implementation": "general",
    },
]
