# 记忆模式提炼与 Skill 生成

**版本**: v1.0
**更新日期**: 2025-02-24

---

## 概述

从用户记忆中识别高价值通用模式，自动转化为可复用的 Agent Skill：

```
记忆积累 → 模式识别 → 价值评估 → 模式提炼 → Skill 生成 → 验证发布
```

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Pattern-to-Skill 流水线                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │  记忆池     │    │  模式挖掘   │    │  价值评估   │    │ Skill 生成  │  │
│  │ Memory Pool │───▶│  Pattern    │───▶│  Value      │───▶│  Skill     │  │
│  │             │    │  Mining     │    │  Scoring    │    │  Generator │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│        │                  │                  │                  │          │
│        ▼                  ▼                  ▼                  ▼          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │ • Episodic  │    │ • 序列模式  │    │ • 复用次数  │    │ • Prompt   │  │
│  │ • Semantic  │    │ • 工作流模式│    │ • 成功率    │    │ • 参数定义 │  │
│  │ • Decision  │    │ • 决策模式  │    │ • 通用性    │    │ • 示例    │  │
│  │ • QA Memory │    │ • 问答模式  │    │ • 时效性    │    │ • 触发条件 │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│                                                                             │
│                              ▼                                              │
│                    ┌───────────────────┐                                    │
│                    │   Skill Registry  │                                    │
│                    │   技能注册中心     │                                    │
│                    └───────────────────┘                                    │
│                              │                                              │
│              ┌───────────────┼───────────────┐                              │
│              ▼               ▼               ▼                              │
│        ┌──────────┐    ┌──────────┐    ┌──────────┐                        │
│        │ 个人技能  │    │ 团队技能  │    │ 公共技能  │                        │
│        │ Personal │    │  Team    │    │  Public  │                        │
│        └──────────┘    └──────────┘    └──────────┘                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 模式类型

### 1. 可识别的模式类型

```python
class PatternType(Enum):
    """模式类型"""

    # 操作序列模式
    WORKFLOW = "workflow"           # 工作流程：A → B → C → D
    TROUBLESHOOT = "troubleshoot"   # 故障排查：症状 → 诊断 → 修复
    REVIEW = "review"               # 审查流程：检查点列表

    # 决策模式
    DECISION_TREE = "decision_tree"     # 决策树：条件 → 选择
    TRADEOFF = "tradeoff"               # 权衡模式：因素 → 平衡
    EVALUATION = "evaluation"           # 评估模式：标准 → 打分

    # 知识模式
    EXPLANATION = "explanation"     # 解释模式：概念 → 原理 → 示例
    COMPARISON = "comparison"       # 比较模式：A vs B
    BEST_PRACTICE = "best_practice" # 最佳实践：场景 → 方法

    # 交互模式
    QA_PAIR = "qa_pair"             # 问答对：问题类型 → 答案模板
    CLARIFICATION = "clarification" # 澄清模式：模糊 → 明确
    GUIDANCE = "guidance"           # 引导模式：目标 → 步骤
```

### 2. 模式数据结构

```python
@dataclass
class Pattern:
    """识别出的模式"""

    id: str
    type: PatternType
    name: str
    description: str

    # 模式内容
    structure: PatternStructure      # 模式结构
    examples: list[PatternExample]   # 实例列表
    parameters: list[PatternParam]   # 可变参数

    # 来源追溯
    source_memories: list[str]       # 来源记忆ID
    source_count: int                # 出现次数
    first_seen: datetime
    last_seen: datetime

    # 评估指标
    metrics: PatternMetrics


@dataclass
class PatternStructure:
    """模式结构"""

    # 工作流类型
    steps: Optional[list[Step]] = None

    # 决策树类型
    conditions: Optional[list[Condition]] = None
    branches: Optional[list[Branch]] = None

    # 模板类型
    template: Optional[str] = None
    slots: Optional[list[Slot]] = None


@dataclass
class PatternExample:
    """模式实例"""
    memory_id: str
    context: str           # 使用场景
    input: dict            # 输入参数
    output: str            # 输出结果
    success: bool          # 是否成功
    feedback: Optional[str] # 用户反馈
```

---

## 模式挖掘

### 1. 挖掘流程

