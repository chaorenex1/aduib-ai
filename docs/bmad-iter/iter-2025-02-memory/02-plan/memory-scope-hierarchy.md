# 记忆范围层级设计

**版本**: v1.0
**更新日期**: 2025-02-24

---

## 1. 范围层级关系

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Memory Scope Hierarchy                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                        个人记忆 (Personal)                        │ │
│  │                      用户的所有记忆                                │ │
│  │                                                                   │ │
│  │  ┌─────────────────────────────────────────────────────────────┐ │ │
│  │  │                    工作记忆 (Work)                          │ │ │
│  │  │                  工作相关的记忆                              │ │ │
│  │  │                                                             │ │ │
│  │  │  ┌─────────────────────────────────────────────────────┐   │ │ │
│  │  │  │              项目记忆 (Project)                     │   │ │ │
│  │  │  │            特定项目的记忆                            │   │ │ │
│  │  │  │                                                     │   │ │ │
│  │  │  │  ┌─────────────────────────────────────────────┐   │   │ │ │
│  │  │  │  │          模块记忆 (Module)                  │   │   │ │ │
│  │  │  │  │        特定模块的记忆                        │   │   │ │ │
│  │  │  │  └─────────────────────────────────────────────┘   │   │ │ │
│  │  │  │                                                     │   │ │ │
│  │  │  └─────────────────────────────────────────────────────┘   │ │ │
│  │  │                                                             │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  │                                                                   │ │
│  │  ┌─────────────────────────────────────────────────────────────┐ │ │
│  │  │                    生活记忆 (Life)                          │ │ │
│  │  │                  非工作的个人记忆                            │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  │                                                                   │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

包含关系:
Personal ⊇ Work ⊇ Project ⊇ Module
Personal ⊇ Life
```

---

## 2. 范围数据模型

### 2.1 层级定义

```python
class MemoryScopeLevel(Enum):
    """记忆范围层级"""

    # 最外层: 用户所有记忆
    PERSONAL = 0          # 个人记忆 (根节点)

    # 第二层: 大类划分
    WORK = 1              # 工作相关
    LIFE = 2              # 生活相关
    LEARNING = 3          # 学习相关

    # 第三层: 具体归属
    PROJECT = 10          # 项目
    TEAM = 11             # 团队

    # 第四层: 细分
    MODULE = 20           # 模块
    TASK = 21             # 任务


@dataclass
class MemoryScope:
    """记忆范围"""

    # 所属用户 (必须)
    user_id: str

    # 范围路径 (从根到叶)
    path: list[ScopeNode]

    # 快捷访问
    @property
    def level(self) -> MemoryScopeLevel:
        return self.path[-1].level if self.path else MemoryScopeLevel.PERSONAL

    @property
    def project_id(self) -> Optional[str]:
        for node in self.path:
            if node.level == MemoryScopeLevel.PROJECT:
                return node.id
        return None

    @property
    def module_id(self) -> Optional[str]:
        for node in self.path:
            if node.level == MemoryScopeLevel.MODULE:
                return node.id
        return None


@dataclass
class ScopeNode:
    """范围节点"""
    level: MemoryScopeLevel
    id: str
    name: str
```

### 2.2 范围路径示例

```python
# 示例1: 个人通用记忆
scope = MemoryScope(
    user_id="user_123",
    path=[
        ScopeNode(MemoryScopeLevel.PERSONAL, "user_123", "张三")
    ]
)
# 路径: Personal

# 示例2: 工作记忆
scope = MemoryScope(
    user_id="user_123",
    path=[
        ScopeNode(MemoryScopeLevel.PERSONAL, "user_123", "张三"),
        ScopeNode(MemoryScopeLevel.WORK, "work", "工作")
    ]
)
# 路径: Personal > Work

# 示例3: 项目记忆
scope = MemoryScope(
    user_id="user_123",
    path=[
        ScopeNode(MemoryScopeLevel.PERSONAL, "user_123", "张三"),
        ScopeNode(MemoryScopeLevel.WORK, "work", "工作"),
        ScopeNode(MemoryScopeLevel.PROJECT, "proj_llm", "LLM平台")
    ]
)
# 路径: Personal > Work > Project:LLM平台

