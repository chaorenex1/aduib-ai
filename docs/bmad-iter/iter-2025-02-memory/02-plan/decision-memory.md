# 决策记忆设计

**版本**: v1.0
**更新日期**: 2025-02-24

---

## 1. 什么是决策记忆

决策记忆是一种特殊的语义记忆，记录项目中的关键决策及其演变过程。

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Decision Memory                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  普通记忆: "讨论了使用 Redis 还是 Memcached"                            │
│                              ↓                                          │
│  决策记忆: "决定使用 Redis 作为缓存方案，因为支持持久化和数据结构"       │
│                              ↓                                          │
│  执行证据: "已在 config.py 中配置 Redis 连接"                           │
│                              ↓                                          │
│  后续变更: "决定从 Redis 迁移到 Redis Cluster，因为单机容量不足"        │
│                                                                         │
│  ════════════════════════════════════════════════════════════════════  │
│                                                                         │
│  决策时间线:                                                            │
│                                                                         │
│  2025-01-05        2025-01-20         2025-02-15                       │
│      │                 │                  │                             │
│      ▼                 ▼                  ▼                             │
│  ┌────────┐       ┌────────┐        ┌────────┐                         │
│  │ 决策   │──────▶│ 执行   │───────▶│ 变更   │                         │
│  │ 使用   │       │ 已配置 │        │ 迁移到 │                         │
│  │ Redis  │       │ Redis  │        │ Cluster│                         │
│  └────────┘       └────────┘        └────────┘                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 决策生命周期

### 2.1 决策状态

```python
class DecisionStatus(Enum):
    """决策状态"""

    # 讨论阶段
    PROPOSED = "proposed"          # 提议中
    UNDER_REVIEW = "under_review"  # 评审中

    # 确定阶段
    DECIDED = "decided"            # 已决定
    APPROVED = "approved"          # 已批准 (需要审批的决策)

    # 执行阶段
    IMPLEMENTING = "implementing"  # 执行中
    IMPLEMENTED = "implemented"    # 已执行

    # 变更阶段
    SUPERSEDED = "superseded"      # 被替代
    DEPRECATED = "deprecated"      # 已废弃
    REVERTED = "reverted"          # 已回滚
```

### 2.2 状态流转

```
                                    ┌──────────────┐
                                    │   PROPOSED   │
                                    └──────┬───────┘
                                           │
                              ┌────────────┴────────────┐
                              ▼                         ▼
                     ┌──────────────┐          ┌──────────────┐
                     │ UNDER_REVIEW │          │   DECIDED    │ (无需审批)
                     └──────┬───────┘          └──────┬───────┘
                            │                         │
                            ▼                         │
                     ┌──────────────┐                 │
                     │   APPROVED   │◀────────────────┘
                     └──────┬───────┘
                            │
                            ▼
                     ┌──────────────┐
                     │ IMPLEMENTING │
                     └──────┬───────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
       ┌────────────┐ ┌──────────┐ ┌──────────┐
       │IMPLEMENTED │ │ REVERTED │ │DEPRECATED│
       └─────┬──────┘ └──────────┘ └──────────┘
             │
             │ (新决策替代)
             ▼
       ┌──────────────┐
       │  SUPERSEDED  │
       └──────────────┘
```

---

## 3. 决策数据模型

### 3.1 核心结构