```python
class PatternMiner:
    """模式挖掘器"""

    async def mine_patterns(
        self,
        user_id: str,
        time_range: tuple[datetime, datetime],
        min_occurrences: int = 3
    ) -> list[Pattern]:
        """挖掘用户记忆中的模式"""

        patterns = []

        # 1. 挖掘工作流模式
        workflow_patterns = await self._mine_workflow_patterns(
            user_id, time_range, min_occurrences
        )
        patterns.extend(workflow_patterns)

        # 2. 挖掘决策模式
        decision_patterns = await self._mine_decision_patterns(
            user_id, time_range, min_occurrences
        )
        patterns.extend(decision_patterns)

        # 3. 挖掘问答模式
        qa_patterns = await self._mine_qa_patterns(
            user_id, time_range, min_occurrences
        )
        patterns.extend(qa_patterns)

        # 4. 挖掘知识模式
        knowledge_patterns = await self._mine_knowledge_patterns(
            user_id, time_range, min_occurrences
        )
        patterns.extend(knowledge_patterns)

        return patterns

    async def _mine_workflow_patterns(
        self,
        user_id: str,
        time_range: tuple,
        min_occurrences: int
    ) -> list[Pattern]:
        """挖掘工作流模式 - 识别重复的操作序列"""

        # 1. 获取会话记忆
        sessions = await self.memory_manager.retrieve(
            user_id=user_id,
            time_range=time_range,
            types=[MemoryType.EPISODIC],
            include_actions=True
        )

        # 2. 提取操作序列
        action_sequences = []
        for session in sessions:
            actions = self._extract_actions(session)
            if len(actions) >= 3:
                action_sequences.append(actions)

        # 3. 序列模式挖掘 (使用 PrefixSpan 算法)
        frequent_sequences = self._prefixspan_mining(
            action_sequences,
            min_support=min_occurrences
        )

        # 4. 构建模式
        patterns = []
        for seq, support, instances in frequent_sequences:
            pattern = Pattern(
                id=generate_pattern_id(),
                type=PatternType.WORKFLOW,
                name=self._generate_workflow_name(seq),
                description=self._describe_workflow(seq),
                structure=PatternStructure(
                    steps=[Step(action=a, order=i) for i, a in enumerate(seq)]
                ),
                examples=[
                    self._create_example(inst) for inst in instances[:5]
                ],
                source_count=support,
                metrics=PatternMetrics(frequency=support)
            )
            patterns.append(pattern)

        return patterns
```

### 2. 序列模式挖掘算法

```python
class SequencePatternMiner:
    """序列模式挖掘"""

    def prefixspan_mining(
        self,
        sequences: list[list[str]],
        min_support: int
    ) -> list[tuple[list[str], int, list]]:
        """PrefixSpan 频繁序列挖掘"""

        # 初始化
        frequent_patterns = []

        # 1. 找单项频繁项
        item_counts = Counter()
        for seq in sequences:
            for item in set(seq):
                item_counts[item] += 1

        frequent_items = [
            item for item, count in item_counts.items()
            if count >= min_support
        ]

        # 2. 递归挖掘
        for item in frequent_items:
            # 投影数据库
            projected_db = self._project_database(sequences, [item])

            # 递归挖掘更长模式
            self._recursive_mining(
                [item],
                projected_db,
                min_support,
                frequent_patterns
            )

        return frequent_patterns

    def _find_workflow_boundaries(
        self,
        actions: list[str]
    ) -> list[tuple[int, int]]:
        """识别工作流边界"""

        boundaries = []
        start = 0

        for i, action in enumerate(actions):
            # 识别工作流结束信号
            if self._is_workflow_end(action):
                if i > start:
                    boundaries.append((start, i + 1))
                start = i + 1

        return boundaries
```

### 3. 决策模式挖掘

```python
class DecisionPatternMiner:
    """决策模式挖掘"""

    async def mine_decision_patterns(
        self,
        user_id: str,
        time_range: tuple,
        min_occurrences: int
    ) -> list[Pattern]:
        """从决策记忆中挖掘模式"""

        # 1. 获取决策记忆
        decisions = await self.decision_store.query(
            user_id=user_id,
            time_range=time_range,
            status=["DECIDED", "IMPLEMENTED"]
        )

        # 2. 按类别分组
        by_category = defaultdict(list)
        for d in decisions:
            by_category[d.category].append(d)

        # 3. 在每个类别内找模式
        patterns = []
        for category, category_decisions in by_category.items():
            if len(category_decisions) < min_occurrences:
                continue

            # 提取决策因素
            factors = self._extract_common_factors(category_decisions)

            # 构建决策树
            decision_tree = self._build_decision_tree(
                category_decisions,
                factors
            )

            if decision_tree:
                patterns.append(Pattern(
                    id=generate_pattern_id(),
                    type=PatternType.DECISION_TREE,
                    name=f"{category.value} 决策模式",
                    structure=PatternStructure(
                        conditions=decision_tree.conditions,
                        branches=decision_tree.branches
                    ),
                    examples=[
                        self._decision_to_example(d)
                        for d in category_decisions[:5]
                    ],
                    source_count=len(category_decisions)
                ))

        return patterns
```

