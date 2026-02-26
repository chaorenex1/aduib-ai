# 分类配置设计

**版本**: v1.0
**更新日期**: 2025-02-24

---

## 1. 混合模式分类策略

```
┌─────────────────────────────────────────────────────────────────┐
│                   Hybrid Classification                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────┐        ┌─────────────────┐               │
│   │  预定义项目列表  │        │  LLM 自动推断   │               │
│   │  (配置文件)      │        │  (新项目/模块)  │               │
│   └────────┬────────┘        └────────┬────────┘               │
│            │                          │                         │
│            ▼                          ▼                         │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │                   Classification Engine                  │  │
│   │                                                          │  │
│   │  1. 尝试匹配预定义项目 (关键词/路径)                     │  │
│   │  2. 匹配失败 → LLM 推断 → 候选项目                       │  │
│   │  3. 候选项目出现 N 次 → 自动加入预定义列表               │  │
│   │                                                          │  │
│   └─────────────────────────────────────────────────────────┘  │
│            │                                                    │
│            ▼                                                    │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │                   User Custom Tags                       │  │
│   │  + 用户自定义标签 (覆盖/补充系统分类)                    │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 配置文件结构

### 2.1 项目分类配置 (YAML)

```yaml
# configs/memory/classification.yaml

version: "1.0"

# 预定义项目列表
projects:
  - id: "llm-platform"
    name: "LLM 平台"
    aliases: ["llm", "ai-platform", "aduib"]
    keywords: ["runtime", "agent", "rag", "memory"]
    modules:
      - id: "runtime/memory"
        name: "记忆系统"
        keywords: ["memory", "embedding", "graph", "retrieval"]
      - id: "runtime/agent"
        name: "Agent 系统"
        keywords: ["agent", "tool", "mcp", "callback"]
      - id: "runtime/rag"
        name: "RAG 系统"
        keywords: ["rag", "extractor", "splitter", "retrieval"]
      - id: "controllers"
        name: "API 控制层"
        keywords: ["api", "controller", "router", "endpoint"]

  - id: "mobile-app"
    name: "移动应用"
    aliases: ["app", "mobile"]
    modules:
      - id: "ui"
        name: "界面"
      - id: "logic"
        name: "业务逻辑"

# 主题类型
topics:
  - id: "architecture"
    name: "架构设计"
    keywords: ["架构", "设计", "structure", "pattern"]
  - id: "implementation"
    name: "实现细节"
    keywords: ["实现", "代码", "implement", "code"]
  - id: "debugging"
    name: "调试问题"
    keywords: ["bug", "error", "fix", "debug", "问题"]
  - id: "optimization"
    name: "性能优化"
    keywords: ["性能", "优化", "performance", "optimize"]
  - id: "best-practice"
    name: "最佳实践"
    keywords: ["最佳", "推荐", "best", "practice"]

# 任务类型
task_types:
  - id: "bug-fix"
    name: "Bug 修复"
    keywords: ["fix", "bug", "修复", "问题"]
  - id: "feature-dev"
    name: "功能开发"
    keywords: ["feature", "功能", "新增", "实现"]
  - id: "code-review"
    name: "代码审查"
    keywords: ["review", "审查", "检查"]
  - id: "refactoring"
    name: "重构"
    keywords: ["refactor", "重构", "优化结构"]
  - id: "documentation"
    name: "文档编写"
    keywords: ["doc", "文档", "说明"]

# 自动学习配置
auto_learning:
  enabled: true
  candidate_threshold: 3        # 候选项目出现 N 次后自动加入
  confirmation_required: false  # 是否需要用户确认
```

### 2.2 用户自定义标签配置

```yaml
# 存储位置: 数据库 user_tags 表 或 Redis
# 每个用户/项目可以有独立的自定义标签

user_tags:
  user_id: "user_123"
  custom_tags:
    - name: "urgent"
      color: "#ff0000"
      description: "紧急事项"
    - name: "review-needed"
      color: "#ffaa00"
      description: "需要复查"
    - name: "archived"
      color: "#888888"
      description: "已归档"

  # 自定义项目
  custom_projects:
    - id: "side-project-x"
      name: "个人项目 X"
      private: true

  # 标签别名
  tag_aliases:
    "py": "python"
    "js": "javascript"
    "ts": "typescript"
