"""replace legacy active retrieval log fields with react fields

Revision ID: a6f3c2d1b9e4
Revises: 5255e589bb54
Create Date: 2026-03-21 10:45:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "a6f3c2d1b9e4"
down_revision = "5255e589bb54"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("memory_retrieval_log", sa.Column("judge_score_weights", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("memory_retrieval_log", sa.Column("judge_weight_reason", sa.Text(), nullable=True))
    op.add_column("memory_retrieval_log", sa.Column("react_enabled", sa.Boolean(), nullable=True))
    op.add_column("memory_retrieval_log", sa.Column("react_step_count", sa.SmallInteger(), nullable=True))
    op.add_column("memory_retrieval_log", sa.Column("react_stop_reason", sa.String(length=64), nullable=True))
    op.add_column("memory_retrieval_log", sa.Column("react_repeated_action_count", sa.Integer(), nullable=True))
    op.add_column("memory_retrieval_log", sa.Column("react_total_new_candidates", sa.Integer(), nullable=True))
    op.add_column("memory_retrieval_log", sa.Column("react_unique_action_query_count", sa.Integer(), nullable=True))
    op.add_column("memory_retrieval_log", sa.Column("react_steps", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    op.add_column("memory_retrieval_result", sa.Column("evidence_count", sa.SmallInteger(), nullable=True, comment="被几轮 ReAct 动作验证"))
    op.add_column(
        "memory_retrieval_result",
        sa.Column("retrieval_sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="该记忆被哪些检索机制命中"),
    )

    op.drop_column("memory_retrieval_log", "sub_query_count")
    op.drop_column("memory_retrieval_log", "sub_query_failed")
    op.drop_column("memory_retrieval_log", "sub_query_stats")
    op.drop_column("memory_retrieval_log", "multi_hit_count")
    op.drop_column("memory_retrieval_log", "multi_hit_max")


def downgrade() -> None:
    op.add_column("memory_retrieval_log", sa.Column("multi_hit_max", sa.SmallInteger(), nullable=True))
    op.add_column("memory_retrieval_log", sa.Column("multi_hit_count", sa.Integer(), nullable=True))
    op.add_column(
        "memory_retrieval_log",
        sa.Column("sub_query_stats", postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="[{query_hash, candidate_count, ...}]"),
    )
    op.add_column("memory_retrieval_log", sa.Column("sub_query_failed", sa.Boolean(), nullable=True))
    op.add_column("memory_retrieval_log", sa.Column("sub_query_count", sa.SmallInteger(), nullable=True))

    op.drop_column("memory_retrieval_result", "retrieval_sources")
    op.drop_column("memory_retrieval_result", "evidence_count")

    op.drop_column("memory_retrieval_log", "react_steps")
    op.drop_column("memory_retrieval_log", "react_unique_action_query_count")
    op.drop_column("memory_retrieval_log", "react_total_new_candidates")
    op.drop_column("memory_retrieval_log", "react_repeated_action_count")
    op.drop_column("memory_retrieval_log", "react_stop_reason")
    op.drop_column("memory_retrieval_log", "react_step_count")
    op.drop_column("memory_retrieval_log", "react_enabled")
    op.drop_column("memory_retrieval_log", "judge_weight_reason")
    op.drop_column("memory_retrieval_log", "judge_score_weights")