```python
@dataclass
class Decision:
    """决策实体"""

    id: str                              # 决策ID
    title: str                           # 决策标题
    summary: str                         # 决策摘要
    context: str                         # 决策背景/问题描述
    decision: str                        # 决策内容
    rationale: str                       # 决策理由
    alternatives: list[Alternative]      # 考虑过的备选方案
    consequences: list[str]              # 预期影响

    # 分类
    category: DecisionCategory           # 决策类别
    scope: DecisionScope                 # 影响范围
    priority: DecisionPriority           # 优先级

    # 关联
    project_id: str                      # 所属项目
    module_ids: list[str]                # 涉及模块
    related_decisions: list[str]         # 相关决策ID
    supersedes: Optional[str]            # 替代的决策ID

    # 状态
    status: DecisionStatus
    decided_at: Optional[datetime]
    decided_by: Optional[str]
    implemented_at: Optional[datetime]

    # 证据
    evidence: list[Evidence]             # 执行证据
    source_memories: list[str]           # 来源记忆ID

    # 元数据
    confidence: float                    # 识别置信度
    created_at: datetime
    updated_at: datetime


class DecisionCategory(Enum):
    """决策类别"""
    ARCHITECTURE = "architecture"        # 架构决策
    TECHNOLOGY = "technology"            # 技术选型
    DESIGN = "design"                    # 设计决策
    PROCESS = "process"                  # 流程决策
    REQUIREMENT = "requirement"          # 需求决策
    SECURITY = "security"                # 安全决策
    PERFORMANCE = "performance"          # 性能决策
    COST = "cost"                        # 成本决策


class DecisionScope(Enum):
    """影响范围"""
    GLOBAL = "global"                    # 全局影响
    PROJECT = "project"                  # 项目级
    MODULE = "module"                    # 模块级
    COMPONENT = "component"              # 组件级


@dataclass
class Alternative:
    """备选方案"""
    name: str
    description: str
    pros: list[str]                      # 优点
    cons: list[str]                      # 缺点
    rejected_reason: str                 # 未选择原因


@dataclass
class Evidence:
    """执行证据"""
    id: str
    type: EvidenceType
    description: str
    reference: str                       # 引用 (文件路径/commit/PR)
    verified: bool                       # 是否已验证
    verified_at: Optional[datetime]
    verified_by: Optional[str]


class EvidenceType(Enum):
    """证据类型"""
    CODE_COMMIT = "code_commit"          # Git commit
    PULL_REQUEST = "pull_request"        # PR
    CONFIG_CHANGE = "config_change"      # 配置变更
    DOCUMENT = "document"                # 文档
    TEST_RESULT = "test_result"          # 测试结果
    DEPLOYMENT = "deployment"            # 部署记录
    MANUAL_CONFIRM = "manual_confirm"    # 人工确认
```

### 3.2 Neo4j 图模型

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Decision Graph Model                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  节点类型:                                                              │
│  ─────────────────────────────────────────────────────────────────────  │
│                                                                         │
│  (Decision) - 决策节点                                                  │
│  {                                                                      │
│    id, title, summary, category, scope,                                │
│    status, decided_at, confidence                                      │
│  }                                                                      │
│                                                                         │
│  (Evidence) - 证据节点                                                  │
│  {                                                                      │
│    id, type, description, reference, verified                          │
│  }                                                                      │
│                                                                         │
│  (Alternative) - 备选方案节点                                           │
│  {                                                                      │
│    id, name, description, rejected_reason                              │
│  }                                                                      │
│                                                                         │
│  关系类型:                                                              │
│  ─────────────────────────────────────────────────────────────────────  │
│                                                                         │
│  (Decision)-[:SUPERSEDES]->(Decision)      # 替代关系                   │
│  (Decision)-[:RELATED_TO]->(Decision)      # 相关关系                   │
│  (Decision)-[:AFFECTS]->(Module)           # 影响模块                   │
│  (Decision)-[:BELONGS_TO]->(Project)       # 所属项目                   │
│  (Decision)-[:DECIDED_BY]->(User)          # 决策者                     │
│  (Decision)-[:HAS_EVIDENCE]->(Evidence)    # 执行证据                   │
│  (Decision)-[:CONSIDERED]->(Alternative)   # 考虑过的方案               │
│  (Decision)-[:EXTRACTED_FROM]->(MemoryRef) # 来源记忆                   │
│  (Evidence)-[:VERIFIED_BY]->(User)         # 验证者                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 决策识别

### 4.1 识别信号

```python
class DecisionSignals:
    """决策识别信号"""

    # 强信号 - 明确的决策表述
    STRONG_PATTERNS = [
        r"决定(使用|采用|选择|实施|放弃)",
        r"(确定|敲定|最终)方案",
        r"(经过|经|综合).*?(讨论|评估|考虑).*?(决定|采用)",
        r"ADR[:\s]*",  # Architecture Decision Record
        r"技术选型[:\s]*",
        r"(we|I)\s+(decided|choose|selected|agreed)",
        r"(decision|conclusion)[:\s]",
    ]

    # 中信号 - 可能的决策
    MEDIUM_PATTERNS = [
        r"(应该|需要|必须)(使用|采用)",
        r"(建议|推荐)(使用|采用).*?(因为|由于)",
        r"(优先|首选|默认)(使用|选择)",
        r"(will|should|must)\s+use",
    ]

    # 弱信号 - 需要上下文确认
    WEAK_PATTERNS = [
        r"(考虑|计划|打算)(使用|采用)",
        r"(可能|或许)(会|要)",
        r"(might|may|could)\s+use",
    ]

    # 变更信号
    CHANGE_PATTERNS = [
        r"(迁移|切换|替换|升级)(到|为)",
        r"(不再|停止|放弃)(使用|采用)",
        r"(migrate|switch|replace|upgrade)\s+(to|from)",
        r"(deprecate|abandon|remove)",
    ]

    # 执行信号
    EXECUTION_PATTERNS = [
        r"(已|完成)(实现|配置|部署|上线)",
        r"(implemented|deployed|configured|completed)",
        r"(merged|committed)\s+.*?(PR|pull request)",
    ]
```