# 示例4: 模块记忆
scope = MemoryScope(
    user_id="user_123",
    path=[
        ScopeNode(MemoryScopeLevel.PERSONAL, "user_123", "张三"),
        ScopeNode(MemoryScopeLevel.WORK, "work", "工作"),
        ScopeNode(MemoryScopeLevel.PROJECT, "proj_llm", "LLM平台"),
        ScopeNode(MemoryScopeLevel.MODULE, "mod_memory", "记忆系统")
    ]
)
# 路径: Personal > Work > Project:LLM平台 > Module:记忆系统
```

---

## 3. 范围继承与检索

### 3.1 向上继承

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Scope Inheritance (向上继承)                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  当前上下文: Project:LLM平台                                            │
│                                                                         │
│  检索时自动包含:                                                        │
│  ─────────────────────────────────────────────────────────────────────  │
│                                                                         │
│  Level 4: Module:记忆系统 ──┐                                          │
│                             │ (当前项目的模块记忆)                      │
│  Level 3: Project:LLM平台 ──┼─── 当前范围                              │
│                             │                                           │
│  Level 2: Work ─────────────┤ (向上继承)                               │
│                             │ 工作通用知识                              │
│  Level 1: Personal ─────────┘                                          │
│                             个人偏好、习惯                              │
│                                                                         │
│  不包含:                                                                │
│  ─────────────────────────────────────────────────────────────────────  │
│  Project:其他项目  (同级其他项目，隔离)                                 │
│  Life             (不同分支，隔离)                                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 检索策略

```python
class ScopeAwareRetriever:
    """范围感知检索器"""

    async def retrieve(
        self,
        query: str,
        current_scope: MemoryScope,
        inheritance: InheritanceMode = InheritanceMode.ANCESTORS
    ) -> list[Memory]:
        """根据范围检索记忆"""

        # 构建范围过滤器
        scope_filter = self._build_scope_filter(current_scope, inheritance)

        # 执行检索
        memories = await self.memory_service.search(
            query=query,
            scope_filter=scope_filter
        )

        # 按范围优先级排序
        memories = self._sort_by_scope_relevance(memories, current_scope)

        return memories

    def _build_scope_filter(
        self,
        current_scope: MemoryScope,
        inheritance: InheritanceMode
    ) -> ScopeFilter:
        """构建范围过滤器"""

        if inheritance == InheritanceMode.EXACT:
            # 精确匹配: 只检索当前范围
            return ScopeFilter(
                exact_path=current_scope.path
            )

        elif inheritance == InheritanceMode.ANCESTORS:
            # 向上继承: 当前范围 + 所有祖先
            return ScopeFilter(
                user_id=current_scope.user_id,
                include_paths=[
                    current_scope.path[:i+1]
                    for i in range(len(current_scope.path))
                ]
            )

        elif inheritance == InheritanceMode.DESCENDANTS:
            # 向下包含: 当前范围 + 所有子范围
            return ScopeFilter(
                user_id=current_scope.user_id,
                path_prefix=current_scope.path
            )

        elif inheritance == InheritanceMode.FULL:
            # 完整继承: 祖先 + 当前 + 子孙
            return ScopeFilter(
                user_id=current_scope.user_id,
                include_ancestors=True,
                path_prefix=current_scope.path
            )

    def _sort_by_scope_relevance(
        self,
        memories: list[Memory],
        current_scope: MemoryScope
    ) -> list[Memory]:
        """按范围相关性排序"""

        def scope_distance(memory: Memory) -> int:
            """计算范围距离 (越近越好)"""
            memory_path = memory.scope.path
            current_path = current_scope.path

            # 完全匹配
            if memory_path == current_path:
                return 0

            # 子范围
            if self._is_descendant(memory_path, current_path):
                return len(memory_path) - len(current_path)

            # 祖先范围
            if self._is_ancestor(memory_path, current_path):
                return len(current_path) - len(memory_path)

            # 不相关
            return 100

        return sorted(memories, key=lambda m: (scope_distance(m), -m.score))


class InheritanceMode(Enum):
    """继承模式"""
    EXACT = "exact"               # 精确匹配
    ANCESTORS = "ancestors"       # 向上继承 (默认)
    DESCENDANTS = "descendants"   # 向下包含
    FULL = "full"                 # 完整继承
```

---

## 4. Neo4j 图模型更新

### 4.1 范围节点

```cypher
// 用户节点 (根)
CREATE (u:User:Scope {
    id: "user_123",
    name: "张三",
    scope_level: 0
})

