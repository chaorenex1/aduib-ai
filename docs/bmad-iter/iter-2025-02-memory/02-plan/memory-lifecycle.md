# 记忆生命周期管理设计

**版本**: v1.0
**更新日期**: 2025-02-24

---

## 1. 核心理念

模拟人类记忆的三个关键特性：

| 特性 | 描述 | 实现机制 |
|------|------|----------|
| **注意力** | 关注用户关心的事 | 信号捕捉 → 重要性提升 |
| **巩固** | 重要记忆从短期转长期 | 工作记忆 → 情景/语义记忆 |
| **遗忘** | 淡化不重要的记忆 | 时间衰减 + 主动清理 |

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Memory Attention & Forgetting                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│     用户交互信号                                                         │
│     ┌──────────────────────────────────────────────────────────────┐   │
│     │ 显式信号           │ 隐式信号           │ 负向信号            │   │
│     │ • 点赞/收藏        │ • 重复访问         │ • 跳过/忽略         │   │
│     │ • 手动标记重要     │ • 长时间停留       │ • 纠正/否定         │   │
│     │ • 主动引用         │ • 相似问题再问     │ • 投诉/举报         │   │
│     └──────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                              ▼                                          │
│     ┌──────────────────────────────────────────────────────────────┐   │
│     │                  Attention Scorer                            │   │
│     │                                                              │   │
│     │  attention_score = Σ(signal_weight × recency_factor)         │   │
│     └──────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│              ┌───────────────┴───────────────┐                         │
│              ▼                               ▼                         │
│     ┌─────────────────┐             ┌─────────────────┐                │
│     │    升级路径      │             │    遗忘路径      │                │
│     │                 │             │                 │                │
│     │ score ↑ → L升级 │             │ score ↓ → 衰减  │                │
│     │ 工作→长期记忆   │             │ 超时 → 清理     │                │
│     └─────────────────┘             └─────────────────┘                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 记忆等级体系

### 2.1 统一等级定义

```python
class MemoryLevel(Enum):
    """记忆等级 (统一所有记忆类型)"""

    # 临时层
    L0_TRANSIENT = "L0"      # 临时记忆 - 会话内有效

    # 工作层
    L1_WORKING = "L1"        # 工作记忆 - 当前任务相关

    # 短期层
    L2_SHORT = "L2"          # 短期记忆 - 近期交互，可能遗忘

    # 长期层
    L3_LONG = "L3"           # 长期记忆 - 已巩固，较少遗忘
    L4_CORE = "L4"           # 核心记忆 - 高度重要，永久保留

    # 特殊状态
    FROZEN = "frozen"        # 冻结 - 用户手动保护
    ARCHIVED = "archived"    # 归档 - 不活跃但保留
```

### 2.2 等级特性

| Level | 名称 | TTL | 衰减速率 | 检索权重 | 升级条件 |
|-------|------|-----|----------|----------|----------|
| L0 | 临时 | 会话内 | 极快 | 1.0 | 自动 |
| L1 | 工作 | 1天 | 快 | 1.2 | 会话结束巩固 |
| L2 | 短期 | 7天 | 中 | 1.5 | attention ≥ 0.4 |
| L3 | 长期 | 90天 | 慢 | 2.0 | attention ≥ 0.7, 验证 ≥ 3 |
| L4 | 核心 | 永久 | 无 | 3.0 | attention ≥ 0.9, 验证 ≥ 5 |

---

## 3. 注意力评分系统

### 3.1 信号类型与权重

