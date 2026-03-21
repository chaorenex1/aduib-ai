import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, Numeric, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from models.base import Base


class MemoryRetrievalLog(Base):
    """一次 LLM/RAG 检索的全链路统计汇总。"""

    __tablename__ = "memory_retrieval_log"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    user_id = Column(String(100), nullable=False)
    agent_id = Column(String(100), nullable=True)
    project_id = Column(String(100), nullable=True)
    retrieve_type = Column(String(10), nullable=False, comment="rag | llm")
    top_k = Column(SmallInteger, nullable=False)
    query_hash = Column(String(16), nullable=False, comment="SHA256(query)[:16]")

    # Step 0: memory structure
    ms_domain_count = Column(SmallInteger, default=0)
    ms_topic_count = Column(SmallInteger, default=0)
    latency_step0_ms = Column(Integer, default=0)

    # Step 1: sub-query generation
    sub_query_count = Column(SmallInteger, default=0)
    sub_query_failed = Column(Boolean, default=False)
    latency_step1_ms = Column(Integer, default=0)

    # Step 2: parallel RAG
    sub_query_stats = Column(JSONB, nullable=True, comment="[{query_hash, candidate_count, ...}]")
    candidate_total_raw = Column(Integer, default=0)
    candidate_total_unique = Column(Integer, default=0)
    multi_hit_count = Column(Integer, default=0)
    multi_hit_max = Column(SmallInteger, default=0)
    latency_step2_ms = Column(Integer, default=0)

    # Step 3: LLM judge
    judge_input_count = Column(Integer, default=0)
    judge_output_count = Column(Integer, default=0)
    judge_selection_rate = Column(Numeric(4, 3), nullable=True)
    judge_failed = Column(Boolean, default=False)
    latency_step3_ms = Column(Integer, default=0)

    # Final results
    final_count = Column(SmallInteger, default=0)
    final_score_avg = Column(Numeric(5, 4), nullable=True)
    final_score_p50 = Column(Numeric(5, 4), nullable=True)
    final_score_p10 = Column(Numeric(5, 4), nullable=True)
    domain_dist = Column(JSONB, nullable=True)
    source_dist = Column(JSONB, nullable=True)
    type_dist = Column(JSONB, nullable=True)

    latency_total_ms = Column(Integer, default=0)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.UTC),
    )


class MemoryRetrievalResult(Base):
    """单次检索中每条候选记忆的明细，用于跨检索的精细分析。"""

    __tablename__ = "memory_retrieval_result"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    # 不加 FK 约束，避免记忆删除后级联问题
    log_id = Column(UUID(as_uuid=True), nullable=False)
    memory_id = Column(UUID(as_uuid=True), nullable=False)

    hit_count = Column(SmallInteger, default=1, comment="被几条子查询命中")
    rag_score = Column(Numeric(5, 4), nullable=True, comment="LLM 融合前的原始向量 score")
    from_expansion = Column(Boolean, default=False, comment="来自图谱邻居扩展")
    judge_rank = Column(SmallInteger, nullable=True, comment="LLM judge 排序位，NULL=未入选 judge 输出")
    final_score = Column(Numeric(5, 4), nullable=True)
    final_rank = Column(SmallInteger, nullable=True, comment="最终结果位置，NULL=未进入最终结果")

    memory_domain = Column(String(50), nullable=True)
    memory_type = Column(String(32), nullable=True)
    memory_source = Column(String(50), nullable=True)
    access_count_at_query = Column(Integer, default=0, comment="查询时刻的 access_count 快照")