// 工作范围
CREATE (w:WorkScope:Scope {
    id: "user_123_work",
    name: "工作",
    scope_level: 1
})
CREATE (u)-[:HAS_SCOPE]->(w)

// 项目范围
CREATE (p:Project:Scope {
    id: "proj_llm",
    name: "LLM平台",
    scope_level: 10
})
CREATE (w)-[:HAS_SCOPE]->(p)

// 模块范围
CREATE (m:Module:Scope {
    id: "mod_memory",
    name: "记忆系统",
    scope_level: 20
})
CREATE (p)-[:HAS_SCOPE]->(m)
```

### 4.2 记忆归属

```cypher
// 记忆属于特定范围
CREATE (mem:MemoryRef {id: "mem_001"})
CREATE (mem)-[:BELONGS_TO_SCOPE]->(m:Module {id: "mod_memory"})

// 查询时: 获取范围链上的所有记忆
MATCH path = (u:User {id: $user_id})-[:HAS_SCOPE*0..]->(scope:Scope)
WHERE scope.id = $current_scope_id OR scope IN nodes(path)
MATCH (mem:MemoryRef)-[:BELONGS_TO_SCOPE]->(scope)
RETURN mem
```

---

## 5. 范围可视化

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      User: 张三 的记忆范围树                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  📁 Personal (个人)                                     [1,234 条记忆]  │
│  │                                                                      │
│  ├── 📁 Work (工作)                                       [892 条记忆]  │
│  │   │                                                                  │
│  │   ├── 📁 Project: LLM平台                              [456 条记忆]  │
│  │   │   ├── 📁 Module: runtime/memory                    [89 条记忆]   │
│  │   │   ├── 📁 Module: runtime/agent                     [67 条记忆]   │
│  │   │   ├── 📁 Module: runtime/rag                       [54 条记忆]   │
│  │   │   └── 📄 项目级记忆                                [246 条记忆]  │
│  │   │                                                                  │
│  │   ├── 📁 Project: Mobile App                           [234 条记忆]  │
│  │   │   └── ...                                                        │
│  │   │                                                                  │
│  │   └── 📄 工作通用记忆                                  [202 条记忆]  │
│  │       (跨项目的工作知识)                                             │
│  │                                                                      │
│  ├── 📁 Life (生活)                                       [189 条记忆]  │
│  │   └── ...                                                            │
│  │                                                                      │
│  ├── 📁 Learning (学习)                                   [98 条记忆]   │
│  │   └── ...                                                            │
│  │                                                                      │
│  └── 📄 个人通用记忆                                      [55 条记忆]   │
│      (偏好、习惯等)                                                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 6. 范围上下文自动推断

### 6.1 推断规则

```python
class ScopeInferrer:
    """范围推断器"""

    async def infer_scope(
        self,
        content: str,
        user_id: str,
        session_context: SessionContext
    ) -> MemoryScope:
        """从内容推断记忆范围"""

        # 规则1: 会话已绑定项目
        if session_context.current_project:
            base_scope = await self._get_project_scope(
                user_id,
                session_context.current_project
            )
        else:
            base_scope = await self._get_user_scope(user_id)

        # 规则2: 内容中提及特定模块
        module = await self._detect_module(content, base_scope)
        if module:
            return self._extend_scope(base_scope, module)

        # 规则3: 内容中提及特定项目
        project = await self._detect_project(content, user_id)
        if project:
            return await self._get_project_scope(user_id, project)

        # 规则4: 判断是否工作相关
        if await self._is_work_related(content):
            return self._extend_scope(base_scope, ScopeNode(
                level=MemoryScopeLevel.WORK,
                id="work",
                name="工作"
            ))

        return base_scope

    async def _detect_module(
        self,
        content: str,
        base_scope: MemoryScope
    ) -> Optional[ScopeNode]:
        """检测内容中提及的模块"""

        if not base_scope.project_id:
            return None

        # 获取项目的模块列表
        modules = await self.project_service.get_modules(base_scope.project_id)

        # 匹配模块关键词
        for module in modules:
            keywords = [module.name, module.path] + module.keywords
            for kw in keywords:
                if kw.lower() in content.lower():
                    return ScopeNode(
                        level=MemoryScopeLevel.MODULE,
                        id=module.id,
                        name=module.name
                    )

        return None