### 4. QA 模式挖掘

```python
class QAPatternMiner:
    """问答模式挖掘"""

    async def mine_qa_patterns(
        self,
        user_id: str,
        time_range: tuple,
        min_occurrences: int
    ) -> list[Pattern]:
        """从 QA 记忆中挖掘模式"""

        # 1. 获取高信任度 QA
        qa_memories = await self.qa_memory_service.search(
            user_id=user_id,
            min_trust_score=0.7,
            min_level=QAMemoryLevel.L2_STRONG
        )

        # 2. 问题聚类
        question_embeddings = await self._embed_questions(
            [qa.question for qa in qa_memories]
        )
        clusters = self._cluster_questions(question_embeddings, qa_memories)

        # 3. 每个聚类生成模式
        patterns = []
        for cluster_id, cluster_qas in clusters.items():
            if len(cluster_qas) < min_occurrences:
                continue

            # 提取问题模板
            question_template = self._extract_question_template(cluster_qas)

            # 提取答案模板
            answer_template = self._extract_answer_template(cluster_qas)

            # 识别参数槽位
            slots = self._identify_slots(cluster_qas)

            patterns.append(Pattern(
                id=generate_pattern_id(),
                type=PatternType.QA_PAIR,
                name=self._generate_qa_pattern_name(question_template),
                structure=PatternStructure(
                    template=answer_template,
                    slots=slots
                ),
                parameters=[
                    PatternParam(name=s.name, type=s.type, description=s.desc)
                    for s in slots
                ],
                examples=[
                    PatternExample(
                        memory_id=qa.id,
                        context=qa.context,
                        input={"question": qa.question},
                        output=qa.answer,
                        success=qa.trust_score > 0.8
                    )
                    for qa in cluster_qas[:5]
                ],
                source_count=len(cluster_qas)
            ))

        return patterns
```

---

## 价值评估

### 1. 评估维度

```python
@dataclass
class PatternMetrics:
    """模式评估指标"""

    # 使用频率
    frequency: int              # 出现次数
    recent_usage: int           # 近30天使用次数
    usage_trend: float          # 使用趋势 (-1 下降, +1 上升)

    # 成功率
    success_rate: float         # 成功率 (0-1)
    positive_feedback: int      # 正面反馈数
    negative_feedback: int      # 负面反馈数

    # 通用性
    context_diversity: float    # 场景多样性 (0-1)
    parameter_stability: float  # 参数稳定性 (0-1)
    cross_project: bool         # 是否跨项目使用

    # 复杂度
    step_count: int             # 步骤数
    decision_points: int        # 决策点数
    estimated_time_saved: float # 预估节省时间(分钟)

    # 综合得分
    @property
    def value_score(self) -> float:
        """计算综合价值得分"""
        return (
            0.25 * min(self.frequency / 10, 1.0) +          # 频率权重
            0.25 * self.success_rate +                       # 成功率权重
            0.20 * self.context_diversity +                  # 通用性权重
            0.15 * (1 - min(self.step_count / 20, 1.0)) +   # 简洁性权重
            0.15 * min(self.estimated_time_saved / 30, 1.0) # 效率权重
        )
```

### 2. 评估器实现

