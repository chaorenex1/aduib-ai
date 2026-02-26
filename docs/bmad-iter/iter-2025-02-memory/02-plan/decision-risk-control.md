# 决策记忆风险控制

**版本**: v1.0
**更新日期**: 2025-02-24

---

## 1. 核心风险

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Decision Memory Risks                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  风险1: 误识别 (False Positive)                                         │
│  ─────────────────────────────────────────────────────────────────────  │
│  用户: "我们讨论了使用 Redis，但还没决定"                                │
│  错误: 系统识别为 "决定使用 Redis"  ← 危险！                            │
│                                                                         │
│  风险2: 上下文污染                                                      │
│  ─────────────────────────────────────────────────────────────────────  │
│  后续对话中，AI 引用了这个"虚假决策"                                    │
│  "根据之前的决策，我们使用 Redis..."  ← 误导用户                        │
│                                                                         │
│  风险3: 决策冲突                                                        │
│  ─────────────────────────────────────────────────────────────────────  │
│  同一问题存在多个矛盾的"决策"                                           │
│  决策A: "使用 Redis"  vs  决策B: "使用 Memcached"                       │
│                                                                         │
│  风险4: 过期决策                                                        │
│  ─────────────────────────────────────────────────────────────────────  │
│  已变更的决策仍被引用                                                   │
│  "使用 Python 2.7" (已过期) 仍在上下文中                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 风险控制框架

### 2.1 决策确定性等级

```python
class DecisionCertainty(Enum):
    """决策确定性等级"""

    # 高确定性 - 可以安全引用
    CONFIRMED = "confirmed"          # 用户明确确认
    EVIDENCED = "evidenced"          # 有执行证据
    EXPLICIT = "explicit"            # 明确的决策表述

    # 中确定性 - 需要谨慎引用
    INFERRED = "inferred"            # 推断的决策
    IMPLICIT = "implicit"            # 隐含的决策

    # 低确定性 - 不应直接引用
    TENTATIVE = "tentative"          # 试探性的
    DISCUSSING = "discussing"        # 讨论中
    UNCERTAIN = "uncertain"          # 不确定

    # 特殊状态
    DISPUTED = "disputed"            # 有争议
    RETRACTED = "retracted"          # 已撤回
```

### 2.2 确定性评估

```python
class CertaintyAssessor:
    """确定性评估器"""

    def assess(self, decision: Decision, context: DecisionContext) -> CertaintyResult:
        """评估决策的确定性"""

        score = 0.0
        factors = []

        # 因素1: 语言表达的确定性
        linguistic_certainty = self._assess_linguistic(decision.source_text)
        score += linguistic_certainty * 0.3
        factors.append(("linguistic", linguistic_certainty))

        # 因素2: 是否有执行证据
        if decision.evidence:
            verified_evidence = [e for e in decision.evidence if e.verified]
            evidence_score = min(1.0, len(verified_evidence) * 0.3)
            score += evidence_score * 0.3
            factors.append(("evidence", evidence_score))
        else:
            factors.append(("evidence", 0.0))

        # 因素3: 是否有用户确认
        if decision.user_confirmed:
            score += 0.25
            factors.append(("user_confirmed", 1.0))
        else:
            factors.append(("user_confirmed", 0.0))

        # 因素4: 是否有后续引用
        if context.subsequent_references > 0:
            ref_score = min(1.0, context.subsequent_references * 0.2)
            score += ref_score * 0.15
            factors.append(("references", ref_score))

        # 因素5: 是否有冲突决策
        if context.conflicting_decisions:
            score -= 0.3
            factors.append(("conflicts", -0.3))

        # 确定等级
        certainty = self._score_to_certainty(score)

        return CertaintyResult(
            certainty=certainty,
            score=score,
            factors=factors
        )

    def _assess_linguistic(self, text: str) -> float:
        """评估语言表达的确定性"""

        # 高确定性表达
        HIGH_CERTAINTY_PATTERNS = [
            r"(决定|确定|敲定|最终)(了|使用|采用)",
            r"(我们|团队)(已经|已)(决定|确认)",
            r"(approved|decided|confirmed|finalized)",
        ]

        # 低确定性表达
        LOW_CERTAINTY_PATTERNS = [
            r"(考虑|讨论|商量|研究)(一下|中|ing)",
            r"(可能|或许|也许|暂时)(会|要|用)",
            r"(如果|假设|万一)",
            r"(还没|尚未|待)(决定|确认)",
            r"(might|maybe|perhaps|considering|discussing)",
            r"(not yet|haven't decided|still thinking)",
        ]

        # 否定表达
        NEGATION_PATTERNS = [
            r"(没有|不|别|勿)(决定|使用|采用)",
            r"(取消|放弃|撤销)(了|这个)",
            r"(don't|won't|didn't|not going to)",
        ]

        text_lower = text.lower()

        # 检查否定
        for pattern in NEGATION_PATTERNS:
            if re.search(pattern, text_lower):
                return 0.1

        # 检查高确定性
        for pattern in HIGH_CERTAINTY_PATTERNS:
            if re.search(pattern, text_lower):
                return 0.9

        # 检查低确定性
        for pattern in LOW_CERTAINTY_PATTERNS:
            if re.search(pattern, text_lower):
                return 0.3

        # 默认中等
        return 0.5
```