```

### 6.2 会话范围绑定

```python
class SessionScopeManager:
    """会话范围管理器"""

    async def bind_project(
        self,
        session_id: str,
        project_id: str
    ):
        """绑定会话到项目"""
        session = await self.session_service.get(session_id)
        session.current_scope = await self._get_project_scope(
            session.user_id,
            project_id
        )
        await self.session_service.update(session)

    async def get_effective_scope(
        self,
        session_id: str
    ) -> MemoryScope:
        """获取会话的有效范围"""
        session = await self.session_service.get(session_id)

        if session.current_scope:
            return session.current_scope

        # 默认: 用户的工作范围
        return MemoryScope(
            user_id=session.user_id,
            path=[
                ScopeNode(MemoryScopeLevel.PERSONAL, session.user_id, "个人"),
                ScopeNode(MemoryScopeLevel.WORK, "work", "工作")
            ]
        )
```

---

## 7. 范围隔离与共享

### 7.1 默认隔离

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Scope Isolation Rules                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  默认隔离:                                                              │
│  ─────────────────────────────────────────────────────────────────────  │
│                                                                         │
│  • 不同用户的记忆完全隔离                                               │
│  • 同一用户的不同项目默认隔离                                           │
│  • Work 和 Life 分支隔离                                               │
│                                                                         │
│  User A                          User B                                 │
│  ├── Work                        ├── Work                              │
│  │   ├── Project X  ─┐           │   └── Project Z                     │
│  │   └── Project Y   │隔离       │                                     │
│  └── Life           ─┘           └── Life                              │
│        │                                                                │
│        └──────────────── 隔离 ───────────────┘                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.2 显式共享

```python
class MemorySharing:
    """记忆共享服务"""

    async def share_to_scope(
        self,
        memory_id: str,
        target_scope: MemoryScope,
        share_mode: ShareMode = ShareMode.REFERENCE
    ):
        """共享记忆到另一个范围"""

        if share_mode == ShareMode.REFERENCE:
            # 引用模式: 创建引用，不复制内容
            await self._create_reference(memory_id, target_scope)

        elif share_mode == ShareMode.COPY:
            # 复制模式: 创建副本
            await self._create_copy(memory_id, target_scope)

    async def share_to_team(
        self,
        memory_id: str,
        team_id: str
    ):
        """共享记忆到团队"""
        # 创建团队可见的引用
        ...


class ShareMode(Enum):
    REFERENCE = "reference"  # 引用 (不复制)
    COPY = "copy"            # 复制
```

---

## 8. 与现有设计的对照

### 8.1 需要修改的部分

| 组件 | 现有设计 | 修改后 |
|------|----------|--------|
| `MemoryScope` | 平级枚举 | 嵌套路径结构 |
| `Memory.scope` | 单一枚举值 | `MemoryScope` 对象 |
| 检索过滤 | 简单 scope 匹配 | 范围路径匹配 + 继承 |
| Neo4j 模型 | 无范围节点 | 增加 Scope 节点和关系 |

### 8.2 数据迁移

```python
# 迁移脚本: 将旧的 scope 枚举转换为新的路径结构

OLD_TO_NEW_MAPPING = {
    "personal": [
        ScopeNode(MemoryScopeLevel.PERSONAL, "{user_id}", "个人")
    ],
    "project": [
        ScopeNode(MemoryScopeLevel.PERSONAL, "{user_id}", "个人"),
        ScopeNode(MemoryScopeLevel.WORK, "work", "工作"),
        ScopeNode(MemoryScopeLevel.PROJECT, "{project_id}", "{project_name}")
    ],
    # ...
}
```

---

## 9. 总结

### 范围层级

```
Personal (个人)           ← 用户所有记忆
├── Work (工作)           ← 工作相关
│   ├── Project A         ← 项目级
│   │   ├── Module 1      ← 模块级
│   │   └── Module 2
│   └── Project B
├── Life (生活)           ← 生活相关
└── Learning (学习)       ← 学习相关
```

### 检索继承

```
当前范围: Project A
检索包含: Personal + Work + Project A + Project A 的所有模块
不包含:   Project B, Life, Learning
```

### 关键改动

| 改动 | 说明 |
|------|------|
| `MemoryScope` 路径化 | 支持嵌套层级 |
| 范围继承检索 | 自动包含祖先范围 |
| 范围推断 | 从内容自动推断归属 |
| 范围隔离 | 不同分支默认隔离 |

---

是否确认此范围层级设计?
