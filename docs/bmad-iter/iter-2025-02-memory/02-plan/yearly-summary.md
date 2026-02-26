# 年终总结生成设计

**版本**: v1.0
**更新日期**: 2025-02-24

---

## 概述

从统一记忆系统生成年终总结，需要：
1. 跨时间范围检索记忆
2. 多维度聚合分析
3. 提取关键洞察
4. 生成结构化报告

---

## 数据流架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        年终总结生成流程                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│  │ 时间范围检索  │───▶│  多维度聚合   │───▶│  洞察提取    │              │
│  │ (365天记忆)  │    │ (项目/领域)   │    │ (LLM分析)   │              │
│  └──────────────┘    └──────────────┘    └──────────────┘              │
│         │                   │                   │                       │
│         ▼                   ▼                   ▼                       │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│  │  Episodic    │    │  统计指标    │    │  成就识别    │              │
│  │  Semantic    │    │  趋势分析    │    │  成长轨迹    │              │
│  │  Decision    │    │  热力图      │    │  未来建议    │              │
│  └──────────────┘    └──────────────┘    └──────────────┘              │
│                                                                         │
│                              │                                          │
│                              ▼                                          │
│                    ┌──────────────────┐                                 │
│                    │   年终总结报告    │                                 │
│                    │  (Markdown/PDF)  │                                 │
│                    └──────────────────┘                                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 数据源与检索

### 1. 检索的记忆类型

| 记忆类型 | 贡献内容 | 检索方式 |
|----------|----------|----------|
| **Episodic** | 时间线事件、会话历史 | 时间范围查询 |
| **Semantic** | 学到的知识、技能 | 主题聚类 |
| **Decision** | 关键决策、选择 | 确定性过滤 |
| **QA Memory** | 问答记录、高频问题 | 访问频次排序 |

### 2. 检索策略

```python
@dataclass
class YearlySummaryQuery:
    """年终总结检索参数"""
    user_id: str
    year: int
    scope: MemoryScope              # 可选：限定范围
    include_types: list[MemoryType] # 包含的记忆类型

    # 过滤条件
    min_importance: float = 0.3     # 最低重要性
    min_certainty: str = "INFERRED" # 决策最低确定性
    exclude_archived: bool = True   # 排除已归档

    # 聚合维度
    group_by: list[str] = field(default_factory=lambda: [
        "scope.project",
        "domain",
        "month"
    ])
```

### 3. 时间分片检索

```python
class YearlyRetriever:
    """年度记忆检索器"""

    async def retrieve_by_quarters(
        self,
        query: YearlySummaryQuery
    ) -> dict[str, list[Memory]]:
        """按季度检索，减少单次查询压力"""
        results = {}

        for quarter in ["Q1", "Q2", "Q3", "Q4"]:
            start, end = self._quarter_range(query.year, quarter)

            memories = await self.memory_manager.retrieve(
                user_id=query.user_id,
                time_range=(start, end),
                scope=query.scope,
                types=query.include_types,
                min_importance=query.min_importance,
                limit=1000  # 每季度最多1000条
            )

            results[quarter] = memories

        return results

    async def retrieve_decisions(
        self,
        query: YearlySummaryQuery
    ) -> list[Decision]:
        """检索年度决策"""
        return await self.decision_store.query(
            user_id=query.user_id,
            year=query.year,
            min_certainty=query.min_certainty,
            status=["DECIDED", "IMPLEMENTED"],  # 已确认的决策
            order_by="importance DESC"
        )
```

---

## 多维度聚合

### 1. 聚合维度

```python
class YearlyAggregator:
    """年度数据聚合器"""

    def aggregate(
        self,
        memories: list[Memory],
        decisions: list[Decision]
    ) -> YearlyAggregation:
        return YearlyAggregation(
            # 按范围聚合
            by_scope=self._aggregate_by_scope(memories),

            # 按领域聚合
            by_domain=self._aggregate_by_domain(memories),

            # 按月份聚合（活跃度热力图）
            by_month=self._aggregate_by_month(memories),

            # 按主题聚合（知识图谱）
            by_topic=self._aggregate_by_topic(memories),

            # 决策统计
            decisions=self._aggregate_decisions(decisions),

            # 实体统计
            entities=self._aggregate_entities(memories)
        )

    def _aggregate_by_scope(self, memories: list[Memory]) -> dict:
        """按项目/模块聚合"""
        scope_stats = defaultdict(lambda: {
            "count": 0,
            "importance_sum": 0.0,
            "topics": set(),
            "first_activity": None,
            "last_activity": None
        })

        for mem in memories:
            scope_key = mem.scope.path_string()
            stats = scope_stats[scope_key]
            stats["count"] += 1
            stats["importance_sum"] += mem.importance
            stats["topics"].update(mem.metadata.get("topics", []))
            # 更新时间范围...

        return dict(scope_stats)
```