### 4.2 识别流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Decision Recognition Pipeline                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  输入: 记忆内容 (对话/文档/commit message)                               │
│     │                                                                   │
│     ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Step 1: 信号检测                                                │   │
│  │ • 正则匹配强/中/弱信号                                          │   │
│  │ • 计算初始置信度                                                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│     │ 置信度 > 0.3                                                     │
│     ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Step 2: LLM 决策提取                                            │   │
│  │ • 提取决策标题、内容、理由                                       │   │
│  │ • 识别备选方案                                                  │   │
│  │ • 分类 (架构/技术选型/设计...)                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│     │                                                                   │
│     ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Step 3: 去重与关联                                              │   │
│  │ • 检查是否已存在相似决策                                        │   │
│  │ • 判断: 新决策 / 更新 / 变更                                    │   │
│  │ • 关联相关决策                                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│     │                                                                   │
│     ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Step 4: 证据收集                                                │   │
│  │ • 搜索相关 commit/PR                                            │   │
│  │ • 检查配置文件变更                                              │   │
│  │ • 关联文档更新                                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│     │                                                                   │
│     ▼                                                                   │
│  输出: Decision 实体 + Evidence 列表                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.3 LLM 提取 Prompt

```python
DECISION_EXTRACTION_PROMPT = """
分析以下内容，提取其中的决策信息。

内容:
{content}

上下文:
- 项目: {project}
- 时间: {timestamp}
- 来源: {source}

如果内容包含决策，返回 JSON:
{
    "is_decision": true,
    "confidence": 0.0-1.0,
    "decision": {
        "title": "简短标题 (<50字)",
        "summary": "一句话摘要",
        "context": "决策背景/问题描述",
        "decision": "具体决策内容",
        "rationale": "决策理由",
        "category": "architecture|technology|design|process|requirement|security|performance|cost",
        "scope": "global|project|module|component",
        "alternatives": [
            {
                "name": "备选方案名",
                "pros": ["优点1", "优点2"],
                "cons": ["缺点1"],
                "rejected_reason": "未选择原因"
            }
        ],
        "consequences": ["影响1", "影响2"],
        "affected_modules": ["module1", "module2"],
        "status": "proposed|decided|implementing|implemented"
    }
}

如果不是决策，返回:
{
    "is_decision": false,
    "reason": "不是决策的原因"
}
"""
```

---

## 5. 证据验证

### 5.1 自动证据收集

```python
class EvidenceCollector:
    """证据收集器"""

    async def collect_evidence(
        self,
        decision: Decision,
        project_path: str
    ) -> list[Evidence]:
        """收集决策的执行证据"""
        evidence = []

        # 1. 搜索相关 Git commits
        commits = await self._search_commits(decision, project_path)
        for commit in commits:
            evidence.append(Evidence(
                type=EvidenceType.CODE_COMMIT,
                description=commit.message,
                reference=commit.sha,
                verified=False
            ))

        # 2. 搜索相关 PR
        prs = await self._search_pull_requests(decision)
        for pr in prs:
            evidence.append(Evidence(
                type=EvidenceType.PULL_REQUEST,
                description=pr.title,
                reference=pr.url,
                verified=pr.merged
            ))

        # 3. 检查配置文件变更
        config_changes = await self._check_config_changes(decision, project_path)
        for change in config_changes:
            evidence.append(Evidence(
                type=EvidenceType.CONFIG_CHANGE,
                description=change.description,
                reference=change.file_path,
                verified=True
            ))

        # 4. 搜索相关文档
        docs = await self._search_documents(decision)
        for doc in docs:
            evidence.append(Evidence(
                type=EvidenceType.DOCUMENT,
                description=doc.title,
                reference=doc.path,
                verified=True
            ))

        return evidence

    async def _search_commits(
        self,
        decision: Decision,
        project_path: str
    ) -> list[Commit]:
        """搜索相关 commits"""
        keywords = self._extract_keywords(decision)

        # 搜索 commit message 包含关键词的提交
        cmd = f"git log --oneline --grep='{keywords}' --since='{decision.decided_at}'"
        ...

    async def _check_config_changes(
        self,
        decision: Decision,
        project_path: str
    ) -> list[ConfigChange]:
        """检查配置变更"""
        # 根据决策类型检查相关配置文件
        if decision.category == DecisionCategory.TECHNOLOGY:
            # 检查 requirements.txt, package.json, pyproject.toml
            ...
        elif decision.category == DecisionCategory.ARCHITECTURE:
            # 检查架构相关配置
            ...
```