```python
class AttentionSignal(Enum):
    """注意力信号类型"""

    # 强正向信号 (用户明确关心)
    EXPLICIT_SAVE = ("explicit_save", 1.0)      # 收藏/保存
    EXPLICIT_IMPORTANT = ("explicit_important", 0.9)  # 标记重要
    MANUAL_REFERENCE = ("manual_reference", 0.8)  # 手动引用

    # 中正向信号 (隐式关心)
    REPEAT_ACCESS = ("repeat_access", 0.5)      # 重复访问
    LONG_ENGAGEMENT = ("long_engagement", 0.4)  # 长时间交互
    FOLLOW_UP_QUERY = ("follow_up_query", 0.4)  # 追问
    TASK_SUCCESS = ("task_success", 0.6)        # 任务成功使用

    # 弱正向信号
    VIEW = ("view", 0.1)                        # 查看
    COPY = ("copy", 0.2)                        # 复制内容

    # 负向信号 (用户不关心)
    SKIP = ("skip", -0.3)                       # 跳过
    DISMISS = ("dismiss", -0.5)                 # 关闭/忽略
    NEGATIVE_FEEDBACK = ("negative_feedback", -0.8)  # 负面反馈
    CORRECTION = ("correction", -0.6)           # 纠正内容
    REPORT = ("report", -1.0)                   # 举报
```

### 3.2 注意力评分计算

```python
@dataclass
class AttentionScore:
    """记忆的注意力评分"""
    memory_id: str
    raw_score: float          # 原始累计分
    normalized_score: float   # 归一化分 0-1
    signal_count: int         # 信号数量
    last_signal_at: datetime  # 最后信号时间
    trend: str                # "rising" | "stable" | "declining"


class AttentionScorer:
    """注意力评分器"""

    # 时间衰减因子
    RECENCY_HALF_LIFE_DAYS = 7  # 7天后信号权重减半

    def compute_score(self, memory_id: str) -> AttentionScore:
        """计算记忆的注意力得分"""
        signals = self._get_signals(memory_id)
        now = datetime.utcnow()

        raw_score = 0.0
        for signal in signals:
            # 时间衰减
            age_days = (now - signal.timestamp).days
            recency_factor = 0.5 ** (age_days / self.RECENCY_HALF_LIFE_DAYS)

            # 信号权重
            weight = signal.type.value[1]

            raw_score += weight * recency_factor

        # 归一化到 0-1
        normalized = self._normalize(raw_score, len(signals))

        # 计算趋势
        trend = self._compute_trend(signals)

        return AttentionScore(
            memory_id=memory_id,
            raw_score=raw_score,
            normalized_score=normalized,
            signal_count=len(signals),
            last_signal_at=signals[-1].timestamp if signals else None,
            trend=trend
        )

    def _normalize(self, raw: float, count: int) -> float:
        """归一化评分"""
        if count == 0:
            return 0.0
        # 基于信号数量的缩放
        scale = min(1.0, count / 10)  # 10个信号达到满分潜力
        # Sigmoid 归一化
        return scale * (1 / (1 + math.exp(-raw)))

    def _compute_trend(self, signals: list) -> str:
        """计算趋势 (最近7天 vs 之前)"""
        if len(signals) < 2:
            return "stable"

        now = datetime.utcnow()
        recent = sum(1 for s in signals if (now - s.timestamp).days <= 7)
        older = len(signals) - recent

        if recent > older * 1.5:
            return "rising"
        elif recent < older * 0.5:
            return "declining"
        return "stable"
```

---

## 4. 升级机制