### 2. 统计指标

```python
@dataclass
class YearlyMetrics:
    """年度统计指标"""

    # 基础指标
    total_memories: int
    total_sessions: int
    total_decisions: int
    active_days: int

    # 分布指标
    memories_by_type: dict[MemoryType, int]
    memories_by_domain: dict[MemoryDomain, int]
    memories_by_month: dict[int, int]

    # 成长指标
    new_knowledge_count: int      # 新学知识数
    skills_developed: list[str]   # 发展的技能
    projects_involved: list[str]  # 参与的项目

    # 决策指标
    decisions_made: int
    decisions_implemented: int
    decision_success_rate: float

    # 趋势指标
    most_active_month: int
    knowledge_growth_rate: float  # 知识增长率
    focus_shift: list[tuple[str, str]]  # 关注点变化
```

---

## 洞察提取

### 1. LLM 分析 Prompt

```python
YEARLY_INSIGHT_PROMPT = """
基于以下年度记忆数据，生成深度洞察分析：

## 输入数据

### 统计摘要
{metrics_summary}

### 按项目分布
{project_distribution}

### 关键决策
{key_decisions}

### 知识主题
{knowledge_topics}

### 月度活跃度
{monthly_activity}

## 分析要求

请从以下维度分析：

1. **年度成就** (3-5项)
   - 完成的重要项目
   - 掌握的新技能
   - 关键决策的影响

2. **成长轨迹**
   - 知识领域的变化
   - 关注点的演变
   - 能力提升的证据

3. **工作模式**
   - 高效时段识别
   - 项目投入分布
   - 协作模式

4. **待改进领域**
   - 被忽视的领域
   - 未完成的目标
   - 效率瓶颈

5. **来年建议** (3-5条)
   - 基于趋势的建议
   - 技能发展方向
   - 时间分配优化

## 输出格式

返回结构化 JSON：
{
  "achievements": [...],
  "growth_trajectory": {...},
  "work_patterns": {...},
  "improvement_areas": [...],
  "recommendations": [...]
}
"""
```

### 2. 成就识别

```python
class AchievementRecognizer:
    """成就识别器"""

    async def recognize(
        self,
        aggregation: YearlyAggregation,
        decisions: list[Decision]
    ) -> list[Achievement]:
        achievements = []

        # 1. 项目里程碑
        for project, stats in aggregation.by_scope.items():
            if self._is_significant_project(stats):
                achievements.append(Achievement(
                    type="PROJECT_MILESTONE",
                    title=f"完成 {project} 项目",
                    description=self._summarize_project(project, stats),
                    importance=stats["importance_sum"] / stats["count"],
                    evidence=self._collect_evidence(project)
                ))

        # 2. 技能突破
        skill_progress = self._analyze_skill_progress(aggregation)
        for skill, progress in skill_progress.items():
            if progress["growth_rate"] > 0.5:  # 增长超过50%
                achievements.append(Achievement(
                    type="SKILL_BREAKTHROUGH",
                    title=f"掌握 {skill}",
                    description=f"从入门到熟练",
                    evidence=progress["milestones"]
                ))

        # 3. 关键决策
        impactful_decisions = [
            d for d in decisions
            if d.status == "IMPLEMENTED" and d.impact_score > 0.7
        ]
        for decision in impactful_decisions:
            achievements.append(Achievement(
                type="KEY_DECISION",
                title=decision.title,
                description=decision.rationale,
                evidence=decision.evidence
            ))

        return sorted(achievements, key=lambda a: a.importance, reverse=True)
```

---

## 报告生成

### 1. 报告结构

```python
@dataclass
class YearlySummaryReport:
    """年终总结报告"""

    # 元信息
    user_id: str
    year: int
    generated_at: datetime
    scope: Optional[MemoryScope]  # 可选：限定范围的总结

    # 概览
    overview: ReportOverview

    # 详细内容
    sections: list[ReportSection]

    # 可视化数据
    visualizations: list[Visualization]

    # 附录
    appendix: ReportAppendix


@dataclass
class ReportOverview:
    """报告概览"""
    headline: str                    # 一句话总结
    year_theme: str                  # 年度主题词
    key_numbers: dict[str, Any]      # 关键数字
    top_achievements: list[str]      # 前3项成就
    word_cloud_data: dict[str, int]  # 词云数据


@dataclass
class ReportSection:
    """报告章节"""
    title: str
    content_type: str  # "narrative" | "list" | "timeline" | "chart"
    content: Any
    insights: list[str]
```