```

---

## 3. 数据库模型

### 3.1 分类配置表

```python
# models/memory_classification.py

class ProjectDefinition(Base):
    """预定义项目"""
    __tablename__ = "memory_project_definitions"

    id: str = Column(String(64), primary_key=True)
    name: str = Column(String(128), nullable=False)
    aliases: list = Column(JSON, default=list)
    keywords: list = Column(JSON, default=list)
    modules: list = Column(JSON, default=list)  # 嵌套模块定义
    is_system: bool = Column(Boolean, default=False)  # 系统预定义
    is_active: bool = Column(Boolean, default=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, onupdate=datetime.utcnow)


class CandidateProject(Base):
    """候选项目 (自动学习)"""
    __tablename__ = "memory_candidate_projects"

    id: str = Column(String(64), primary_key=True)
    name: str = Column(String(128), nullable=False)
    occurrence_count: int = Column(Integer, default=1)
    first_seen_at: datetime = Column(DateTime, default=datetime.utcnow)
    last_seen_at: datetime = Column(DateTime, default=datetime.utcnow)
    promoted: bool = Column(Boolean, default=False)  # 是否已晋升为正式项目
    sample_memories: list = Column(JSON, default=list)  # 示例记忆 ID


class UserCustomTag(Base):
    """用户自定义标签"""
    __tablename__ = "memory_user_tags"

    id: str = Column(String(64), primary_key=True)
    user_id: str = Column(String(64), nullable=False, index=True)
    name: str = Column(String(64), nullable=False)
    color: str = Column(String(7), default="#888888")
    description: str = Column(String(256))
    usage_count: int = Column(Integer, default=0)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('user_id', 'name', name='uq_user_tag'),
    )


class MemoryTagAssociation(Base):
    """记忆-标签关联"""
    __tablename__ = "memory_tag_associations"

    memory_id: str = Column(String(64), primary_key=True)
    tag_id: str = Column(String(64), primary_key=True)
    tagged_by: str = Column(String(64))  # user_id or "system"
    tagged_at: datetime = Column(DateTime, default=datetime.utcnow)
```

---

## 4. 分类 API

### 4.1 配置管理 API

```python
# controllers/memory/classification.py

router = APIRouter(prefix="/memory/classification", tags=["memory_classification"])


@router.get("/projects")
async def list_projects(include_candidates: bool = False):
    """获取项目列表"""
    projects = ClassificationService.get_projects()
    if include_candidates:
        candidates = ClassificationService.get_candidate_projects()
        return {"projects": projects, "candidates": candidates}
    return {"projects": projects}


@router.post("/projects")
async def create_project(payload: ProjectCreatePayload):
    """创建自定义项目"""
    return ClassificationService.create_project(payload)


@router.post("/projects/{project_id}/promote")
async def promote_candidate(project_id: str):
    """将候选项目提升为正式项目"""
    return ClassificationService.promote_candidate(project_id)


@router.get("/tags")
async def list_user_tags(user_id: str):
    """获取用户自定义标签"""
    return ClassificationService.get_user_tags(user_id)


@router.post("/tags")
async def create_tag(payload: TagCreatePayload):
    """创建自定义标签"""
    return ClassificationService.create_tag(payload)


@router.post("/memories/{memory_id}/tags")
async def tag_memory(memory_id: str, payload: TagMemoryPayload):
    """为记忆添加标签"""
    return ClassificationService.tag_memory(
        memory_id=memory_id,
        tags=payload.tags,
        user_id=payload.user_id
    )
```

### 4.2 分类服务

```python
# service/classification_service.py

