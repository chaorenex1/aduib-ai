# 简历项目经历自动生成

**版本**: v1.0
**更新日期**: 2025-02-24

---

## 概述

从统一记忆系统自动生成简历中的项目经历，解决：
- 项目细节遗忘
- 贡献难以量化
- 成果描述不具体
- 技术栈遗漏

---

## 数据流架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     简历项目经历生成流程                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │  项目记忆   │    │  贡献提取   │    │  成果量化   │    │  描述生成   │  │
│  │  检索      │───▶│  Contribution│───▶│  Metrics   │───▶│  Resume    │  │
│  │            │    │  Extractor  │    │  Quantifier │    │  Generator │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│        │                  │                  │                  │          │
│        ▼                  ▼                  ▼                  ▼          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │ • 决策记忆  │    │ • 角色识别  │    │ • 代码统计  │    │ • STAR格式  │  │
│  │ • 情景记忆  │    │ • 职责范围  │    │ • 性能提升  │    │ • 技术栈   │  │
│  │ • 知识记忆  │    │ • 关键贡献  │    │ • 业务影响  │    │ • 亮点突出  │  │
│  │ • Git记录  │    │ • 技术难点  │    │ • 时间节省  │    │ • 关键词   │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 数据来源

### 1. 记忆系统数据

| 数据源 | 提取内容 | 用途 |
|--------|----------|------|
| **项目范围记忆** | 项目名、时间范围、团队规模 | 基本信息 |
| **决策记忆** | 技术选型、架构决策、方案设计 | 关键贡献 |
| **情景记忆** | 解决的问题、攻克的难题 | 挑战与成就 |
| **知识记忆** | 使用的技术、学到的技能 | 技术栈 |
| **QA记忆** | 高频问题、专业知识 | 专业深度 |

### 2. 外部数据增强

```python
class ExternalDataCollector:
    """外部数据收集器"""

    async def collect_git_stats(
        self,
        project_path: str,
        user_email: str,
        time_range: tuple[datetime, datetime]
    ) -> GitStats:
        """收集 Git 统计数据"""
        return GitStats(
            commits_count=await self._count_commits(project_path, user_email, time_range),
            lines_added=await self._count_lines_added(...),
            lines_deleted=await self._count_lines_deleted(...),
            files_changed=await self._count_files_changed(...),
            pull_requests=await self._count_prs(...),
            code_reviews=await self._count_reviews(...)
        )

    async def collect_issue_stats(
        self,
        project_id: str,
        user_id: str
    ) -> IssueStats:
        """收集 Issue 统计"""
        return IssueStats(
            issues_created=...,
            issues_resolved=...,
            bugs_fixed=...,
            features_delivered=...
        )
```

---

## 贡献提取

### 1. 角色识别

```python
class RoleIdentifier:
    """角色识别器"""

    ROLE_SIGNALS = {
        "TECH_LEAD": [
            "架构设计", "技术选型", "code review", "指导", "mentor",
            "技术方案", "评审"
        ],
        "CORE_DEVELOPER": [
            "核心模块", "重构", "性能优化", "主要开发"
        ],
        "FULL_STACK": [
            "前端", "后端", "数据库", "API", "部署"
        ],
        "BACKEND": [
            "API开发", "数据库", "微服务", "后端逻辑"
        ],
        "FRONTEND": [
            "UI", "组件", "交互", "React", "Vue"
        ],
        "DEVOPS": [
            "CI/CD", "部署", "监控", "运维", "K8s"
        ]
    }

    async def identify_role(
        self,
        project_memories: list[Memory],
        decisions: list[Decision]
    ) -> ProjectRole:
        """识别用户在项目中的角色"""

        # 1. 统计信号词频率
        signal_counts = defaultdict(int)
        for memory in project_memories:
            content = memory.content.lower()
            for role, signals in self.ROLE_SIGNALS.items():
                for signal in signals:
                    if signal in content:
                        signal_counts[role] += 1

        # 2. 分析决策类型
        decision_roles = self._analyze_decision_roles(decisions)

        # 3. 综合判断
        role_scores = self._calculate_role_scores(signal_counts, decision_roles)

        return ProjectRole(
            primary=max(role_scores, key=role_scores.get),
            secondary=[r for r, s in role_scores.items() if s > 0.3][:2],
            confidence=max(role_scores.values())
        )
```

### 2. 贡献分类