---

## 3. 决策隔离机制

### 3.1 分层存储

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Decision Isolation Layers                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Layer 1: 可信决策池 (Trusted Pool)                                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 条件: certainty IN [CONFIRMED, EVIDENCED, EXPLICIT]             │   │
│  │ 权限: 可被检索引用，可出现在上下文中                             │   │
│  │ 标记: trusted=true                                              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Layer 2: 候选决策池 (Candidate Pool)                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 条件: certainty IN [INFERRED, IMPLICIT]                         │   │
│  │ 权限: 仅在明确查询时显示，不主动注入上下文                       │   │
│  │ 标记: trusted=false, needs_confirmation=true                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Layer 3: 讨论记录池 (Discussion Pool)                                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 条件: certainty IN [TENTATIVE, DISCUSSING, UNCERTAIN]           │   │
│  │ 权限: 仅作为历史记录，不参与决策检索                             │   │
│  │ 标记: is_discussion=true                                        │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Layer 4: 隔离区 (Quarantine)                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 条件: certainty IN [DISPUTED, RETRACTED] OR has_conflicts       │   │
│  │ 权限: 完全不参与检索，仅管理员可见                               │   │
│  │ 标记: quarantined=true                                          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 上下文注入规则

```python
class DecisionContextInjector:
    """决策上下文注入器 - 控制哪些决策可以进入上下文"""

    INJECTION_RULES = {
        # 可信决策: 可以直接注入
        DecisionCertainty.CONFIRMED: {
            "inject": True,
            "prefix": None,
            "max_age_days": None,  # 无时间限制
        },
        DecisionCertainty.EVIDENCED: {
            "inject": True,
            "prefix": None,
            "max_age_days": 365,
        },
        DecisionCertainty.EXPLICIT: {
            "inject": True,
            "prefix": None,
            "max_age_days": 180,
        },

        # 候选决策: 带警告前缀注入
        DecisionCertainty.INFERRED: {
            "inject": True,
            "prefix": "[待确认] ",
            "max_age_days": 30,
        },
        DecisionCertainty.IMPLICIT: {
            "inject": True,
            "prefix": "[推断] ",
            "max_age_days": 14,
        },

        # 低确定性: 不注入
        DecisionCertainty.TENTATIVE: {"inject": False},
        DecisionCertainty.DISCUSSING: {"inject": False},
        DecisionCertainty.UNCERTAIN: {"inject": False},

        # 特殊状态: 不注入
        DecisionCertainty.DISPUTED: {"inject": False},
        DecisionCertainty.RETRACTED: {"inject": False},
    }

    async def get_injectable_decisions(
        self,
        project_id: str,
        context_query: str,
        max_decisions: int = 5
    ) -> list[InjectedDecision]:
        """获取可注入上下文的决策"""

        # 仅从可信池检索
        decisions = await self.decision_service.search(
            project_id=project_id,
            query=context_query,
            certainty_filter=["CONFIRMED", "EVIDENCED", "EXPLICIT"],
            status_filter=["DECIDED", "IMPLEMENTED"],
            limit=max_decisions * 2  # 预留筛选空间
        )

        injectable = []
        for decision in decisions:
            rule = self.INJECTION_RULES.get(decision.certainty, {"inject": False})

            if not rule["inject"]:
                continue

            # 检查时间限制
            if rule.get("max_age_days"):
                age = (datetime.utcnow() - decision.decided_at).days
                if age > rule["max_age_days"]:
                    continue

            # 构建注入内容
            prefix = rule.get("prefix", "")
            injectable.append(InjectedDecision(
                decision_id=decision.id,
                content=f"{prefix}{decision.title}: {decision.summary}",
                certainty=decision.certainty,
                decided_at=decision.decided_at
            ))

            if len(injectable) >= max_decisions:
                break

        return injectable
```

