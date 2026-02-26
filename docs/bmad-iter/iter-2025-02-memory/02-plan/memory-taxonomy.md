# 记忆分类体系设计

**版本**: v1.0
**更新日期**: 2025-02-24

---

## 1. 多维度分类模型

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           Memory Taxonomy                                  │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   │
│   │   SOURCE    │   │   DOMAIN    │   │    SCOPE    │   │  LIFECYCLE  │   │
│   │   来源维度   │   │   领域维度   │   │   范围维度   │   │   生命周期   │   │
│   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘   │
│          │                 │                 │                 │          │
│   ┌──────▼──────┐   ┌──────▼──────┐   ┌──────▼──────┐   ┌──────▼──────┐   │
│   │ • Chat      │   │ • Work      │   │ • Personal  │   │ • Transient │   │
│   │ • QA        │   │ • Learning  │   │ • Project   │   │ • Short     │   │
│   │ • Browse    │   │ • Life      │   │ • Team      │   │ • Long      │   │
│   │ • Document  │   │ • Hobby     │   │ • Global    │   │ • Permanent │   │
│   │ • Action    │   │ • ...       │   │             │   │             │   │
│   └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘   │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 来源维度 (Source)

记忆的原始产生来源：

```python
class MemorySource(Enum):
    # 对话类
    CHAT = "chat"                    # 普通聊天对话
    QA = "qa"                        # 问答知识
    AGENT_TASK = "agent_task"        # Agent 执行任务

    # 内容类
    BROWSE = "browse"                # 网页浏览历史
    DOCUMENT = "document"            # 文档阅读
    CODE = "code"                    # 代码相关

    # 行为类
    ACTION = "action"                # 用户操作行为
    PREFERENCE = "preference"        # 用户偏好设置
    FEEDBACK = "feedback"            # 用户反馈
```

### 来源元数据结构

```python
@dataclass
class SourceMetadata:
    source: MemorySource
    source_id: str                   # 原始记录ID (如 message_id, url)
    source_uri: Optional[str]        # 来源URI
    created_by: str                  # 创建者 (user/agent/system)
    session_id: Optional[str]        # 会话ID (对话类)
    timestamp: datetime              # 原始时间戳
```

---

## 3. 领域维度 (Domain)

记忆所属的知识/工作领域：

```python
class MemoryDomain(Enum):
    # 工作领域
    WORK = "work"                    # 工作相关
    LEARNING = "learning"            # 学习相关
    RESEARCH = "research"            # 研究相关

    # 生活领域
    LIFE = "life"                    # 日常生活
    HEALTH = "health"                # 健康相关
    FINANCE = "finance"              # 财务相关

    # 兴趣领域
    HOBBY = "hobby"                  # 兴趣爱好
    ENTERTAINMENT = "entertainment"  # 娱乐

    # 通用
    GENERAL = "general"              # 通用知识
```

### 领域层级结构 (以 WORK 为例)

```
WORK (工作)
├── PROJECT:project_name           # 项目级别
│   ├── MODULE:module_name         # 模块级别
│   │   └── TASK:task_type         # 任务级别
│   └── TOPIC:topic_name           # 主题级别
├── SKILL:skill_name               # 技能知识
└── PROCEDURE:proc_name            # 流程规范
```

```python
@dataclass
class DomainHierarchy:
    domain: MemoryDomain
    project: Optional[str] = None     # 项目名
    module: Optional[str] = None      # 模块名
    topic: Optional[str] = None       # 主题
    task_type: Optional[str] = None   # 任务类型
    tags: list[str] = field(default_factory=list)  # 自由标签
```

---

## 4. QA 工作内容分级

针对 QA 类型的记忆，设计专门的分级体系：

### 4.1 QA 分级模型

```
┌────────────────────────────────────────────────────────────────┐
│                      QA Memory Hierarchy                       │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Level 1: PROJECT (项目)                                       │
│  ├── llm-platform                                              │
│  ├── mobile-app                                                │
│  └── data-pipeline                                             │
│                                                                │
│  Level 2: MODULE (模块)                                        │
│  ├── runtime/memory          # 记忆系统                        │
│  ├── runtime/agent           # Agent 系统                      │
│  ├── runtime/rag             # RAG 系统                        │
│  └── controllers/api         # API 层                          │
│                                                                │
│  Level 3: TOPIC (主题)                                         │
│  ├── architecture            # 架构设计                        │
│  ├── implementation          # 实现细节                        │
│  ├── debugging               # 调试问题                        │
│  ├── optimization            # 性能优化                        │
│  └── best-practice           # 最佳实践                        │
│                                                                │
│  Level 4: TASK_TYPE (任务类型)                                 │
│  ├── bug-fix                 # Bug 修复                        │
│  ├── feature-dev             # 功能开发                        │
│  ├── code-review             # 代码审查                        │
│  ├── refactoring             # 重构                            │
│  └── documentation           # 文档编写                        │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### 4.2 QA 分级数据结构

```python
@dataclass
class QAClassification:
    """QA 记忆分类"""

    # 层级分类
    project: Optional[str] = None        # L1: 项目
    module: Optional[str] = None         # L2: 模块
    topic: Optional[str] = None          # L3: 主题
    task_type: Optional[str] = None      # L4: 任务类型

    # 技术栈标签
    tech_stack: list[str] = field(default_factory=list)  # ["python", "fastapi", "milvus"]

    # 重要性指标
    importance: ImportanceLevel = ImportanceLevel.MEDIUM
    frequency: FrequencyLevel = FrequencyLevel.OCCASIONAL

    # 时效性
    time_sensitivity: TimeSensitivity = TimeSensitivity.STABLE