```python
class ContributionType(Enum):
    """贡献类型"""

    # 技术贡献
    ARCHITECTURE = "architecture"       # 架构设计
    CORE_FEATURE = "core_feature"       # 核心功能开发
    OPTIMIZATION = "optimization"       # 性能优化
    REFACTORING = "refactoring"         # 代码重构
    BUG_FIX = "bug_fix"                 # Bug 修复
    TECH_DEBT = "tech_debt"             # 技术债务清理

    # 流程贡献
    PROCESS_IMPROVEMENT = "process"     # 流程改进
    TOOLING = "tooling"                 # 工具开发
    DOCUMENTATION = "documentation"     # 文档编写

    # 领导贡献
    TEAM_LEAD = "team_lead"             # 团队管理
    MENTORING = "mentoring"             # 指导新人
    CODE_REVIEW = "code_review"         # 代码评审


@dataclass
class Contribution:
    """贡献记录"""

    type: ContributionType
    title: str
    description: str

    # 时间范围
    start_date: date
    end_date: Optional[date]

    # 来源证据
    source_memories: list[str]
    source_decisions: list[str]
    source_commits: list[str]

    # 影响评估
    impact: ContributionImpact

    # 技术栈
    technologies: list[str]


@dataclass
class ContributionImpact:
    """贡献影响"""

    scope: str                  # "module" | "service" | "system" | "company"
    metrics: dict[str, Any]     # 量化指标
    qualitative: str            # 定性描述
```

### 3. 贡献提取器

```python
class ContributionExtractor:
    """贡献提取器"""

    async def extract_contributions(
        self,
        project_scope: str,
        time_range: tuple[datetime, datetime]
    ) -> list[Contribution]:
        """提取项目贡献"""

        contributions = []

        # 1. 从决策记忆提取架构贡献
        architecture_contributions = await self._extract_from_decisions(
            project_scope, time_range,
            categories=[DecisionCategory.ARCHITECTURE, DecisionCategory.TECHNOLOGY]
        )
        contributions.extend(architecture_contributions)

        # 2. 从情景记忆提取问题解决
        problem_solving = await self._extract_problem_solving(
            project_scope, time_range
        )
        contributions.extend(problem_solving)

        # 3. 从 Git 提取代码贡献
        code_contributions = await self._extract_from_git(
            project_scope, time_range
        )
        contributions.extend(code_contributions)

        # 4. 合并相似贡献
        merged = self._merge_similar_contributions(contributions)

        # 5. 按影响排序
        return sorted(merged, key=lambda c: c.impact.score, reverse=True)

    async def _extract_from_decisions(
        self,
        project_scope: str,
        time_range: tuple,
        categories: list[DecisionCategory]
    ) -> list[Contribution]:
        """从决策记忆提取贡献"""

        decisions = await self.decision_store.query(
            scope_prefix=project_scope,
            time_range=time_range,
            categories=categories,
            status=["DECIDED", "IMPLEMENTED"]
        )

        contributions = []
        for decision in decisions:
            contributions.append(Contribution(
                type=self._map_decision_to_contribution_type(decision),
                title=decision.title,
                description=decision.rationale,
                source_decisions=[decision.id],
                technologies=decision.metadata.get("technologies", []),
                impact=ContributionImpact(
                    scope=self._determine_scope(decision),
                    metrics=self._extract_metrics(decision),
                    qualitative=decision.expected_impact
                )
            ))

        return contributions

    async def _extract_problem_solving(
        self,
        project_scope: str,
        time_range: tuple
    ) -> list[Contribution]:
        """从情景记忆提取问题解决贡献"""

        # 查找包含"问题"、"解决"、"修复"等关键词的记忆
        memories = await self.memory_manager.retrieve(
            scope_prefix=project_scope,
            time_range=time_range,
            types=[MemoryType.EPISODIC],
            keywords=["问题", "解决", "修复", "优化", "攻克", "突破"]
        )

        # 使用 LLM 提取问题-解决对
        problem_solutions = await self._llm_extract_problems(memories)

        return [
            Contribution(
                type=ContributionType.BUG_FIX if ps.is_bug else ContributionType.OPTIMIZATION,
                title=ps.problem_title,
                description=ps.solution_description,
                source_memories=[m.id for m in ps.source_memories],
                impact=ps.impact
            )
            for ps in problem_solutions
        ]
```

---

## 成果量化

### 1. 量化维度