---

## 4. 用户确认机制

### 4.1 确认触发条件

```python
class ConfirmationTrigger:
    """决策确认触发器"""

    TRIGGER_RULES = {
        # 规则1: 低确定性决策需要确认
        "low_certainty": {
            "condition": lambda d: d.certainty in [
                DecisionCertainty.INFERRED,
                DecisionCertainty.IMPLICIT,
                DecisionCertainty.UNCERTAIN
            ],
            "priority": "high",
            "message": "检测到可能的决策，请确认是否正确"
        },

        # 规则2: 高影响决策需要确认
        "high_impact": {
            "condition": lambda d: d.scope == DecisionScope.GLOBAL or
                                   d.category == DecisionCategory.ARCHITECTURE,
            "priority": "high",
            "message": "这是一个重要决策，请确认"
        },

        # 规则3: 有冲突的决策需要确认
        "has_conflict": {
            "condition": lambda d, ctx: len(ctx.conflicting_decisions) > 0,
            "priority": "critical",
            "message": "检测到冲突决策，请选择正确的决策"
        },

        # 规则4: 首次识别的决策
        "first_occurrence": {
            "condition": lambda d: d.occurrence_count == 1,
            "priority": "medium",
            "message": "首次识别此决策，请确认"
        },
    }

    async def should_request_confirmation(
        self,
        decision: Decision,
        context: DecisionContext
    ) -> Optional[ConfirmationRequest]:
        """判断是否需要请求用户确认"""

        for rule_name, rule in self.TRIGGER_RULES.items():
            condition = rule["condition"]

            # 执行条件检查
            try:
                if callable(condition):
                    # 支持带 context 和不带 context 的条件
                    import inspect
                    sig = inspect.signature(condition)
                    if len(sig.parameters) == 2:
                        triggered = condition(decision, context)
                    else:
                        triggered = condition(decision)
                else:
                    triggered = False
            except Exception:
                triggered = False

            if triggered:
                return ConfirmationRequest(
                    decision_id=decision.id,
                    rule=rule_name,
                    priority=rule["priority"],
                    message=rule["message"],
                    options=self._build_options(decision, rule_name)
                )

        return None

    def _build_options(
        self,
        decision: Decision,
        rule_name: str
    ) -> list[ConfirmationOption]:
        """构建确认选项"""

        options = [
            ConfirmationOption(
                id="confirm",
                label="确认此决策",
                action="confirm",
                description="标记为已确认决策"
            ),
            ConfirmationOption(
                id="modify",
                label="修改决策内容",
                action="modify",
                description="编辑决策详情"
            ),
            ConfirmationOption(
                id="reject",
                label="这不是决策",
                action="reject",
                description="标记为讨论内容，非决策"
            ),
            ConfirmationOption(
                id="defer",
                label="稍后确认",
                action="defer",
                description="暂不处理，保持待确认状态"
            ),
        ]

        # 有冲突时增加选项
        if rule_name == "has_conflict":
            options.insert(2, ConfirmationOption(
                id="resolve_conflict",
                label="解决冲突",
                action="resolve_conflict",
                description="选择正确的决策，废弃其他"
            ))

        return options
```