### 5.2 证据验证规则

```python
class EvidenceValidator:
    """证据验证器"""

    VALIDATION_RULES = {
        DecisionCategory.TECHNOLOGY: {
            "required_evidence": [
                EvidenceType.CONFIG_CHANGE,  # 必须有配置变更
            ],
            "optional_evidence": [
                EvidenceType.CODE_COMMIT,
                EvidenceType.PULL_REQUEST,
            ],
            "verification_checks": [
                "dependency_exists",         # 依赖是否存在
                "import_found",              # 代码中是否有 import
            ]
        },
        DecisionCategory.ARCHITECTURE: {
            "required_evidence": [
                EvidenceType.DOCUMENT,       # 必须有文档
            ],
            "optional_evidence": [
                EvidenceType.CODE_COMMIT,
            ],
            "verification_checks": [
                "structure_matches",         # 代码结构是否匹配
            ]
        }
    }

    async def validate_decision(
        self,
        decision: Decision,
        evidence: list[Evidence]
    ) -> ValidationResult:
        """验证决策是否真实执行"""

        rules = self.VALIDATION_RULES.get(decision.category, {})
        required = rules.get("required_evidence", [])
        checks = rules.get("verification_checks", [])

        # 检查必要证据
        evidence_types = {e.type for e in evidence}
        missing_required = set(required) - evidence_types

        if missing_required:
            return ValidationResult(
                valid=False,
                confidence=0.3,
                reason=f"缺少必要证据: {missing_required}"
            )

        # 执行验证检查
        check_results = []
        for check in checks:
            result = await self._run_check(check, decision, evidence)
            check_results.append(result)

        # 计算置信度
        passed_checks = sum(1 for r in check_results if r.passed)
        confidence = passed_checks / len(checks) if checks else 0.8

        return ValidationResult(
            valid=confidence >= 0.6,
            confidence=confidence,
            checks=check_results
        )
```

---

## 6. 决策时间线

### 6.1 时间线数据结构

```python
@dataclass
class DecisionTimeline:
    """决策时间线"""

    decision_id: str
    title: str
    events: list[TimelineEvent]


@dataclass
class TimelineEvent:
    """时间线事件"""

    timestamp: datetime
    type: TimelineEventType
    description: str
    actor: Optional[str]              # 操作人
    evidence: Optional[Evidence]      # 关联证据
    metadata: dict


class TimelineEventType(Enum):
    """事件类型"""
    PROPOSED = "proposed"             # 提议
    DISCUSSED = "discussed"           # 讨论
    DECIDED = "decided"               # 决定
    APPROVED = "approved"             # 批准
    STARTED = "started"               # 开始执行
    PROGRESS = "progress"             # 执行进度
    COMPLETED = "completed"           # 执行完成
    VERIFIED = "verified"             # 验证通过
    CHANGED = "changed"               # 变更
    SUPERSEDED = "superseded"         # 被替代
    REVERTED = "reverted"             # 回滚
```

### 6.2 时间线查询

```cypher
// 获取决策时间线
MATCH (d:Decision {id: $decision_id})
OPTIONAL MATCH (d)-[:HAS_EVIDENCE]->(e:Evidence)
OPTIONAL MATCH (d)-[:SUPERSEDES]->(old:Decision)
OPTIONAL MATCH (new:Decision)-[:SUPERSEDES]->(d)
OPTIONAL MATCH (d)-[:EXTRACTED_FROM]->(m:MemoryRef)
RETURN d,
       collect(DISTINCT e) as evidence,
       old as superseded_decision,
       new as superseding_decision,
       collect(DISTINCT m) as source_memories
ORDER BY d.decided_at
```

