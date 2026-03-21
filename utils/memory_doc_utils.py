"""Memory document utilities for injecting metadata into markdown."""

import re

import yaml


def inject_frontmatter(body: str, **kwargs) -> str:
    """Inject or update KV metadata as YAML frontmatter in a markdown document.

    - If document has existing frontmatter: merge and overwrite keys
    - If document has no frontmatter: create new one

    Args:
        body: The markdown document (may or may not have existing frontmatter)
        **kwargs: Key-value pairs to inject/update

    Returns:
        Complete markdown document with merged YAML frontmatter

    Example:
        >>> # New frontmatter
        >>> body = "## Python GC\\n\\nPython垃圾回收..."
        >>> doc = inject_frontmatter(body, mem_type="semantic", topic="Python GC")
        >>> print(doc)
        ---
        mem_type: semantic
        topic: Python GC
        ---
        <body>

        >>> # Update existing frontmatter
        >>> old = "---\\nmem_type: episodic\\ntopic: Old Topic\\n---\\n\\n## Content"
        >>> new = inject_frontmatter(old, topic="New Topic", lang="zh")
        >>> print(new)
        ---
        mem_type: episodic
        topic: New Topic
        lang: zh
        ---
        <body>
    """
    existing = {}

    # Parse existing frontmatter if present
    pattern = r"^---\s*\n(.*?)\n---"
    match = re.match(pattern, body, re.DOTALL)
    if match:
        try:
            existing = yaml.safe_load(match.group(1)) or {}
            body = re.sub(pattern, "", body, count=1, flags=re.DOTALL).strip()
        except yaml.YAMLError:
            pass

    # Merge: new values overwrite existing
    merged = {**existing, **kwargs}

    frontmatter = yaml.dump(merged, default_flow_style=False, allow_unicode=True)
    return f"---\n{frontmatter}---\n\n{body}"