```python
class PatternEvaluator:
    """模式价值评估器"""

    def evaluate(self, pattern: Pattern) -> PatternMetrics:
        """评估模式价值"""

        # 1. 计算使用频率
        frequency_metrics = self._evaluate_frequency(pattern)

        # 2. 计算成功率
        success_metrics = self._evaluate_success(pattern)

        # 3. 计算通用性
        generality_metrics = self._evaluate_generality(pattern)

        # 4. 计算复杂度
        complexity_metrics = self._evaluate_complexity(pattern)

        return PatternMetrics(
            **frequency_metrics,
            **success_metrics,
            **generality_metrics,
            **complexity_metrics
        )

    def _evaluate_generality(self, pattern: Pattern) -> dict:
        """评估通用性"""

        # 场景多样性：实例来自多少不同场景
        contexts = [ex.context for ex in pattern.examples]
        unique_contexts = len(set(contexts))
        context_diversity = min(unique_contexts / 5, 1.0)

        # 参数稳定性：参数值的变化程度
        param_values = defaultdict(list)
        for ex in pattern.examples:
            for key, value in ex.input.items():
                param_values[key].append(value)

        # 如果参数值变化大但结构稳定，说明模式有好的抽象
        parameter_stability = self._calculate_param_stability(param_values)

        # 跨项目使用
        projects = set()
        for mem_id in pattern.source_memories:
            memory = self.memory_manager.get(mem_id)
            if memory and memory.scope:
                projects.add(memory.scope.project)
        cross_project = len(projects) > 1

        return {
            "context_diversity": context_diversity,
            "parameter_stability": parameter_stability,
            "cross_project": cross_project
        }

    def filter_high_value_patterns(
        self,
        patterns: list[Pattern],
        min_score: float = 0.6
    ) -> list[Pattern]:
        """过滤高价值模式"""

        evaluated = []
        for pattern in patterns:
            metrics = self.evaluate(pattern)
            pattern.metrics = metrics

            if metrics.value_score >= min_score:
                evaluated.append(pattern)

        # 按价值得分排序
        return sorted(evaluated, key=lambda p: p.metrics.value_score, reverse=True)
```

---

## Skill 生成

### 1. Skill 结构

```python
@dataclass
class GeneratedSkill:
    """生成的技能"""

    # 基本信息
    name: str
    description: str
    version: str = "1.0.0"

    # 触发条件
    triggers: list[SkillTrigger]

    # 技能内容
    system_prompt: str
    user_prompt_template: str
    parameters: list[SkillParameter]

    # 执行配置
    execution: SkillExecution

    # 来源追溯
    source_pattern: str          # 来源模式ID
    source_examples: list[str]   # 来源实例ID

    # 元数据
    scope: SkillScope            # 个人/团队/公共
    tags: list[str]
    created_at: datetime
    created_by: str


@dataclass
class SkillTrigger:
    """技能触发条件"""
    type: str                    # "keyword" | "intent" | "context"
    pattern: str                 # 匹配模式
    confidence_threshold: float  # 置信度阈值


@dataclass
class SkillParameter:
    """技能参数"""
    name: str
    type: str                    # "string" | "number" | "enum" | "list"
    description: str
    required: bool = True
    default: Optional[Any] = None
    enum_values: Optional[list] = None
    extraction_hint: str = ""    # 如何从用户输入提取
```

### 2. Skill 生成器

