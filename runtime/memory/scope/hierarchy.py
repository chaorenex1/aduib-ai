from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from runtime.memory.types.base import MemoryScope


class MemoryScopeLevel(IntEnum):
    PERSONAL = 0
    WORK = 1
    LIFE = 2
    LEARNING = 3
    PROJECT = 10
    TEAM = 11
    MODULE = 20
    TASK = 21


class ScopeNode(BaseModel):
    level: MemoryScopeLevel
    id: str
    name: str

    model_config = ConfigDict(from_attributes=True)


class ScopePath(BaseModel):
    user_id: str
    nodes: list[ScopeNode] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

    @property
    def level(self) -> MemoryScopeLevel:
        if not self.nodes:
            return MemoryScopeLevel.PERSONAL
        return self.nodes[-1].level

    @property
    def project_id(self) -> Optional[str]:
        for node in self.nodes:
            if node.level == MemoryScopeLevel.PROJECT:
                return node.id
        return None

    @property
    def module_id(self) -> Optional[str]:
        for node in self.nodes:
            if node.level == MemoryScopeLevel.MODULE:
                return node.id
        return None

    def ancestors(self) -> list[ScopePath]:
        if not self.nodes:
            return [self]

        return [
            ScopePath(user_id=self.user_id, nodes=list(self.nodes[:index]))
            for index in range(1, len(self.nodes) + 1)
        ]

    def is_ancestor_of(self, other: ScopePath) -> bool:
        if self.user_id != other.user_id:
            return False

        self_keys = self._node_keys()
        other_keys = other._node_keys()
        if len(self_keys) >= len(other_keys):
            return False
        return self_keys == other_keys[: len(self_keys)]

    def is_descendant_of(self, other: ScopePath) -> bool:
        return other.is_ancestor_of(self)

    def distance_to(self, other: ScopePath) -> int:
        if self.is_same_path(other):
            return 0
        if self.is_ancestor_of(other):
            return len(other.nodes) - len(self.nodes)
        if self.is_descendant_of(other):
            return -1 * (len(self.nodes) - len(other.nodes))
        return 100

    def to_legacy_scope(self) -> MemoryScope:
        levels = {node.level for node in self.nodes}
        if MemoryScopeLevel.MODULE in levels or MemoryScopeLevel.TASK in levels:
            return MemoryScope.MODULE
        if MemoryScopeLevel.PROJECT in levels or MemoryScopeLevel.TEAM in levels:
            return MemoryScope.PROJECT
        if (
            MemoryScopeLevel.WORK in levels
            or MemoryScopeLevel.LIFE in levels
            or MemoryScopeLevel.LEARNING in levels
        ):
            return MemoryScope.WORK
        return MemoryScope.PERSONAL

    @classmethod
    def from_legacy_scope(cls, scope_value: str | MemoryScope, user_id: str) -> ScopePath:
        scope = cls._normalize_legacy_scope(scope_value)
        if scope == MemoryScope.WORK:
            return cls.work(user_id)
        if scope == MemoryScope.PROJECT:
            return cls.project(user_id, "default", "Project")
        if scope == MemoryScope.MODULE:
            return cls.module(user_id, "default", "Project", "default", "Module")
        return cls.personal(user_id)

    @classmethod
    def personal(cls, user_id: str) -> ScopePath:
        return cls(
            user_id=user_id,
            nodes=[ScopeNode(level=MemoryScopeLevel.PERSONAL, id=user_id, name="Personal")],
        )

    @classmethod
    def work(cls, user_id: str) -> ScopePath:
        return cls(
            user_id=user_id,
            nodes=[
                ScopeNode(level=MemoryScopeLevel.PERSONAL, id=user_id, name="Personal"),
                ScopeNode(level=MemoryScopeLevel.WORK, id="work", name="Work"),
            ],
        )

    @classmethod
    def project(cls, user_id: str, project_id: str, project_name: str) -> ScopePath:
        return cls(
            user_id=user_id,
            nodes=[
                ScopeNode(level=MemoryScopeLevel.PERSONAL, id=user_id, name="Personal"),
                ScopeNode(level=MemoryScopeLevel.WORK, id="work", name="Work"),
                ScopeNode(level=MemoryScopeLevel.PROJECT, id=project_id, name=project_name),
            ],
        )

    @classmethod
    def module(
        cls,
        user_id: str,
        project_id: str,
        project_name: str,
        module_id: str,
        module_name: str,
    ) -> ScopePath:
        return cls(
            user_id=user_id,
            nodes=[
                ScopeNode(level=MemoryScopeLevel.PERSONAL, id=user_id, name="Personal"),
                ScopeNode(level=MemoryScopeLevel.WORK, id="work", name="Work"),
                ScopeNode(level=MemoryScopeLevel.PROJECT, id=project_id, name=project_name),
                ScopeNode(level=MemoryScopeLevel.MODULE, id=module_id, name=module_name),
            ],
        )

    def is_same_path(self, other: ScopePath) -> bool:
        return self.user_id == other.user_id and self._node_keys() == other._node_keys()

    def _node_keys(self) -> list[tuple[MemoryScopeLevel, str]]:
        return [(node.level, node.id) for node in self.nodes]

    @staticmethod
    def _normalize_legacy_scope(scope_value: str | MemoryScope) -> MemoryScope:
        if isinstance(scope_value, MemoryScope):
            return scope_value
        value = str(scope_value).strip().lower()
        try:
            return MemoryScope(value)
        except ValueError:
            return MemoryScope.PERSONAL


class InheritanceMode(StrEnum):
    EXACT = "exact"
    ANCESTORS = "ancestors"
    DESCENDANTS = "descendants"
    FULL = "full"


class ScopeFilter(BaseModel):
    user_id: str
    exact_path: Optional[ScopePath] = None
    include_paths: list[ScopePath] = Field(default_factory=list)
    path_prefix: Optional[ScopePath] = None
    include_ancestors: bool = False

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_scope(cls, scope: ScopePath, mode: InheritanceMode) -> ScopeFilter:
        if mode == InheritanceMode.EXACT:
            return cls(user_id=scope.user_id, exact_path=scope)
        if mode == InheritanceMode.ANCESTORS:
            return cls(user_id=scope.user_id, include_paths=scope.ancestors())
        if mode == InheritanceMode.DESCENDANTS:
            return cls(user_id=scope.user_id, path_prefix=scope)
        return cls(user_id=scope.user_id, include_paths=scope.ancestors(), path_prefix=scope, include_ancestors=True)

    def matches(self, memory_scope: ScopePath) -> bool:
        if memory_scope.user_id != self.user_id:
            return False

        if self.exact_path is not None:
            return memory_scope.is_same_path(self.exact_path)

        matched = False

        if self.include_paths:
            matched = matched or any(memory_scope.is_same_path(path) for path in self.include_paths)

        if self.path_prefix is not None:
            matched = matched or memory_scope.is_same_path(self.path_prefix)
            matched = matched or memory_scope.is_descendant_of(self.path_prefix)
            if self.include_ancestors:
                matched = matched or memory_scope.is_ancestor_of(self.path_prefix)

        if self.path_prefix is None and not self.include_paths:
            matched = True

        return matched