### 6.3 时间线可视化

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Decision Timeline: 缓存方案选型                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  2025-01-05                                                            │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 💬 PROPOSED                                                     │   │
│  │ "讨论缓存方案，考虑 Redis 和 Memcached"                          │   │
│  │ 来源: 会话 sess_001                                              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│      │                                                                  │
│      ▼                                                                  │
│  2025-01-08                                                            │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ ✅ DECIDED                                                      │   │
│  │ "决定使用 Redis，因为支持持久化和丰富数据结构"                    │   │
│  │ 决策者: 张三                                                     │   │
│  │ 备选方案: Memcached (rejected: 不支持持久化)                     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│      │                                                                  │
│      ▼                                                                  │
│  2025-01-10                                                            │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 🔨 STARTED                                                      │   │
│  │ "开始实施 Redis 集成"                                            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│      │                                                                  │
│      ▼                                                                  │
│  2025-01-15                                                            │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 📝 PROGRESS                                                     │   │
│  │ "PR #123: Add Redis cache layer"                                │   │
│  │ 证据: github.com/project/pull/123                               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│      │                                                                  │
│      ▼                                                                  │
│  2025-01-20                                                            │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ ✅ COMPLETED + VERIFIED                                         │   │
│  │ "Redis 集成完成，配置已更新"                                     │   │
│  │ 证据:                                                            │   │
│  │ • configs/cache.yaml (CONFIG_CHANGE) ✓                          │   │
│  │ • commit abc123 (CODE_COMMIT) ✓                                 │   │
│  │ • PR #123 merged (PULL_REQUEST) ✓                               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│      │                                                                  │
│      │ (2个月后)                                                       │
│      ▼                                                                  │
│  2025-03-15                                                            │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 🔄 SUPERSEDED                                                   │   │
│  │ "迁移到 Redis Cluster，单机容量不足"                             │   │
│  │ 新决策: DEC-002                                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 7. API 设计

### 7.1 决策查询 API

```python
router = APIRouter(prefix="/decisions", tags=["decisions"])


@router.get("/")
async def list_decisions(
    project_id: str = None,
    category: DecisionCategory = None,
    status: DecisionStatus = None,
    since: datetime = None,
    limit: int = 20
):
    """查询决策列表"""
    ...


@router.get("/{decision_id}")
async def get_decision(decision_id: str):
    """获取决策详情"""
    ...


@router.get("/{decision_id}/timeline")
async def get_decision_timeline(decision_id: str):
    """获取决策时间线"""
    ...


@router.get("/{decision_id}/evidence")
async def get_decision_evidence(decision_id: str):
    """获取决策证据"""
    ...


@router.post("/{decision_id}/verify")
async def verify_decision(decision_id: str):
    """验证决策执行状态"""
    ...


@router.get("/project/{project_id}/timeline")
async def get_project_decision_timeline(
    project_id: str,
    category: DecisionCategory = None
):
    """获取项目决策时间线"""
    ...


@router.get("/search")
async def search_decisions(
    query: str,
    project_id: str = None
):
    """搜索决策"""
    ...
```

---

## 8. 集成到记忆系统

### 8.1 自动识别触发

```python
class MemoryProcessor:
    """记忆处理器 - 增加决策识别"""

    async def process_memory(self, memory: Memory) -> Memory:
        # ... 其他处理 ...

        # 决策识别
        if memory.type == MemoryType.SEMANTIC:
            decision = await self.decision_recognizer.recognize(memory)
            if decision and decision.confidence >= 0.6:
                # 存储决策
                await self.decision_service.save(decision)
                # 关联记忆
                memory.decision_id = decision.id
                memory.tags.append("decision")

        return memory
```

### 8.2 证据持续收集

```python
class DecisionEvidenceWatcher:
    """决策证据监控"""

    async def on_git_push(self, commits: list[Commit]):
        """Git 推送时检查是否是决策证据"""
        for commit in commits:
            # 搜索相关的未验证决策
            decisions = await self._find_related_decisions(commit.message)
            for decision in decisions:
                evidence = Evidence(
                    type=EvidenceType.CODE_COMMIT,
                    description=commit.message,
                    reference=commit.sha,
                    verified=True
                )
                await self.decision_service.add_evidence(decision.id, evidence)
                await self._update_decision_status(decision)

    async def on_config_change(self, file_path: str, diff: str):
        """配置变更时检查是否是决策证据"""
        ...
```

---

## 9. 新增迭代故事

| Story ID | 标题 | 优先级 |
|----------|------|--------|
| **STORY-017** | **决策数据模型** | **P1** |
| **STORY-018** | **决策识别器** | **P1** |
| **STORY-019** | **证据收集与验证** | **P2** |
| **STORY-020** | **决策时间线** | **P2** |
| **STORY-021** | **决策 API** | **P2** |

---

是否确认此设计?