class ImportanceLevel(Enum):
    """重要性等级"""
    CRITICAL = "critical"      # 关键知识，必须记住
    HIGH = "high"              # 高频使用
    MEDIUM = "medium"          # 一般重要
    LOW = "low"                # 可遗忘


class FrequencyLevel(Enum):
    """使用频率"""
    DAILY = "daily"            # 每日使用
    WEEKLY = "weekly"          # 每周使用
    OCCASIONAL = "occasional"  # 偶尔使用
    RARE = "rare"              # 很少使用


class TimeSensitivity(Enum):
    """时效性"""
    VOLATILE = "volatile"      # 易变 (如临时配置)
    EVOLVING = "evolving"      # 渐变 (如 API 版本)
    STABLE = "stable"          # 稳定 (如核心概念)
    PERMANENT = "permanent"    # 永久 (如基础知识)
```

---

## 5. 完整记忆分类结构

```python
@dataclass
class MemoryClassification:
    """完整记忆分类"""

    # 核心维度
    source: MemorySource                          # 来源
    domain: MemoryDomain                          # 领域
    scope: MemoryScope                            # 范围
    lifecycle: MemoryLifecycle                    # 生命周期

    # 来源详情
    source_metadata: SourceMetadata

    # 领域层级
    domain_hierarchy: DomainHierarchy

    # QA 专用分类 (仅当 source == QA)
    qa_classification: Optional[QAClassification] = None

    # 通用标签
    tags: list[str] = field(default_factory=list)

    # 自动推断的分类 (由系统填充)
    inferred_topics: list[str] = field(default_factory=list)
    inferred_entities: list[str] = field(default_factory=list)


class MemoryScope(Enum):
    """记忆范围"""
    PERSONAL = "personal"      # 个人级别
    PROJECT = "project"        # 项目级别
    TEAM = "team"              # 团队级别
    GLOBAL = "global"          # 全局级别


class MemoryLifecycle(Enum):
    """记忆生命周期"""
    TRANSIENT = "transient"    # 临时 (会话内)
    SHORT = "short"            # 短期 (数小时到数天)
    LONG = "long"              # 长期 (数周到数月)
    PERMANENT = "permanent"    # 永久
```

---

## 6. 分类索引策略

### 6.1 多维索引

```
┌─────────────────────────────────────────────────────────────┐
│                    Index Structure                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Primary Index (Milvus)                                     │
│  ├── Vector embedding                                       │
│  └── Metadata filters:                                      │
│      ├── source                                             │
│      ├── domain                                             │
│      ├── scope                                              │
│      ├── project                                            │
│      ├── module                                             │
│      └── importance                                         │
│                                                             │
│  Secondary Index (Redis)                                    │
│  ├── source:{source}:memories → Set[memory_id]             │
│  ├── domain:{domain}:memories → Set[memory_id]             │
│  ├── project:{project}:memories → Set[memory_id]           │
│  ├── tag:{tag}:memories → Set[memory_id]                   │
│  └── user:{user_id}:recent → Sorted Set (by timestamp)     │
│                                                             │
│  Graph Index (Optional Neo4j)                               │
│  ├── (Memory)-[:BELONGS_TO]->(Project)                     │
│  ├── (Memory)-[:TAGGED_WITH]->(Tag)                        │
│  ├── (Memory)-[:RELATED_TO]->(Memory)                      │
│  └── (Memory)-[:DERIVED_FROM]->(Source)                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 查询示例

```python
# 按项目+模块查询
memories = await memory_manager.search(
    query="如何实现记忆检索",
    filters={
        "source": MemorySource.QA,
        "domain": MemoryDomain.WORK,
        "project": "llm-platform",
        "module": "runtime/memory",
    },
    limit=10
)

# 按重要性+时效性查询
memories = await memory_manager.search(
    query="API 配置",
    filters={
        "importance": {"$gte": ImportanceLevel.HIGH},
        "time_sensitivity": TimeSensitivity.STABLE,
    }
)

# 按标签组合查询
memories = await memory_manager.search(
    query="性能优化",
    filters={
        "tags": {"$all": ["python", "async"]},
        "task_type": "optimization",
    }
)
```