### 4.1 升级路径

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Memory Promotion Path                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────┐                                                                │
│  │ L0  │ ─────────────────────────────────────────────────────────────┐ │
│  │临时 │  会话结束时自动评估                                           │ │
│  └──┬──┘                                                              │ │
│     │                                                                  │ │
│     │ 条件: 有交互 且 非负面                                           │ │
│     ▼                                                                  │ │
│  ┌─────┐                                                              │ │
│  │ L1  │ ─────────────────────────────────────────────────────────┐   │ │
│  │工作 │  定期巩固检查 (每日)                                       │   │ │
│  └──┬──┘                                                          │   │ │
│     │                                                              │   │ │
│     │ 条件: attention ≥ 0.4                                        │   │ │
│     │       访问次数 ≥ 2                                           │   │ │
│     ▼                                                              │   │ │
│  ┌─────┐                                                          │   │ │
│  │ L2  │ ─────────────────────────────────────────────────────┐   │   │ │
│  │短期 │  周期巩固检查 (每周)                                   │   │   │ │
│  └──┬──┘                                                      │   │   │ │
│     │                                                          │   │   │ │
│     │ 条件: attention ≥ 0.7                                    │   │   │ │
│     │       验证通过 ≥ 3                                       │   │   │ │
│     │       无强负向信号                                        │   │   │ │
│     ▼                                                          │   │   │ │
│  ┌─────┐                                                      │   │   │ │
│  │ L3  │ ─────────────────────────────────────────────────┐   │   │   │ │
│  │长期 │  长期巩固检查 (每月)                               │   │   │   │ │
│  └──┬──┘                                                  │   │   │   │ │
│     │                                                      │   │   │   │ │
│     │ 条件: attention ≥ 0.9                                │   │   │   │ │
│     │       验证通过 ≥ 5                                   │   │   │   │ │
│     │       trend = "rising" 或 "stable"                   │   │   │   │ │
│     │       无任何负向信号                                  │   │   │   │ │
│     ▼                                                      │   │   │   │ │
│  ┌─────┐                                                  │   │   │   │ │
│  │ L4  │  核心记忆 - 永久保留                              │   │   │   │ │
│  │核心 │                                                  │   │   │   │ │
│  └─────┘                                                  │   │   │   │ │
│                                                            │   │   │   │ │
│  ┌─────┐                                                  │   │   │   │ │
│  │FROZEN│◀─── 用户手动保护 (任意等级可冻结) ◀──────────────┴───┴───┴───┘ │
│  └─────┘                                                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 升级服务

```python
class MemoryPromotion:
    """记忆升级服务"""

    PROMOTION_RULES = {
        MemoryLevel.L0_TRANSIENT: {
            "target": MemoryLevel.L1_WORKING,
            "conditions": {
                "min_interactions": 1,
                "no_negative_signals": True,
            }
        },
        MemoryLevel.L1_WORKING: {
            "target": MemoryLevel.L2_SHORT,
            "conditions": {
                "min_attention": 0.4,
                "min_access_count": 2,
            }
        },
        MemoryLevel.L2_SHORT: {
            "target": MemoryLevel.L3_LONG,
            "conditions": {
                "min_attention": 0.7,
                "min_validations": 3,
                "no_strong_negative": True,
            }
        },
        MemoryLevel.L3_LONG: {
            "target": MemoryLevel.L4_CORE,
            "conditions": {
                "min_attention": 0.9,
                "min_validations": 5,
                "trend_not_declining": True,
                "no_negative_signals": True,
            }
        }
    }

    async def evaluate_promotion(self, memory: Memory) -> Optional[MemoryLevel]:
        """评估是否应该升级"""
        if memory.level == MemoryLevel.FROZEN:
            return None  # 冻结记忆不升级

        rule = self.PROMOTION_RULES.get(memory.level)
        if not rule:
            return None

        attention = await self.scorer.compute_score(memory.id)
        stats = await self._get_memory_stats(memory.id)

        if self._check_conditions(rule["conditions"], attention, stats):
            return rule["target"]

        return None

    async def run_promotion_batch(self, batch_size: int = 100):
        """批量升级检查"""
        candidates = await self._get_promotion_candidates(batch_size)

        for memory in candidates:
            new_level = await self.evaluate_promotion(memory)
            if new_level:
                await self._promote(memory, new_level)
                await self._emit_event("memory.promoted", {
                    "memory_id": memory.id,
                    "from_level": memory.level,
                    "to_level": new_level,
                })
```

---

## 5. 遗忘机制

### 5.1 遗忘类型

| 类型 | 描述 | 触发条件 |
|------|------|----------|
| **自然衰减** | 记忆权重随时间降低 | 时间流逝 |
| **注意力遗忘** | 低关注度记忆被淘汰 | attention 持续低 |
| **TTL 过期** | 超过生存时间 | 到期未续期 |
| **主动遗忘** | 用户触发删除 | 用户操作 |
| **空间压力** | 存储满时淘汰低优先级 | 容量阈值 |

### 5.2 遗忘曲线实现