```python
class SkillGenerator:
    """技能生成器"""

    SKILL_GENERATION_PROMPT = """
基于以下模式信息，生成一个可复用的 Agent Skill。

## 模式信息

**名称**: {pattern_name}
**类型**: {pattern_type}
**描述**: {pattern_description}

### 模式结构
{pattern_structure}

### 典型实例
{examples}

### 可变参数
{parameters}

## 生成要求

请生成以下内容：

1. **技能名称**: 简洁的动词短语
2. **触发条件**: 用户说什么时触发此技能
3. **System Prompt**: 给 Agent 的指令
4. **User Prompt Template**: 用户输入模板
5. **参数定义**: 需要提取的参数
6. **执行步骤**: Agent 应该执行的步骤

## 输出格式

返回 YAML 格式的技能定义。
"""

    async def generate_skill(
        self,
        pattern: Pattern
    ) -> GeneratedSkill:
        """从模式生成技能"""

        # 1. 准备提示词
        prompt = self.SKILL_GENERATION_PROMPT.format(
            pattern_name=pattern.name,
            pattern_type=pattern.type.value,
            pattern_description=pattern.description,
            pattern_structure=self._format_structure(pattern.structure),
            examples=self._format_examples(pattern.examples),
            parameters=self._format_parameters(pattern.parameters)
        )

        # 2. 调用 LLM 生成
        response = await self.llm.generate(
            system="你是一个专业的 Agent Skill 设计专家。",
            user=prompt,
            response_format="yaml"
        )

        # 3. 解析响应
        skill_def = yaml.safe_load(response)

        # 4. 构建技能对象
        skill = self._build_skill(skill_def, pattern)

        # 5. 验证技能
        validation = await self._validate_skill(skill, pattern.examples)
        if not validation.passed:
            # 修复问题
            skill = await self._fix_skill(skill, validation.issues)

        return skill

    def _build_skill(
        self,
        skill_def: dict,
        pattern: Pattern
    ) -> GeneratedSkill:
        """构建技能对象"""

        return GeneratedSkill(
            name=skill_def["name"],
            description=skill_def["description"],
            triggers=[
                SkillTrigger(
                    type=t["type"],
                    pattern=t["pattern"],
                    confidence_threshold=t.get("confidence", 0.7)
                )
                for t in skill_def.get("triggers", [])
            ],
            system_prompt=skill_def["system_prompt"],
            user_prompt_template=skill_def["user_prompt_template"],
            parameters=[
                SkillParameter(
                    name=p["name"],
                    type=p["type"],
                    description=p["description"],
                    required=p.get("required", True),
                    extraction_hint=p.get("extraction_hint", "")
                )
                for p in skill_def.get("parameters", [])
            ],
            execution=SkillExecution(
                steps=skill_def.get("steps", []),
                max_iterations=skill_def.get("max_iterations", 5),
                timeout_seconds=skill_def.get("timeout", 300)
            ),
            source_pattern=pattern.id,
            source_examples=[ex.memory_id for ex in pattern.examples],
            scope=SkillScope.PERSONAL,
            tags=skill_def.get("tags", []),
            created_at=datetime.now(),
            created_by="pattern_mining"
        )
```

### 3. 不同模式类型的 Skill 模板

```python
SKILL_TEMPLATES = {
    PatternType.WORKFLOW: """
name: "{name}"
description: "{description}"

triggers:
  - type: intent
    pattern: "{trigger_intent}"
    confidence: 0.7
  - type: keyword
    pattern: "{trigger_keywords}"

system_prompt: |
  你是一个专业助手，帮助用户完成 {workflow_name}。

  ## 工作流程

  {steps_formatted}

  ## 执行规则

  1. 按顺序执行每个步骤
  2. 每个步骤完成后确认结果
  3. 遇到问题时提供替代方案
  4. 完成后总结执行结果

user_prompt_template: |
  请帮我执行 {workflow_name}。

  **上下文**: {{context}}
  **参数**:
  {param_slots}

parameters:
  {parameters_def}

steps:
  {steps_def}
""",

    PatternType.DECISION_TREE: """
name: "{name}"
description: "{description}"

triggers:
  - type: intent
    pattern: "帮我决定|如何选择|应该选哪个"
  - type: keyword
    pattern: "{decision_keywords}"

system_prompt: |
  你是一个决策顾问，帮助用户做出 {decision_type} 决策。

  ## 决策框架

  ### 考虑因素
  {factors}

  ### 决策树
  {decision_tree}

  ## 执行规则

  1. 首先了解用户的具体情况
  2. 逐一评估每个因素
  3. 根据决策树给出建议
  4. 说明选择理由和潜在风险

user_prompt_template: |
  请帮我决定 {decision_topic}。

  **情况**: {{situation}}
  **偏好**: {{preferences}}

parameters:
  - name: situation
    type: string
    description: 当前情况描述
  - name: preferences
    type: list
    description: 用户偏好
""",

    PatternType.QA_PAIR: """
name: "{name}"
description: "{description}"

triggers:
  - type: intent
    pattern: "{question_intent}"
  - type: keyword
    pattern: "{question_keywords}"

system_prompt: |
  你是一个专业顾问，擅长回答 {qa_domain} 相关问题。

  ## 回答模板

  {answer_template}

  ## 回答规则

  1. 使用清晰的结构化格式
  2. 提供具体的示例
  3. 注明适用条件和限制
  4. 如有必要，提供进一步学习资源

user_prompt_template: |
  {{question}}

parameters:
  - name: question
    type: string
    description: 用户问题
  {additional_params}
"""
}
```

---

## 技能验证

### 1. 验证流程