### 4.2 确认交互流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Decision Confirmation Flow                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. 检测到潜在决策                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 📋 检测到可能的决策:                                            │   │
│  │                                                                  │   │
│  │ "使用 Redis 作为缓存方案"                                        │   │
│  │                                                                  │   │
│  │ 确定性: 推断 (INFERRED)                                         │   │
│  │ 来源: 会话 sess_001 中的讨论                                     │   │
│  │                                                                  │   │
│  │ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐    │   │
│  │ │ ✅ 确认    │ │ ✏️ 修改    │ │ ❌ 不是决策 │ │ ⏰ 稍后    │    │   │
│  │ └────────────┘ └────────────┘ └────────────┘ └────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  2a. 用户点击 "确认"                                                    │
│  ─────────────────────────────────────────────────────────────────────  │
│  → certainty = CONFIRMED                                               │
│  → user_confirmed = true                                               │
│  → 进入可信决策池                                                       │
│                                                                         │
│  2b. 用户点击 "不是决策"                                                │
│  ─────────────────────────────────────────────────────────────────────  │
│  → certainty = RETRACTED                                               │
│  → 移入隔离区                                                           │
│  → 原记忆移除 decision 标签                                             │
│                                                                         │
│  2c. 用户点击 "稍后"                                                    │
│  ─────────────────────────────────────────────────────────────────────  │
│  → 保持在候选池                                                         │
│  → 设置提醒时间                                                         │
│  → 24小时后再次提示 (最多3次)                                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. 冲突检测与解决

### 5.1 冲突检测

```python
class DecisionConflictDetector:
    """决策冲突检测器"""

    async def detect_conflicts(
        self,
        new_decision: Decision
    ) -> list[ConflictResult]:
        """检测与现有决策的冲突"""

        conflicts = []

        # 1. 语义相似性检测
        similar_decisions = await self._find_similar_decisions(new_decision)

        for existing in similar_decisions:
            # 检查是否矛盾
            contradiction = await self._check_contradiction(new_decision, existing)

            if contradiction.is_conflicting:
                conflicts.append(ConflictResult(
                    existing_decision=existing,
                    new_decision=new_decision,
                    conflict_type=contradiction.type,
                    description=contradiction.description,
                    resolution_options=self._get_resolution_options(contradiction)
                ))

        return conflicts

    async def _check_contradiction(
        self,
        decision_a: Decision,
        decision_b: Decision
    ) -> ContradictionResult:
        """检查两个决策是否矛盾"""

        prompt = f"""
        分析以下两个决策是否存在矛盾:

        决策A (新):
        - 标题: {decision_a.title}
        - 内容: {decision_a.decision}
        - 时间: {decision_a.decided_at}

        决策B (已存在):
        - 标题: {decision_b.title}
        - 内容: {decision_b.decision}
        - 时间: {decision_b.decided_at}

        返回 JSON:
        {{
            "is_conflicting": true/false,
            "conflict_type": "direct_contradiction|partial_overlap|supersedes|unrelated",
            "description": "冲突描述",
            "resolution_suggestion": "建议的解决方式"
        }}
        """

        result = await self.llm.generate(prompt, response_format="json")
        return ContradictionResult(**result)


class ConflictType(Enum):
    """冲突类型"""
    DIRECT_CONTRADICTION = "direct_contradiction"  # 直接矛盾
    PARTIAL_OVERLAP = "partial_overlap"            # 部分重叠
    SUPERSEDES = "supersedes"                      # 新决策替代旧决策
    UNRELATED = "unrelated"                        # 不相关
```