```python
class ForgettingCurve:
    """艾宾浩斯遗忘曲线"""

    def retention_rate(self, memory: Memory, now: datetime) -> float:
        """计算记忆保留率 (0-1)"""
        # 基础保留率 = e^(-t/S)
        # t = 时间间隔
        # S = 记忆强度 (由等级和注意力决定)

        age_hours = (now - memory.last_accessed_at).total_seconds() / 3600
        strength = self._compute_strength(memory)

        retention = math.exp(-age_hours / strength)
        return max(0.0, min(1.0, retention))

    def _compute_strength(self, memory: Memory) -> float:
        """计算记忆强度 (影响衰减速度)"""
        base_strength = {
            MemoryLevel.L0_TRANSIENT: 2,      # 2小时半衰期
            MemoryLevel.L1_WORKING: 24,       # 1天
            MemoryLevel.L2_SHORT: 168,        # 7天
            MemoryLevel.L3_LONG: 2160,        # 90天
            MemoryLevel.L4_CORE: float('inf'),  # 永不衰减
        }.get(memory.level, 24)

        # 注意力加成
        attention_boost = memory.attention_score * 0.5  # 最多+50%强度

        return base_strength * (1 + attention_boost)


class Forgetting:
    """遗忘服务"""

    # 遗忘阈值
    RETENTION_THRESHOLD = 0.2  # 保留率低于20%时触发遗忘
    ATTENTION_THRESHOLD = 0.1  # 注意力低于10%时触发遗忘

    async def evaluate_forgetting(self, memory: Memory) -> bool:
        """评估是否应该遗忘"""
        # 冻结/核心记忆不遗忘
        if memory.level in [MemoryLevel.FROZEN, MemoryLevel.L4_CORE]:
            return False

        now = datetime.utcnow()

        # 检查 TTL
        if memory.ttl_expire_at and memory.ttl_expire_at < now:
            return True

        # 检查保留率
        retention = self.curve.retention_rate(memory, now)
        if retention < self.RETENTION_THRESHOLD:
            return True

        # 检查注意力
        attention = await self.scorer.compute_score(memory.id)
        if attention.normalized_score < self.ATTENTION_THRESHOLD:
            # 额外条件: 持续低注意力 30 天
            if attention.last_signal_at:
                days_since_signal = (now - attention.last_signal_at).days
                if days_since_signal > 30:
                    return True

        return False

    async def forget(self, memory: Memory, reason: str):
        """执行遗忘"""
        # 软删除 - 移到归档
        memory.level = MemoryLevel.ARCHIVED
        memory.archived_at = datetime.utcnow()
        memory.archive_reason = reason

        await self._save(memory)
        await self._remove_from_index(memory.id)
        await self._emit_event("memory.forgotten", {
            "memory_id": memory.id,
            "reason": reason,
        })

    async def run_forgetting_batch(self, batch_size: int = 500):
        """批量遗忘检查"""
        candidates = await self._get_forgetting_candidates(batch_size)
        forgotten = 0

        for memory in candidates:
            if await self.evaluate_forgetting(memory):
                reason = self._determine_reason(memory)
                await self.forget(memory, reason)
                forgotten += 1

        return forgotten
```

### 5.3 遗忘保护

```python
class ForgettingProtection:
    """遗忘保护机制"""

    async def protect_memory(self, memory_id: str, duration_days: int = None):
        """保护记忆不被遗忘"""
        memory = await self._get_memory(memory_id)

        if duration_days:
            # 临时保护
            memory.protected_until = datetime.utcnow() + timedelta(days=duration_days)
        else:
            # 永久冻结
            memory.level = MemoryLevel.FROZEN

        await self._save(memory)

    async def bulk_protect_by_tag(self, tag: str, duration_days: int):
        """按标签批量保护"""
        memories = await self._get_memories_by_tag(tag)
        for memory in memories:
            await self.protect_memory(memory.id, duration_days)
```

---

## 6. 调度任务

### 6.1 定时任务配置