```python
class MetricType(Enum):
    """指标类型"""

    # 代码指标
    CODE_VOLUME = "code_volume"         # 代码量
    CODE_QUALITY = "code_quality"       # 代码质量
    TEST_COVERAGE = "test_coverage"     # 测试覆盖率

    # 性能指标
    PERFORMANCE_GAIN = "performance"    # 性能提升
    LATENCY_REDUCTION = "latency"       # 延迟降低
    THROUGHPUT_INCREASE = "throughput"  # 吞吐量提升

    # 业务指标
    USER_IMPACT = "user_impact"         # 用户影响
    COST_SAVING = "cost_saving"         # 成本节省
    REVENUE_IMPACT = "revenue"          # 营收影响

    # 效率指标
    TIME_SAVED = "time_saved"           # 时间节省
    AUTOMATION_RATE = "automation"      # 自动化率
    ERROR_REDUCTION = "error_reduction" # 错误减少


@dataclass
class QuantifiedMetric:
    """量化指标"""

    type: MetricType
    value: float
    unit: str
    comparison_base: Optional[str]     # 比较基准
    confidence: float                   # 置信度
    source: str                         # 数据来源
```

### 2. 量化器实现

```python
class MetricsQuantifier:
    """成果量化器"""

    async def quantify_contribution(
        self,
        contribution: Contribution
    ) -> list[QuantifiedMetric]:
        """量化贡献成果"""

        metrics = []

        # 1. 从记忆中提取显式指标
        explicit_metrics = await self._extract_explicit_metrics(contribution)
        metrics.extend(explicit_metrics)

        # 2. 从 Git 计算代码指标
        if contribution.source_commits:
            code_metrics = await self._calculate_code_metrics(contribution)
            metrics.extend(code_metrics)

        # 3. 推断隐式指标
        inferred_metrics = await self._infer_metrics(contribution)
        metrics.extend(inferred_metrics)

        # 4. 验证和校准
        validated = self._validate_metrics(metrics)

        return validated

    async def _extract_explicit_metrics(
        self,
        contribution: Contribution
    ) -> list[QuantifiedMetric]:
        """提取显式提到的指标"""

        # 从相关记忆中提取数字
        memories = await self.memory_manager.get_batch(contribution.source_memories)

        # 使用 LLM 提取指标
        prompt = f"""
从以下内容中提取量化指标：

{self._format_memories(memories)}

请提取：
1. 性能提升百分比（如 "提升了50%"）
2. 时间节省（如 "从2小时减少到10分钟"）
3. 规模数字（如 "处理100万条数据"）
4. 效率改进（如 "错误率降低90%"）

返回 JSON 格式：
[
  {{"type": "performance", "value": 50, "unit": "%", "description": "API响应时间提升"}}
]
"""

        response = await self.llm.generate(prompt)
        return self._parse_metrics(response)

    async def _calculate_code_metrics(
        self,
        contribution: Contribution
    ) -> list[QuantifiedMetric]:
        """计算代码相关指标"""

        commits = contribution.source_commits
        if not commits:
            return []

        stats = await self.git_analyzer.analyze_commits(commits)

        metrics = []

        # 代码行数（净增加）
        if stats.net_lines > 100:
            metrics.append(QuantifiedMetric(
                type=MetricType.CODE_VOLUME,
                value=stats.net_lines,
                unit="行",
                confidence=1.0,
                source="git"
            ))

        # 文件影响范围
        if stats.files_changed > 10:
            metrics.append(QuantifiedMetric(
                type=MetricType.CODE_VOLUME,
                value=stats.files_changed,
                unit="文件",
                confidence=1.0,
                source="git"
            ))

        return metrics

    METRIC_INFERENCE_RULES = {
        ContributionType.OPTIMIZATION: {
            "default_metric": MetricType.PERFORMANCE_GAIN,
            "typical_range": (10, 100),
            "unit": "%",
            "confidence": 0.5
        },
        ContributionType.REFACTORING: {
            "default_metric": MetricType.CODE_QUALITY,
            "typical_value": "提升可维护性",
            "confidence": 0.6
        },
        ContributionType.TOOLING: {
            "default_metric": MetricType.TIME_SAVED,
            "typical_range": (30, 80),
            "unit": "%",
            "confidence": 0.5
        }
    }
```

---

## 描述生成

### 1. STAR 格式