```python
class SkillValidator:
    """技能验证器"""

    async def validate_skill(
        self,
        skill: GeneratedSkill,
        test_examples: list[PatternExample]
    ) -> ValidationResult:
        """验证生成的技能"""

        results = []

        for example in test_examples:
            # 1. 模拟执行
            execution_result = await self._simulate_execution(
                skill=skill,
                input=example.input,
                expected_output=example.output
            )

            # 2. 评估结果
            evaluation = await self._evaluate_result(
                actual=execution_result.output,
                expected=example.output,
                context=example.context
            )

            results.append(TestResult(
                example_id=example.memory_id,
                passed=evaluation.similarity > 0.8,
                similarity=evaluation.similarity,
                issues=evaluation.issues
            ))

        # 3. 汇总结果
        pass_rate = sum(1 for r in results if r.passed) / len(results)

        return ValidationResult(
            passed=pass_rate >= 0.8,
            pass_rate=pass_rate,
            test_results=results,
            issues=self._aggregate_issues(results)
        )

    async def _simulate_execution(
        self,
        skill: GeneratedSkill,
        input: dict,
        expected_output: str
    ) -> ExecutionResult:
        """模拟技能执行"""

        # 填充模板
        user_prompt = skill.user_prompt_template.format(**input)

        # 执行
        response = await self.llm.generate(
            system=skill.system_prompt,
            user=user_prompt
        )

        return ExecutionResult(
            output=response,
            tokens_used=len(response.split()),
            execution_time=0.0
        )
```

### 2. 迭代优化

```python
class SkillOptimizer:
    """技能优化器"""

    async def optimize_skill(
        self,
        skill: GeneratedSkill,
        validation: ValidationResult
    ) -> GeneratedSkill:
        """基于验证结果优化技能"""

        if validation.passed:
            return skill

        # 分析失败原因
        failure_analysis = self._analyze_failures(validation.test_results)

        # 生成优化建议
        optimization_prompt = f"""
技能 "{skill.name}" 的验证通过率为 {validation.pass_rate:.0%}。

## 失败分析

{failure_analysis}

## 当前 System Prompt

{skill.system_prompt}

## 优化要求

请优化 System Prompt 以解决上述问题，同时保持技能的核心功能。
"""

        # 获取优化后的 prompt
        optimized_prompt = await self.llm.generate(
            system="你是一个 Prompt 优化专家。",
            user=optimization_prompt
        )

        # 更新技能
        skill.system_prompt = optimized_prompt
        skill.version = self._increment_version(skill.version)

        return skill
```

---

## 技能注册与管理

### 1. 技能注册中心

```python
class SkillRegistry:
    """技能注册中心"""

    async def register_skill(
        self,
        skill: GeneratedSkill,
        user_id: str
    ) -> RegisteredSkill:
        """注册技能"""

        # 1. 检查重复
        existing = await self._find_similar_skill(skill)
        if existing and existing.similarity > 0.9:
            raise SkillDuplicateError(f"与现有技能 {existing.name} 高度相似")

        # 2. 生成技能文件
        skill_file = self._generate_skill_file(skill)

        # 3. 保存到技能库
        skill_path = self._get_skill_path(skill, user_id)
        await self.storage.write(skill_path, skill_file)

        # 4. 更新索引
        await self._update_skill_index(skill, user_id)

        # 5. 记录到数据库
        registered = await self.skill_store.create(
            skill_id=skill.id,
            user_id=user_id,
            skill_data=skill.dict(),
            file_path=skill_path
        )

        return registered

    def _generate_skill_file(self, skill: GeneratedSkill) -> str:
        """生成技能文件内容"""

        return f"""---
name: {skill.name}
description: {skill.description}
version: {skill.version}
scope: {skill.scope.value}
tags: {skill.tags}

triggers:
{yaml.dump(skill.triggers, allow_unicode=True)}

parameters:
{yaml.dump(skill.parameters, allow_unicode=True)}

source:
  pattern_id: {skill.source_pattern}
  created_at: {skill.created_at.isoformat()}
  created_by: {skill.created_by}
---

{skill.system_prompt}

---

## User Prompt Template

{skill.user_prompt_template}

---

## Execution Steps

{yaml.dump(skill.execution.steps, allow_unicode=True)}
"""
```

### 2. 技能共享

