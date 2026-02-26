"""统一记忆系统模块。

该模块提供统一的记忆管理架构，整合工作记忆、情景记忆和语义记忆。
"""

# 基础类型总是可以导入
from runtime.memory.types.base import (
    DomainHierarchy,
    Entity,
    EntityType,
    FrequencyLevel,
    ImportanceLevel,
    Memory,
    MemoryClassification,
    MemoryDomain,
    MemoryLifecycle,
    MemoryMetadata,
    MemoryScope,
    MemorySource,
    MemoryType,
    QAClassification,
    Relation,
    SourceMetadata,
    TimeSensitivity,
)

# 可选导入，在缺失依赖时不会失败
_optional_imports = []

try:
    from runtime.memory.classifier import MemoryClassifier
    _optional_imports.append("MemoryClassifier")
except ImportError:
    MemoryClassifier = None

try:
    from runtime.memory.manager import UnifiedMemoryManager
    _optional_imports.append("UnifiedMemoryManager")
except ImportError:
    UnifiedMemoryManager = None

try:
    from runtime.memory.types.working import WorkingMemory
    _optional_imports.append("WorkingMemory")
except ImportError:
    WorkingMemory = None

# 基础类型
__all__ = [
    "DomainHierarchy",
    "Entity",
    "EntityType",
    "FrequencyLevel",
    "ImportanceLevel",
    "Memory",
    "MemoryClassification",
    "MemoryDomain",
    "MemoryLifecycle",
    "MemoryMetadata",
    "MemoryScope",
    "MemorySource",
    "MemoryType",
    "QAClassification",
    "Relation",
    "SourceMetadata",
    "TimeSensitivity",
]

# 添加可选导入到 __all__
__all__.extend(_optional_imports)
