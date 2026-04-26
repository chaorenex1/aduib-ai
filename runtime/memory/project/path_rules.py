from __future__ import annotations


def normalize_path_segment(value: str, *, fallback: str = "general") -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return fallback

    chars: list[str] = []
    last_dash = False
    for char in raw:
        if char.isalnum():
            chars.append(char)
            last_dash = False
        else:
            if not last_dash:
                chars.append("-")
                last_dash = True

    normalized = "".join(chars).strip("-")
    return normalized or fallback


def build_docs_target_path(
    *,
    project_docs_path: str,
    topic: str,
    category: str,
) -> str:
    return f"{project_docs_path}/{normalize_path_segment(topic)}/{normalize_path_segment(category)}.md"


def build_snippets_target_path(
    *,
    snippets_path: str,
    domain: str,
    topic: str,
    category: str,
) -> str:
    return (
        f"{snippets_path}/{normalize_path_segment(domain)}/"
        f"{normalize_path_segment(topic)}/{normalize_path_segment(category)}.md"
    )