### 5.2 冲突解决

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Conflict Resolution UI                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ⚠️ 检测到决策冲突                                                      │
│                                                                         │
│  ┌──────────────────────────┐    ┌──────────────────────────┐          │
│  │ 决策 A (2025-01-08)      │ vs │ 决策 B (2025-02-15)      │          │
│  │ "使用 Redis 作为缓存"    │    │ "使用 Memcached 缓存"   │          │
│  │                          │    │                          │          │
│  │ 状态: IMPLEMENTED        │    │ 状态: DECIDED            │          │
│  │ 证据: ✅ 有              │    │ 证据: ❌ 无              │          │
│  └──────────────────────────┘    └──────────────────────────┘          │
│                                                                         │
│  请选择解决方式:                                                        │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ ○ 保留决策 A，废弃决策 B                                        │   │
│  │   (B 将被标记为 RETRACTED)                                       │   │
│  │                                                                  │   │
│  │ ○ 保留决策 B，废弃决策 A                                        │   │
│  │   (A 将被标记为 SUPERSEDED)                                      │   │
│  │                                                                  │   │
│  │ ○ 两者都保留 (它们适用于不同场景)                               │   │
│  │   请说明: [________________]                                    │   │
│  │                                                                  │   │
│  │ ○ 两者都废弃，创建新决策                                        │   │
│  │   [创建新决策...]                                               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│                              [确认解决]                                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 6. 安全检索策略

### 6.1 检索过滤

```python
class SafeDecisionRetriever:
    """安全决策检索器"""

    async def retrieve_for_context(
        self,
        query: str,
        project_id: str,
        safety_level: SafetyLevel = SafetyLevel.STANDARD
    ) -> list[Decision]:
        """安全检索决策 (用于上下文注入)"""

        # 基础过滤条件
        filters = {
            "project_id": project_id,
            "quarantined": False,
        }

        # 根据安全级别调整
        if safety_level == SafetyLevel.STRICT:
            # 严格模式: 仅返回已确认+有证据的决策
            filters["certainty"] = ["CONFIRMED", "EVIDENCED"]
            filters["status"] = ["IMPLEMENTED"]

        elif safety_level == SafetyLevel.STANDARD:
            # 标准模式: 返回高确定性决策
            filters["certainty"] = ["CONFIRMED", "EVIDENCED", "EXPLICIT"]
            filters["status"] = ["DECIDED", "IMPLEMENTING", "IMPLEMENTED"]

        elif safety_level == SafetyLevel.LOOSE:
            # 宽松模式: 包含推断决策 (带标记)
            filters["certainty"] = [
                "CONFIRMED", "EVIDENCED", "EXPLICIT",
                "INFERRED", "IMPLICIT"
            ]

        decisions = await self.decision_service.search(
            query=query,
            **filters
        )

        # 添加安全元信息
        for decision in decisions:
            decision.safety_metadata = SafetyMetadata(
                can_cite=decision.certainty in ["CONFIRMED", "EVIDENCED"],
                needs_verification=decision.certainty in ["INFERRED", "IMPLICIT"],
                warning=self._get_warning(decision)
            )

        return decisions

    def _get_warning(self, decision: Decision) -> Optional[str]:
        """获取警告信息"""
        if decision.certainty == DecisionCertainty.INFERRED:
            return "此决策为系统推断，尚未经用户确认"
        if decision.certainty == DecisionCertainty.IMPLICIT:
            return "此决策为隐含推断，建议与用户确认"
        if not decision.evidence:
            return "此决策尚无执行证据"
        return None
```

### 6.2 引用时的安全提示

```python
class DecisionCitationFormatter:
    """决策引用格式化器"""

    def format_for_context(self, decision: Decision) -> str:
        """格式化决策用于上下文注入"""

        # 高确定性: 直接引用
        if decision.certainty in [DecisionCertainty.CONFIRMED, DecisionCertainty.EVIDENCED]:
            return f"[决策] {decision.title}: {decision.summary}"

        # 中确定性: 带警告
        elif decision.certainty in [DecisionCertainty.EXPLICIT]:
            return f"[决策] {decision.title}: {decision.summary}"

        # 低确定性: 带强警告
        elif decision.certainty in [DecisionCertainty.INFERRED, DecisionCertainty.IMPLICIT]:
            return f"[待确认决策] {decision.title}: {decision.summary} (需要用户确认)"

        # 其他: 不应该出现在这里
        else:
            return ""

    def format_for_response(self, decision: Decision) -> str:
        """格式化决策用于回复用户"""

        base = f"**{decision.title}**\n{decision.summary}"

        # 添加确定性标注
        if decision.certainty == DecisionCertainty.CONFIRMED:
            badge = "✅ 已确认"
        elif decision.certainty == DecisionCertainty.EVIDENCED:
            badge = "📝 有证据"
        elif decision.certainty == DecisionCertainty.INFERRED:
            badge = "⚠️ 待确认"
        else:
            badge = "❓ 不确定"

        return f"{badge} {base}"
```