### 2. 报告模板

```markdown
# {year}年度总结

> {headline}

## 概览

### 年度关键数字

| 指标 | 数值 |
|------|------|
| 活跃天数 | {active_days} |
| 记忆总数 | {total_memories} |
| 参与项目 | {projects_count} |
| 关键决策 | {decisions_count} |
| 新增知识 | {new_knowledge} |

### 年度主题词

{word_cloud}

---

## 成就回顾

### {achievement_1_title}
{achievement_1_description}

**证据**:
{achievement_1_evidence}

### {achievement_2_title}
...

---

## 项目参与

### {project_1_name}

**投入时间**: {time_spent}
**关键里程碑**:
- {milestone_1}
- {milestone_2}

**学到的知识**:
{knowledge_gained}

---

## 知识成长

### 技能发展

{skill_radar_chart}

### 知识领域分布

{domain_pie_chart}

### 月度活跃热力图

{monthly_heatmap}

---

## 决策回顾

### 关键决策

| 决策 | 时间 | 状态 | 影响 |
|------|------|------|------|
| {decision_1} | {date} | {status} | {impact} |
| ... | ... | ... | ... |

### 决策模式分析

{decision_pattern_analysis}

---

## 成长轨迹

### Q1: {q1_theme}
{q1_summary}

### Q2: {q2_theme}
{q2_summary}

### Q3: {q3_theme}
{q3_summary}

### Q4: {q4_theme}
{q4_summary}

---

## 来年展望

### 建议关注领域

1. **{recommendation_1_area}**
   {recommendation_1_reason}

2. **{recommendation_2_area}**
   {recommendation_2_reason}

### 目标建议

- [ ] {goal_1}
- [ ] {goal_2}
- [ ] {goal_3}

---

*生成时间: {generated_at}*
*数据范围: {data_scope}*
```

---

## 可视化支持

### 1. 支持的图表类型

```python
class VisualizationType(Enum):
    """可视化类型"""

    # 时间维度
    MONTHLY_HEATMAP = "monthly_heatmap"      # 月度活跃热力图
    QUARTERLY_TREND = "quarterly_trend"       # 季度趋势线
    TIMELINE = "timeline"                     # 时间线

    # 分布维度
    DOMAIN_PIE = "domain_pie"                 # 领域饼图
    PROJECT_BAR = "project_bar"               # 项目柱状图
    SKILL_RADAR = "skill_radar"               # 技能雷达图

    # 关系维度
    KNOWLEDGE_GRAPH = "knowledge_graph"       # 知识图谱
    WORD_CLOUD = "word_cloud"                 # 词云
    SANKEY_FLOW = "sankey_flow"               # 桑基图(领域流向)
```

### 2. 图表数据生成

```python
class VisualizationGenerator:
    """可视化数据生成器"""

    def generate_monthly_heatmap(
        self,
        by_month: dict[int, int]
    ) -> dict:
        """生成月度热力图数据"""
        return {
            "type": "heatmap",
            "data": [
                {"month": month, "value": count, "intensity": count / max_count}
                for month, count in by_month.items()
            ],
            "config": {
                "color_scale": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]
            }
        }

    def generate_skill_radar(
        self,
        skills: dict[str, float]
    ) -> dict:
        """生成技能雷达图数据"""
        return {
            "type": "radar",
            "data": {
                "labels": list(skills.keys()),
                "datasets": [{
                    "label": "技能水平",
                    "data": list(skills.values()),
                    "fill": True
                }]
            }
        }

    def generate_knowledge_graph_mini(
        self,
        entities: list[Entity],
        relations: list[Relation]
    ) -> dict:
        """生成迷你知识图谱"""
        # 只取 Top 50 实体
        top_entities = sorted(entities, key=lambda e: e.mention_count, reverse=True)[:50]
        entity_ids = {e.id for e in top_entities}

        # 过滤相关关系
        relevant_relations = [
            r for r in relations
            if r.source_id in entity_ids and r.target_id in entity_ids
        ]

        return {
            "type": "force_graph",
            "nodes": [{"id": e.id, "label": e.name, "size": e.mention_count} for e in top_entities],
            "edges": [{"source": r.source_id, "target": r.target_id, "label": r.type} for r in relevant_relations]
        }
```

---

## API 设计

### 1. 生成年终总结