```python
@dataclass
class STARDescription:
    """STAR 格式描述"""

    situation: str    # 背景/挑战
    task: str         # 任务/目标
    action: str       # 行动/方案
    result: str       # 结果/成果


class STARGenerator:
    """STAR 格式生成器"""

    STAR_PROMPT = """
基于以下项目贡献信息，生成 STAR 格式的简历描述：

## 贡献信息

**类型**: {contribution_type}
**标题**: {title}
**描述**: {description}
**技术栈**: {technologies}
**量化成果**: {metrics}

## 要求

1. **Situation (背景)**: 简述项目背景和面临的挑战
2. **Task (任务)**: 明确你的职责和目标
3. **Action (行动)**: 描述你采取的具体行动和技术方案
4. **Result (成果)**: 量化结果，使用数字说明影响

## 格式要求

- 使用动词开头（设计、开发、优化、主导）
- 包含具体技术栈
- 量化成果（%提升、X倍改进、N万用户）
- 简洁有力，每条 1-2 句话

## 输出

返回单条简历描述（一句话，包含 STAR 要素）。
"""

    async def generate_star(
        self,
        contribution: Contribution,
        metrics: list[QuantifiedMetric]
    ) -> str:
        """生成 STAR 格式描述"""

        prompt = self.STAR_PROMPT.format(
            contribution_type=contribution.type.value,
            title=contribution.title,
            description=contribution.description,
            technologies=", ".join(contribution.technologies),
            metrics=self._format_metrics(metrics)
        )

        return await self.llm.generate(prompt)
```

### 2. 多种描述风格

```python
class DescriptionStyle(Enum):
    """描述风格"""

    TECHNICAL = "technical"     # 技术导向（适合技术岗位）
    BUSINESS = "business"       # 业务导向（适合管理岗位）
    CONCISE = "concise"         # 简洁风格（一句话）
    DETAILED = "detailed"       # 详细风格（多要点）


class ResumeDescriptionGenerator:
    """简历描述生成器"""

    STYLE_TEMPLATES = {
        DescriptionStyle.TECHNICAL: """
**技术栈**: {tech_stack}

{action_description}

**技术亮点**:
{technical_highlights}

**成果**: {quantified_results}
""",

        DescriptionStyle.BUSINESS: """
{business_context}

主导 {scope} 的 {initiative}，{business_impact}

**关键成果**:
{business_metrics}
""",

        DescriptionStyle.CONCISE: """
{action_verb} {what}，使用 {key_tech}，{result}
""",

        DescriptionStyle.DETAILED: """
**项目背景**: {situation}

**核心职责**:
{responsibilities}

**技术方案**:
{technical_approach}

**项目成果**:
{detailed_results}
"""
    }

    async def generate_description(
        self,
        contribution: Contribution,
        metrics: list[QuantifiedMetric],
        style: DescriptionStyle = DescriptionStyle.CONCISE
    ) -> str:
        """生成简历描述"""

        # 1. 选择模板
        template = self.STYLE_TEMPLATES[style]

        # 2. 准备数据
        data = await self._prepare_template_data(contribution, metrics, style)

        # 3. 生成描述
        if style == DescriptionStyle.CONCISE:
            return await self._generate_concise(contribution, metrics)
        else:
            return template.format(**data)

    async def _generate_concise(
        self,
        contribution: Contribution,
        metrics: list[QuantifiedMetric]
    ) -> str:
        """生成简洁一句话描述"""

        # 选择最有力的动词
        action_verb = self._select_action_verb(contribution.type)

        # 选择核心技术（最多3个）
        key_tech = contribution.technologies[:3]

        # 选择最重要的指标
        primary_metric = self._select_primary_metric(metrics)

        prompt = f"""
生成一句简历描述：

动作: {action_verb}
内容: {contribution.title}
技术: {', '.join(key_tech)}
成果: {primary_metric}

要求:
1. 以动词开头
2. 包含技术栈
3. 以量化成果结尾
4. 总长度 < 50字

示例:
- 设计并实现分布式缓存系统，基于 Redis Cluster，QPS 提升 300%
- 主导 API 网关重构，使用 Go + gRPC，延迟降低 60%
"""

        return await self.llm.generate(prompt)

    ACTION_VERBS = {
        ContributionType.ARCHITECTURE: ["设计", "架构", "规划"],
        ContributionType.CORE_FEATURE: ["开发", "实现", "构建"],
        ContributionType.OPTIMIZATION: ["优化", "提升", "改进"],
        ContributionType.REFACTORING: ["重构", "改造", "升级"],
        ContributionType.TEAM_LEAD: ["主导", "带领", "负责"],
        ContributionType.TOOLING: ["开发", "搭建", "自动化"]
    }
```