---

## 7. 撤回与纠错

### 7.1 撤回机制

```python
class DecisionRetraction:
    """决策撤回服务"""

    async def retract(
        self,
        decision_id: str,
        reason: str,
        retracted_by: str
    ) -> RetractionResult:
        """撤回决策"""

        decision = await self.decision_service.get(decision_id)

        # 1. 更新决策状态
        decision.certainty = DecisionCertainty.RETRACTED
        decision.retracted_at = datetime.utcnow()
        decision.retracted_by = retracted_by
        decision.retraction_reason = reason

        # 2. 移入隔离区
        decision.quarantined = True

        # 3. 清理关联
        # - 从源记忆中移除 decision 标签
        await self._clean_source_memories(decision)
        # - 从 Neo4j 中标记为撤回
        await self._mark_retracted_in_graph(decision)

        # 4. 通知相关方
        await self._notify_retraction(decision)

        # 5. 记录撤回事件
        await self._log_retraction(decision, reason, retracted_by)

        return RetractionResult(
            success=True,
            decision_id=decision_id,
            affected_memories=decision.source_memories
        )

    async def _clean_source_memories(self, decision: Decision):
        """清理源记忆的决策标签"""
        for memory_id in decision.source_memories:
            memory = await self.memory_service.get(memory_id)
            if "decision" in memory.tags:
                memory.tags.remove("decision")
            if decision.id in memory.decision_ids:
                memory.decision_ids.remove(decision.id)
            await self.memory_service.update(memory)
```

### 7.2 定期审计

```python
class DecisionAudit:
    """决策审计任务"""

    async def run_daily_audit(self):
        """每日审计任务"""

        # 1. 检查长期未确认的决策
        stale_candidates = await self.decision_service.find(
            certainty=["INFERRED", "IMPLICIT", "UNCERTAIN"],
            created_before=datetime.utcnow() - timedelta(days=7),
            user_confirmed=False
        )

        for decision in stale_candidates:
            # 降级为讨论记录
            decision.certainty = DecisionCertainty.DISCUSSING
            await self.decision_service.update(decision)
            logger.info(f"Decision {decision.id} demoted due to lack of confirmation")

        # 2. 检查证据过期的决策
        expired_evidence = await self.decision_service.find(
            certainty="EVIDENCED",
            evidence_checked_before=datetime.utcnow() - timedelta(days=30)
        )

        for decision in expired_evidence:
            # 重新验证证据
            still_valid = await self.evidence_validator.revalidate(decision)
            if not still_valid:
                decision.certainty = DecisionCertainty.INFERRED
                decision.needs_confirmation = True
                await self.decision_service.update(decision)

        # 3. 生成审计报告
        return AuditReport(
            stale_demoted=len(stale_candidates),
            evidence_invalidated=len([d for d in expired_evidence if not d.evidence_valid])
        )
```

---

## 8. 总结: 风险控制清单

| 风险 | 控制措施 | 实现 |
|------|----------|------|
| **误识别** | 确定性评估 + 用户确认 | CertaintyAssessor |
| **上下文污染** | 分层隔离 + 安全检索 | DecisionIsolation |
| **虚假引用** | 引用时标注确定性 | CitationFormatter |
| **决策冲突** | 冲突检测 + 解决流程 | ConflictDetector |
| **过期决策** | 定期审计 + 证据重验 | DecisionAudit |
| **错误决策** | 撤回机制 + 隔离区 | DecisionRetraction |

---

## 9. 新增迭代故事

| Story ID | 标题 | 优先级 |
|----------|------|--------|
| **STORY-022** | **决策确定性评估** | **P0** |
| **STORY-023** | **决策隔离分层** | **P0** |
| **STORY-024** | **用户确认流程** | **P1** |
| **STORY-025** | **冲突检测与解决** | **P1** |
| **STORY-026** | **决策撤回机制** | **P1** |
| **STORY-027** | **定期审计任务** | **P2** |

---

是否确认此风险控制设计?