---

## 7. 自动分类流程

```
┌─────────────────────────────────────────────────────────────┐
│                 Auto Classification Pipeline                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Input Memory                                               │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 1. Source Detection                                  │   │
│  │    • 来源类型识别 (chat/qa/browse/...)              │   │
│  │    • 来源元数据提取                                  │   │
│  └──────────────────────────┬──────────────────────────┘   │
│                             │                               │
│                             ▼                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 2. Domain Classification (LLM)                       │   │
│  │    • 领域分类 (work/learning/life/...)              │   │
│  │    • 项目/模块推断                                   │   │
│  └──────────────────────────┬──────────────────────────┘   │
│                             │                               │
│                             ▼                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 3. Topic & Task Extraction (LLM)                     │   │
│  │    • 主题识别                                        │   │
│  │    • 任务类型分类                                    │   │
│  │    • 技术栈标签                                      │   │
│  └──────────────────────────┬──────────────────────────┘   │
│                             │                               │
│                             ▼                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 4. Importance Assessment                             │   │
│  │    • 基于内容复杂度                                  │   │
│  │    • 基于用户反馈历史                                │   │
│  │    • 基于使用频率预测                                │   │
│  └──────────────────────────┬──────────────────────────┘   │
│                             │                               │
│                             ▼                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 5. Entity & Relation Extraction                      │   │
│  │    • 命名实体识别                                    │   │
│  │    • 关系三元组提取                                  │   │
│  └──────────────────────────┬──────────────────────────┘   │
│                             │                               │
│                             ▼                               │
│                    Classified Memory                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. 实现示例

### 8.1 分类器接口

```python
class MemoryClassifier:
    """记忆自动分类器"""

    def __init__(self, llm_generator: LLMGenerator):
        self.llm = llm_generator
        self.project_patterns = self._load_project_patterns()

    async def classify(
        self,
        content: str,
        source: MemorySource,
        context: Optional[dict] = None
    ) -> MemoryClassification:
        """对记忆内容进行自动分类"""

        # 1. 来源元数据
        source_metadata = self._extract_source_metadata(source, context)

        # 2. 领域分类 (LLM)
        domain_result = await self._classify_domain(content)

        # 3. QA 专用分类
        qa_classification = None
        if source == MemorySource.QA:
            qa_classification = await self._classify_qa(content, context)

        # 4. 重要性评估
        importance = self._assess_importance(content, domain_result)

        return MemoryClassification(
            source=source,
            domain=domain_result.domain,
            scope=self._infer_scope(context),
            lifecycle=self._infer_lifecycle(importance),
            source_metadata=source_metadata,
            domain_hierarchy=domain_result.hierarchy,
            qa_classification=qa_classification,
            tags=domain_result.tags,
        )

    async def _classify_qa(
        self,
        content: str,
        context: dict
    ) -> QAClassification:
        """QA 内容专用分类"""

        prompt = f"""
        分析以下 QA 内容，提取分类信息：

        内容: {content}
        上下文: {context}

        返回 JSON:
        {{
            "project": "项目名称或null",
            "module": "模块路径或null",
            "topic": "主题类型",
            "task_type": "任务类型",
            "tech_stack": ["技术标签"],
            "importance": "critical/high/medium/low",
            "time_sensitivity": "volatile/evolving/stable/permanent"
        }}
        """

        result = await self.llm.generate(prompt, response_format="json")
        return QAClassification(**result)
```

---

## 9. 与现有系统集成

### 9.1 QA Memory Service 适配

```python
# service/qa_memory_service.py 修改

class QAMemoryService:
    @staticmethod
    def create_candidate(
        project_id: str,
        question: str,
        answer: str,
        # 新增分类参数
        classification: Optional[QAClassification] = None,
        **kwargs
    ) -> QAMemory:
        # 自动分类
        if classification is None:
            classifier = MemoryClassifier(LLMGenerator())
            classification = await classifier.classify_qa(
                content=f"Q: {question}\nA: {answer}",
                context={"project_id": project_id}
            )

        # 构建统一记忆
        memory = Memory(
            type=MemoryType.SEMANTIC,
            content=answer,
            metadata=MemoryMetadata(
                source=MemorySource.QA,
                qa_classification=classification,
            )
        )

        # 存储
        return await memory_manager.store(memory)
```

---

## 10. 下一步

1. 更新 STORY-001 增加分类相关数据结构
2. 新增 STORY-001b: 实现 MemoryClassifier
3. 在 STORY-006 (SemanticMemory) 中集成分类逻辑

是否确认此分类设计并更新迭代计划?
