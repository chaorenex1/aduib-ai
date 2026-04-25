from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field

from runtime.memory.base.contracts import MemoryContract

ALIASES = {
    "ops_runbook": "runbook",
    "ops_deployment": "deployment",
    "ops_incident": "incident",
    "ops_rollback": "rollback",
    "preferences": "preference",
    "events": "event",
    "entities": "entity",
    "tasks": "task",
    "verifications": "verification",
    "reviews": "review",
    "solutions": "solution",
    "patterns": "pattern",
    "tools": "tool",
    "skills": "skill",
    "deployments": "deployment",
    "runbooks": "runbook",
    "incidents": "incident",
    "rollbacks": "rollback",
}


class MemorySchemaField(MemoryContract):
    name: str = Field(..., min_length=1)
    type: str = Field(default="string", min_length=1)
    description: str | None = None
    merge_op: str = Field(default="patch", min_length=1)


class MemorySchemaDefinition(MemoryContract):
    memory_type: str = Field(..., min_length=1)
    source_name: str = Field(..., min_length=1)
    description: str | None = None
    directory: str = Field(..., min_length=1)
    filename_template: str = Field(..., min_length=1)
    content_template: str | None = None
    fields: list[MemorySchemaField] = Field(default_factory=list)
    path: str = Field(..., min_length=1)

    @property
    def memory_mode(self) -> str:
        return "template" if self.content_template else "simple"

    @property
    def field_merge_ops(self) -> dict[str, str]:
        return {field.name: field.merge_op for field in self.fields}


class MemorySchemaRegistry:
    def __init__(self, definitions: dict[str, MemorySchemaDefinition]) -> None:
        self._definitions = definitions

    @classmethod
    @lru_cache(maxsize=1)
    def load(cls) -> MemorySchemaRegistry:
        schema_dir = Path(__file__).resolve().parent
        definitions: dict[str, MemorySchemaDefinition] = {}
        for path in sorted(schema_dir.glob("*.yaml")):
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            source_name = str(raw.get("name") or path.stem).strip()
            memory_type = normalize_memory_type(source_name)
            fields = [MemorySchemaField(**field) for field in raw.get("fields") or []]
            try:
                display_path = path.relative_to(Path.cwd())
            except ValueError:
                display_path = path
            definitions[memory_type] = MemorySchemaDefinition(
                memory_type=memory_type,
                source_name=source_name,
                description=raw.get("description"),
                directory=str(raw.get("directory") or "").strip(),
                filename_template=str(raw.get("filename_template") or "").strip(),
                content_template=raw.get("content_template"),
                fields=fields,
                path=str(display_path).replace("\\", "/"),
            )
        return cls(definitions=definitions)

    def list(self) -> list[MemorySchemaDefinition]:
        return list(self._definitions.values())

    def get(self, memory_type: str) -> MemorySchemaDefinition | None:
        return self._definitions.get(normalize_memory_type(memory_type))

    def require(self, memory_type: str) -> MemorySchemaDefinition:
        normalized = normalize_memory_type(memory_type)
        definition = self._definitions.get(normalized)
        if definition is None:
            raise ValueError(f"unsupported memory_type: {memory_type}")
        return definition

    def summary(self) -> list[dict[str, Any]]:
        return [
            {
                "memory_type": definition.memory_type,
                "description": definition.description,
                "directory": definition.directory,
                "filename_template": definition.filename_template,
                "memory_mode": definition.memory_mode,
                "fields": [field.model_dump(mode="python") for field in definition.fields],
            }
            for definition in self.list()
        ]


def normalize_memory_type(memory_type: str) -> str:
    raw = str(memory_type or "").strip().lower()
    return ALIASES.get(raw, raw)