---

## 项目经历聚合

### 1. 完整项目经历结构

```python
@dataclass
class ProjectExperience:
    """项目经历"""

    # 基本信息
    project_name: str
    company: Optional[str]
    duration: str                      # "2024.01 - 2024.12"
    team_size: Optional[int]

    # 角色
    role: ProjectRole

    # 项目简介
    project_description: str

    # 贡献列表（按重要性排序）
    contributions: list[str]           # STAR 格式描述

    # 技术栈
    tech_stack: list[str]

    # 亮点标签
    highlights: list[str]              # ["核心开发者", "性能提升10x"]


class ProjectExperienceAggregator:
    """项目经历聚合器"""

    async def aggregate_project(
        self,
        project_scope: str,
        user_id: str
    ) -> ProjectExperience:
        """聚合单个项目的经历"""

        # 1. 获取项目基本信息
        project_info = await self._get_project_info(project_scope)

        # 2. 确定时间范围
        time_range = await self._determine_time_range(project_scope, user_id)

        # 3. 识别角色
        role = await self.role_identifier.identify_role(
            project_scope, user_id, time_range
        )

        # 4. 提取贡献
        contributions = await self.contribution_extractor.extract_contributions(
            project_scope, time_range
        )

        # 5. 量化成果
        quantified_contributions = []
        for contrib in contributions[:5]:  # Top 5 贡献
            metrics = await self.quantifier.quantify_contribution(contrib)
            description = await self.description_generator.generate_description(
                contrib, metrics, DescriptionStyle.CONCISE
            )
            quantified_contributions.append(description)

        # 6. 汇总技术栈
        tech_stack = self._aggregate_tech_stack(contributions)

        # 7. 生成亮点标签
        highlights = self._generate_highlights(role, contributions)

        return ProjectExperience(
            project_name=project_info.name,
            company=project_info.company,
            duration=self._format_duration(time_range),
            team_size=project_info.team_size,
            role=role,
            project_description=await self._generate_project_summary(project_info),
            contributions=quantified_contributions,
            tech_stack=tech_stack,
            highlights=highlights
        )

    def _generate_highlights(
        self,
        role: ProjectRole,
        contributions: list[Contribution]
    ) -> list[str]:
        """生成亮点标签"""

        highlights = []

        # 角色亮点
        if role.primary == "TECH_LEAD":
            highlights.append("技术负责人")
        elif role.primary == "CORE_DEVELOPER":
            highlights.append("核心开发者")

        # 贡献亮点
        for contrib in contributions[:3]:
            if contrib.impact.scope == "system":
                highlights.append("系统级影响")
            if any(m.type == MetricType.PERFORMANCE_GAIN and m.value >= 100
                   for m in contrib.impact.metrics):
                highlights.append(f"性能提升{m.value}%")

        return highlights[:4]  # 最多4个标签
```

### 2. 多项目聚合

```python
class ResumeProjectsGenerator:
    """简历项目生成器"""

    async def generate_resume_projects(
        self,
        user_id: str,
        target_role: str,                    # 目标岗位
        max_projects: int = 4,
        time_range: Optional[tuple] = None   # 可选时间范围
    ) -> list[ProjectExperience]:
        """生成简历项目列表"""

        # 1. 获取用户所有项目范围
        project_scopes = await self._get_user_projects(user_id, time_range)

        # 2. 聚合每个项目
        all_projects = []
        for scope in project_scopes:
            project = await self.aggregator.aggregate_project(scope, user_id)
            all_projects.append(project)

        # 3. 根据目标岗位评分
        scored_projects = self._score_for_role(all_projects, target_role)

        # 4. 选择最相关的项目
        selected = sorted(scored_projects, key=lambda p: p.relevance_score, reverse=True)
        selected = selected[:max_projects]

        # 5. 按时间排序（最近的在前）
        return sorted(selected, key=lambda p: p.end_date, reverse=True)

    def _score_for_role(
        self,
        projects: list[ProjectExperience],
        target_role: str
    ) -> list[ProjectExperience]:
        """根据目标岗位评分"""

        # 目标岗位关键词
        role_keywords = self._get_role_keywords(target_role)

        for project in projects:
            score = 0.0

            # 技术匹配度
            tech_match = len(set(project.tech_stack) & set(role_keywords.tech))
            score += tech_match * 0.3

            # 角色匹配度
            if project.role.primary in role_keywords.roles:
                score += 0.3

            # 贡献类型匹配
            # ...

            project.relevance_score = score

        return projects
```