```python
@router.post("/summary/yearly")
async def generate_yearly_summary(
    request: YearlySummaryRequest,
    user: User = Depends(get_current_user)
) -> YearlySummaryResponse:
    """
    生成年终总结

    请求参数:
    - year: 年份
    - scope: 可选，限定范围 (如只总结某个项目)
    - format: 输出格式 (markdown | json | pdf)
    - sections: 可选，指定生成的章节

    响应:
    - report: 总结报告
    - visualizations: 可视化数据
    - metadata: 元信息
    """

    # 1. 检索年度记忆
    query = YearlySummaryQuery(
        user_id=user.id,
        year=request.year,
        scope=request.scope
    )

    retriever = YearlyRetriever(memory_manager)
    memories = await retriever.retrieve_by_quarters(query)
    decisions = await retriever.retrieve_decisions(query)

    # 2. 聚合分析
    aggregator = YearlyAggregator()
    aggregation = aggregator.aggregate(
        memories=flatten(memories.values()),
        decisions=decisions
    )

    # 3. 计算指标
    metrics = MetricsCalculator().calculate(aggregation)

    # 4. 识别成就
    achievements = await AchievementRecognizer().recognize(aggregation, decisions)

    # 5. LLM 洞察
    insights = await InsightExtractor().extract(
        aggregation=aggregation,
        metrics=metrics,
        achievements=achievements
    )

    # 6. 生成报告
    report = ReportGenerator().generate(
        year=request.year,
        metrics=metrics,
        achievements=achievements,
        insights=insights,
        format=request.format
    )

    # 7. 生成可视化
    visualizations = VisualizationGenerator().generate_all(aggregation)

    return YearlySummaryResponse(
        report=report,
        visualizations=visualizations,
        metadata={
            "generated_at": datetime.now(),
            "data_range": f"{request.year}-01-01 to {request.year}-12-31",
            "memory_count": sum(len(m) for m in memories.values())
        }
    )
```

### 2. 请求/响应模型

```python
class YearlySummaryRequest(BaseModel):
    """年终总结请求"""
    year: int = Field(..., ge=2020, le=2030)
    scope: Optional[str] = None  # 范围路径，如 "work/project-x"
    format: Literal["markdown", "json", "pdf"] = "markdown"
    sections: Optional[list[str]] = None  # 指定章节
    include_visualizations: bool = True
    language: str = "zh-CN"


class YearlySummaryResponse(BaseModel):
    """年终总结响应"""
    report: str  # Markdown 或 JSON 字符串
    visualizations: list[dict]
    metadata: dict

    # 辅助信息
    generation_time_ms: int
    memory_count: int
    decision_count: int
```

---

## 范围限定总结

除了全年总结，还支持：

### 1. 项目年终总结

```python
# 只总结某个项目
request = YearlySummaryRequest(
    year=2025,
    scope="work/llm-platform",  # 限定到 llm-platform 项目
    sections=["achievements", "decisions", "knowledge"]
)
```

### 2. 领域年终总结

```python
# 只总结某个领域
request = YearlySummaryRequest(
    year=2025,
    domain_filter="WORK",  # 只看工作领域
)
```

### 3. 季度/月度总结

```python
# 复用相同逻辑，调整时间范围
request = QuarterlySummaryRequest(
    year=2025,
    quarter=4  # Q4 总结
)
```

---

## 故事追加

| ID | 优先级 | 标题 | Sprint |
|----|--------|------|--------|
| STORY-031 | P2 | 实现 YearlyRetriever | 6 |
| STORY-032 | P2 | 实现 YearlyAggregator | 6 |
| STORY-033 | P2 | 实现成就识别器 | 6 |
| STORY-034 | P2 | 实现 LLM 洞察提取 | 6 |
| STORY-035 | P2 | 实现报告生成器 | 6 |
| STORY-036 | P3 | 实现可视化数据生成 | 7 |
| STORY-037 | P3 | 实现 PDF 导出 | 7 |

---

## 总结

年终总结生成的关键流程：

```
1. 时间范围检索 (按季度分片，避免大查询)
         ↓
2. 多维度聚合 (范围/领域/月份/主题)
         ↓
3. 指标计算 (基础/分布/成长/趋势)
         ↓
4. 成就识别 (项目/技能/决策)
         ↓
5. LLM 洞察 (趋势/模式/建议)
         ↓
6. 报告生成 (Markdown/JSON/PDF)
         ↓
7. 可视化 (热力图/雷达图/知识图谱)
```

**核心依赖**:
- Episodic Memory → 时间线事件
- Semantic Memory → 知识主题
- Decision Memory → 关键决策
- Knowledge Graph → 实体关系