```python
class SkillScope(Enum):
    """技能范围"""
    PERSONAL = "personal"     # 个人私有
    TEAM = "team"             # 团队共享
    PUBLIC = "public"         # 公开发布


class SkillSharingService:
    """技能共享服务"""

    async def promote_skill(
        self,
        skill_id: str,
        from_scope: SkillScope,
        to_scope: SkillScope,
        user_id: str
    ) -> bool:
        """提升技能范围"""

        skill = await self.skill_store.get(skill_id)

        # 权限检查
        if not self._can_promote(skill, user_id, to_scope):
            raise PermissionError("无权限提升技能范围")

        # 团队共享：需要团队管理员审核
        if to_scope == SkillScope.TEAM:
            await self._request_team_review(skill, user_id)
            return False  # 等待审核

        # 公开发布：需要质量检查
        if to_scope == SkillScope.PUBLIC:
            quality_check = await self._quality_check(skill)
            if not quality_check.passed:
                raise QualityCheckError(quality_check.issues)

            await self._publish_to_marketplace(skill)

        # 更新技能范围
        skill.scope = to_scope
        await self.skill_store.update(skill)

        return True
```

---

## 完整流程示例

### 场景：代码审查工作流

```python
# 1. 用户多次进行代码审查，系统识别出模式

pattern = Pattern(
    type=PatternType.WORKFLOW,
    name="Python 代码审查流程",
    structure=PatternStructure(
        steps=[
            Step(action="检查代码风格", tools=["ruff", "black"]),
            Step(action="运行类型检查", tools=["mypy"]),
            Step(action="运行单元测试", tools=["pytest"]),
            Step(action="检查安全漏洞", tools=["bandit"]),
            Step(action="生成审查报告", output="markdown")
        ]
    ),
    examples=[...],  # 5个实例
    metrics=PatternMetrics(
        frequency=15,
        success_rate=0.93,
        context_diversity=0.8,
        estimated_time_saved=20.0,
        value_score=0.85
    )
)

# 2. 系统生成 Skill

generated_skill = GeneratedSkill(
    name="python-code-review",
    description="执行完整的 Python 代码审查流程",
    triggers=[
        SkillTrigger(type="keyword", pattern="审查代码|code review|检查代码"),
        SkillTrigger(type="intent", pattern="帮我审查这段Python代码")
    ],
    system_prompt="""
你是一个专业的 Python 代码审查助手。

## 审查流程

1. **代码风格检查**
   - 运行 ruff 检查代码风格
   - 运行 black --check 检查格式

2. **类型检查**
   - 运行 mypy 进行静态类型检查

3. **单元测试**
   - 运行 pytest 执行测试
   - 检查覆盖率

4. **安全检查**
   - 运行 bandit 检查安全漏洞

5. **生成报告**
   - 汇总所有检查结果
   - 提供改进建议

## 输出格式

使用 Markdown 格式，包含：
- 检查摘要
- 详细问题列表
- 改进建议
""",
    parameters=[
        SkillParameter(name="file_path", type="string", description="要审查的文件路径"),
        SkillParameter(name="focus_areas", type="list", description="重点关注领域", required=False)
    ]
)

# 3. 用户下次只需说

# "帮我审查 src/service/user.py"

# 系统自动触发 python-code-review 技能
```

---

## 新增故事

| ID | 优先级 | 标题 | Sprint |
|----|--------|------|--------|
| STORY-038 | P1 | 实现序列模式挖掘算法 | 7 |
| STORY-039 | P1 | 实现决策模式挖掘 | 7 |
| STORY-040 | P1 | 实现 QA 模式挖掘 | 7 |
| STORY-041 | P1 | 实现模式价值评估器 | 7 |
| STORY-042 | P0 | 实现 Skill 生成器 | 7 |
| STORY-043 | P1 | 实现 Skill 验证器 | 7 |
| STORY-044 | P1 | 实现 Skill 注册中心 | 7 |
| STORY-045 | P2 | 实现 Skill 共享服务 | 8 |
| STORY-046 | P2 | 实现模式挖掘定时任务 | 8 |

---

## 总结

模式到 Skill 的转化流程：

```
记忆积累 (3+ 次相似操作)
      ↓
模式挖掘 (序列/决策/QA/知识)
      ↓
价值评估 (频率×成功率×通用性)
      ↓
Skill 生成 (LLM + 模板)
      ↓
验证优化 (测试实例回放)
      ↓
注册发布 (个人→团队→公共)
```

**核心价值**：
- 用户的最佳实践自动沉淀为可复用技能
- 减少重复操作，提升效率
- 支持团队知识共享
- 持续学习和优化
