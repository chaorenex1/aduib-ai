from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass
class ResultDetail:
    memory_id: str
    hit_count: int = 1  # 被几条子查询命中
    evidence_count: int = 1  # 被几轮 ReAct 动作验证
    rag_score: float = 0.0  # graph-boost 后、LLM 融合前的原始 score
    from_expansion: bool = False  # 来自图谱邻居扩展
    judge_rank: int | None = None  # LLM judge 给出的排序位（None = 未入选 judge 输出）
    final_score: float | None = None
    final_rank: int | None = None  # 在最终结果中的位置（None = 未进入最终结果）
    memory_domain: str = ""
    memory_type: str = ""
    memory_source: str = ""
    retrieval_sources: list[str] = field(default_factory=list)


@dataclass
class ReActStepTrace:
    step_index: int
    action_type: str
    query_hash: str = ""
    retrieval_method: str = ""
    score_threshold: float | None = None
    input_candidate_count: int = 0
    output_candidate_count: int = 0
    new_candidate_count: int = 0
    graph_prefetch_count: int = 0
    graph_boost_count: int = 0
    graph_expansion_count: int = 0
    latency_ms: int = 0
    strategy_reason: str = ""
    threshold_reason: str = ""
    stop_reason: str = ""
    reason_summary: str = ""


@dataclass
class RetrievalTrace:
    # ── 请求标识 ──────────────────────────────────
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str = ""
    agent_id: str | None = None
    project_id: str | None = None
    retrieve_type: str = "llm"
    top_k: int = 5
    query_hash: str = ""  # SHA256(query)[:16]，不存明文

    # ── Step 0: Memory Structure ──────────────────
    ms_domain_count: int = 0  # 注入的 domain 数
    ms_topic_count: int = 0  # 注入的 topic 数
    latency_step0_ms: int = 0

    # ── Step 1: Planner / Retrieval Orchestration ─
    latency_step1_ms: int = 0

    # ── Step 2: Retrieval Execution ───────────────
    candidate_total_raw: int = 0  # merge 前总数（含跨子查询重复）
    candidate_total_unique: int = 0  # merge 后唯一 memory_id 数
    latency_step2_ms: int = 0

    # ── Step 3: LLM Judge ─────────────────────────
    judge_input_count: int = 0
    judge_output_count: int = 0
    judge_selection_rate: float = 0.0
    judge_failed: bool = False  # 降级为 score 排序
    judge_score_weights: dict[str, float] = field(default_factory=dict)
    judge_weight_reason: str = ""
    latency_step3_ms: int = 0

    # ── ReAct Loop ────────────────────────────────
    react_enabled: bool = False
    react_step_count: int = 0
    react_stop_reason: str = ""
    react_repeated_action_count: int = 0
    react_total_new_candidates: int = 0
    react_unique_action_query_count: int = 0
    react_steps: list[ReActStepTrace] = field(default_factory=list)

    # ── Final Results ──────────────────────────────
    final_count: int = 0
    final_score_avg: float = 0.0
    final_score_p50: float = 0.0
    final_score_p10: float = 0.0  # 最低 10% 分位，反映召回下界
    domain_dist: dict[str, int] = field(default_factory=dict)
    source_dist: dict[str, int] = field(default_factory=dict)
    type_dist: dict[str, int] = field(default_factory=dict)

    latency_total_ms: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # ── Per-result Detail ─────────────────────────
    result_details: list[ResultDetail] = field(default_factory=list)

    @staticmethod
    def hash_query(query: str) -> str:
        return hashlib.sha256(query.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["created_at"] = self.created_at.isoformat()
        return d