class ClassificationService:
    """分类服务"""

    _config_cache: dict = None
    _config_loaded_at: datetime = None

    @classmethod
    def load_config(cls) -> dict:
        """加载分类配置"""
        if cls._config_cache and cls._config_loaded_at:
            # 缓存 5 分钟
            if datetime.utcnow() - cls._config_loaded_at < timedelta(minutes=5):
                return cls._config_cache

        config_path = Path("configs/memory/classification.yaml")
        if config_path.exists():
            with open(config_path) as f:
                cls._config_cache = yaml.safe_load(f)
                cls._config_loaded_at = datetime.utcnow()
        else:
            cls._config_cache = {"projects": [], "topics": [], "task_types": []}

        # 合并数据库中的自定义项目
        with get_db() as session:
            db_projects = session.query(ProjectDefinition).filter_by(is_active=True).all()
            for p in db_projects:
                if p.id not in [x["id"] for x in cls._config_cache["projects"]]:
                    cls._config_cache["projects"].append({
                        "id": p.id,
                        "name": p.name,
                        "aliases": p.aliases,
                        "keywords": p.keywords,
                        "modules": p.modules,
                    })

        return cls._config_cache

    @classmethod
    def match_project(cls, content: str, context: dict = None) -> Optional[str]:
        """匹配项目 (关键词匹配)"""
        config = cls.load_config()
        content_lower = content.lower()

        for project in config["projects"]:
            # 检查关键词
            for kw in project.get("keywords", []):
                if kw.lower() in content_lower:
                    return project["id"]
            # 检查别名
            for alias in project.get("aliases", []):
                if alias.lower() in content_lower:
                    return project["id"]

        return None

    @classmethod
    async def infer_project(cls, content: str, llm: LLMGenerator) -> Optional[str]:
        """LLM 推断项目"""
        config = cls.load_config()
        project_names = [p["name"] for p in config["projects"]]

        prompt = f"""
        分析以下内容，判断它属于哪个项目，或者是否是新项目。

        已知项目: {project_names}

        内容: {content[:500]}

        返回 JSON:
        {{
            "project_id": "匹配的项目ID或null",
            "new_project_name": "如果是新项目，给出名称，否则null",
            "confidence": 0.0-1.0
        }}
        """

        result = await llm.generate(prompt, response_format="json")
        return result

    @classmethod
    def record_candidate(cls, project_name: str, memory_id: str):
        """记录候选项目"""
        with get_db() as session:
            candidate = session.query(CandidateProject).filter_by(name=project_name).first()
            if candidate:
                candidate.occurrence_count += 1
                candidate.last_seen_at = datetime.utcnow()
                if memory_id not in candidate.sample_memories:
                    candidate.sample_memories = candidate.sample_memories + [memory_id]
            else:
                candidate = CandidateProject(
                    id=str(uuid4()),
                    name=project_name,
                    sample_memories=[memory_id]
                )
                session.add(candidate)

            # 检查是否达到晋升阈值
            config = cls.load_config()
            threshold = config.get("auto_learning", {}).get("candidate_threshold", 3)
            if candidate.occurrence_count >= threshold and not candidate.promoted:
                cls.promote_candidate(candidate.id)

            session.commit()
```

---

## 5. 用户标签交互流程

```
┌─────────────────────────────────────────────────────────────────┐
│                    User Tagging Flow                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. 创建记忆时                                                   │
│     ┌─────────────────────────────────────────────┐             │
│     │ POST /memory                                 │             │
│     │ {                                            │             │
│     │   "content": "...",                          │             │
│     │   "tags": ["python", "urgent", "my-custom"]  │ ← 用户指定  │
│     │ }                                            │             │
│     └─────────────────────────────────────────────┘             │
│                         │                                        │
│                         ▼                                        │
│     ┌─────────────────────────────────────────────┐             │
│     │ 系统处理:                                    │             │
│     │ • "python" → 匹配系统标签                    │             │
│     │ • "urgent" → 匹配用户自定义标签              │             │
│     │ • "my-custom" → 自动创建新用户标签           │             │
│     └─────────────────────────────────────────────┘             │
│                                                                 │
│  2. 后续标记                                                     │
│     ┌─────────────────────────────────────────────┐             │
│     │ POST /memory/{id}/tags                       │             │
│     │ { "tags": ["review-needed"] }                │             │
│     └─────────────────────────────────────────────┘             │
│                                                                 │
│  3. 按标签搜索                                                   │
│     ┌─────────────────────────────────────────────┐             │
│     │ GET /memory/search?tags=urgent,python        │             │
│     └─────────────────────────────────────────────┘             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. 更新迭代故事

新增故事:

| Story ID | 标题 | 优先级 |
|----------|------|--------|
| STORY-001b | 实现 MemoryClassifier | P0 |
| STORY-001c | 分类配置管理 | P1 |
| STORY-001d | 用户自定义标签 | P1 |

是否确认并更新迭代计划?