---

## 输出格式

### 1. Markdown 格式

```python
class ResumeMarkdownFormatter:
    """Markdown 格式输出"""

    def format(self, projects: list[ProjectExperience]) -> str:
        output = []

        for project in projects:
            output.append(f"### {project.project_name}")

            if project.company:
                output.append(f"**{project.company}** | {project.duration}")
            else:
                output.append(f"*{project.duration}*")

            output.append("")
            output.append(f"**角色**: {project.role.primary}")

            if project.team_size:
                output.append(f"**团队规模**: {project.team_size}人")

            output.append("")
            output.append(f"> {project.project_description}")
            output.append("")

            output.append("**主要贡献**:")
            for contrib in project.contributions:
                output.append(f"- {contrib}")

            output.append("")
            output.append(f"**技术栈**: {', '.join(project.tech_stack)}")

            if project.highlights:
                output.append(f"**亮点**: {' | '.join(project.highlights)}")

            output.append("")
            output.append("---")
            output.append("")

        return "\n".join(output)
```

### 2. 输出示例

```markdown
### 统一记忆系统
**Aduib AI** | 2024.06 - 2025.02

**角色**: 技术负责人
**团队规模**: 5人

> 企业级 AI Agent 记忆管理系统，支持多类型记忆存储、智能检索和生命周期管理

**主要贡献**:
- 设计并实现统一记忆架构，整合 Redis + Milvus + Neo4j，支持百万级记忆存储
- 主导混合检索引擎开发，基于 RRF 融合算法，检索准确率提升 40%
- 优化图索引预计算机制，检索延迟从 200ms 降至 15ms（13x 提升）
- 实现决策记忆识别系统，自动提取项目决策并建立证据链

**技术栈**: Python, FastAPI, Redis, Milvus, Neo4j, LangChain

**亮点**: 核心架构师 | 性能提升13x | 系统级影响

---
```

---

## API 设计

```python
@router.post("/resume/projects")
async def generate_resume_projects(
    request: ResumeProjectsRequest,
    user: User = Depends(get_current_user)
) -> ResumeProjectsResponse:
    """
    生成简历项目经历

    请求参数:
    - target_role: 目标岗位（用于匹配度排序）
    - max_projects: 最多返回项目数
    - time_range: 可选时间范围
    - style: 描述风格 (concise | detailed | technical)
    - format: 输出格式 (markdown | json | docx)
    """

    generator = ResumeProjectsGenerator()

    projects = await generator.generate_resume_projects(
        user_id=user.id,
        target_role=request.target_role,
        max_projects=request.max_projects,
        time_range=request.time_range
    )

    # 格式化输出
    if request.format == "markdown":
        content = ResumeMarkdownFormatter().format(projects)
    elif request.format == "json":
        content = [p.dict() for p in projects]
    else:
        content = await ResumeDocxFormatter().format(projects)

    return ResumeProjectsResponse(
        projects=projects,
        formatted_content=content,
        metadata={
            "total_projects_analyzed": len(project_scopes),
            "selected_projects": len(projects)
        }
    )
```

---

## 新增故事

| ID | 优先级 | 标题 | Sprint |
|----|--------|------|--------|
| STORY-047 | P2 | 实现角色识别器 | 8 |
| STORY-048 | P2 | 实现贡献提取器 | 8 |
| STORY-049 | P2 | 实现成果量化器 | 8 |
| STORY-050 | P2 | 实现 STAR 描述生成 | 8 |
| STORY-051 | P2 | 实现项目经历聚合器 | 8 |
| STORY-052 | P3 | 实现多格式导出 | 9 |

---

## 总结

简历项目经历生成的核心流程：

```
项目范围记忆 + 决策记忆 + Git 记录
              ↓
        角色识别 (Tech Lead / Core Dev / ...)
              ↓
        贡献提取 (架构/功能/优化/修复)
              ↓
        成果量化 (显式指标 + Git统计 + 推断)
              ↓
        STAR 描述生成 (动词 + 技术 + 量化结果)
              ↓
        多项目聚合 + 岗位匹配排序
              ↓
        Markdown / JSON / DOCX 输出
```

**核心价值**：
- 自动提取项目细节，不遗忘
- 量化成果，有说服力
- 针对目标岗位优化
- 一键生成，省时省力