```python
# runtime/memory/lifecycle/scheduler.py

class MemoryLifecycleScheduler:
    """记忆生命周期调度器"""

    SCHEDULES = {
        # 会话结束时
        "session_end": {
            "task": "consolidate_working_memory",
            "trigger": "on_session_end",
        },

        # 每日任务
        "daily_promotion": {
            "task": "run_promotion_batch",
            "cron": "0 3 * * *",  # 每天凌晨3点
            "params": {"levels": [MemoryLevel.L1_WORKING]},
        },
        "daily_forgetting": {
            "task": "run_forgetting_batch",
            "cron": "0 4 * * *",  # 每天凌晨4点
            "params": {"levels": [MemoryLevel.L0_TRANSIENT, MemoryLevel.L1_WORKING]},
        },

        # 每周任务
        "weekly_promotion": {
            "task": "run_promotion_batch",
            "cron": "0 3 * * 0",  # 每周日凌晨3点
            "params": {"levels": [MemoryLevel.L2_SHORT]},
        },
        "weekly_forgetting": {
            "task": "run_forgetting_batch",
            "cron": "0 4 * * 0",
            "params": {"levels": [MemoryLevel.L2_SHORT]},
        },

        # 每月任务
        "monthly_promotion": {
            "task": "run_promotion_batch",
            "cron": "0 3 1 * *",  # 每月1号凌晨3点
            "params": {"levels": [MemoryLevel.L3_LONG]},
        },
        "monthly_cleanup": {
            "task": "cleanup_archived",
            "cron": "0 5 1 * *",
            "params": {"older_than_days": 180},  # 清理180天前的归档
        },
    }
```

---

## 7. 用户控制接口

### 7.1 API 设计

```python
# controllers/memory/lifecycle.py

router = APIRouter(prefix="/memory/lifecycle", tags=["memory_lifecycle"])


@router.post("/memories/{memory_id}/signal")
async def record_signal(memory_id: str, signal: AttentionSignalPayload):
    """记录注意力信号"""
    return LifecycleService.record_signal(
        memory_id=memory_id,
        signal_type=signal.type,
        payload=signal.payload
    )


@router.post("/memories/{memory_id}/protect")
async def protect_memory(memory_id: str, payload: ProtectPayload):
    """保护记忆"""
    return LifecycleService.protect_memory(
        memory_id=memory_id,
        duration_days=payload.duration_days
    )


@router.post("/memories/{memory_id}/freeze")
async def freeze_memory(memory_id: str):
    """冻结记忆 (永久保护)"""
    return LifecycleService.freeze_memory(memory_id)


@router.post("/memories/{memory_id}/forget")
async def forget_memory(memory_id: str):
    """主动遗忘"""
    return LifecycleService.forget_memory(memory_id, reason="user_requested")


@router.get("/memories/{memory_id}/attention")
async def get_attention_score(memory_id: str):
    """获取注意力得分"""
    return LifecycleService.get_attention_score(memory_id)


@router.get("/stats/lifecycle")
async def get_lifecycle_stats():
    """获取生命周期统计"""
    return LifecycleService.get_stats()
```

---

## 8. 与现有 QA Memory 对比

| 特性 | QA Memory (现有) | 统一记忆系统 (新) |
|------|------------------|-------------------|
| 等级数 | 4级 (L0-L3) | 5级 (L0-L4) + 特殊状态 |
| 升级依据 | 验证次数 + 信任分 | 注意力得分 + 验证 + 趋势 |
| 降级机制 | 连续失败降级 | 自然衰减 + 注意力遗忘 |
| 信号类型 | 验证信号 (pass/fail) | 多种交互信号 |
| 遗忘 | TTL 过期 | 遗忘曲线 + 多维度评估 |
| 用户控制 | 无 | 冻结/保护/主动遗忘 |

---

## 9. 更新迭代故事

新增/修改故事:

| Story ID | 标题 | 优先级 |
|----------|------|--------|
| STORY-010 | 实现记忆整合机制 | P1 → **P0** |
| STORY-011 | 实现遗忘机制 | P2 → **P1** |
| **STORY-010b** | **实现注意力评分系统** | **P1 新增** |
| **STORY-010c** | **实现记忆升级服务** | **P1 新增** |
| **STORY-011b** | **实现遗忘曲线** | **P1 新增** |
| **STORY-011c** | **生命周期调度任务** | **P2 新增** |

---

是否确认此设计并开始实现?
