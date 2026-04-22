"""add memory_write_task table for async memory pipeline

Revision ID: d7b9e3f4a1c2
Revises: a6f3c2d1b9e4
Create Date: 2026-04-19 14:23:00
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "d7b9e3f4a1c2"
down_revision = "a6f3c2d1b9e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memory_write_task",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="DB row id"),
        sa.Column("task_id", sa.String(length=64), nullable=False, comment="Public task id"),
        sa.Column("trigger_type", sa.String(length=32), nullable=False, comment="memory_api | session_commit"),
        sa.Column("user_id", sa.String(length=100), nullable=True, comment="Owning user id"),
        sa.Column("agent_id", sa.String(length=100), nullable=True, comment="Owning agent id"),
        sa.Column("project_id", sa.String(length=255), nullable=True, comment="Project id"),
        sa.Column("trace_id", sa.String(length=64), nullable=False, comment="Trace id"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False, comment="Idempotency key"),
        sa.Column(
            "source_ref",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
            comment="Stable source reference for background extraction",
        ),
        sa.Column(
            "archive_ref",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Archived source details used by worker",
        ),
        sa.Column(
            "queue_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Metadata-only queue envelope",
        ),
        sa.Column(
            "result_ref",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Result metadata from compatibility projector",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'pending'"),
            comment="pending | accepted | running | committed | rolled_back | needs_manual_recovery | publish_failed",
        ),
        sa.Column(
            "phase",
            sa.String(length=64),
            nullable=False,
            server_default=sa.text("'accepted'"),
            comment="Detailed phase state machine",
        ),
        sa.Column(
            "queue_status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'publish_pending'"),
            comment="publish_pending | queued | publish_failed",
        ),
        sa.Column(
            "retry_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Publish retry attempts",
        ),
        sa.Column(
            "retry_budget",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("3"),
            comment="Max publish retry attempts",
        ),
        sa.Column("last_publish_error", sa.Text(), nullable=True, comment="Last publish error"),
        sa.Column("publish_failed_at", sa.DateTime(), nullable=True, comment="Publish failure timestamp"),
        sa.Column("replayed_by", sa.String(length=100), nullable=True, comment="Operator that replayed publish_failed"),
        sa.Column("replayed_at", sa.DateTime(), nullable=True, comment="Replay timestamp"),
        sa.Column("failure_code", sa.String(length=64), nullable=True, comment="Failure code"),
        sa.Column("failure_message", sa.Text(), nullable=True, comment="Failure message"),
        sa.Column("last_error", sa.Text(), nullable=True, comment="Last error seen by task"),
        sa.Column(
            "rollback_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Rollback and recovery metadata payload",
        ),
        sa.Column("journal_ref", sa.String(length=255), nullable=True, comment="Commit journal location"),
        sa.Column("operator_notes", sa.Text(), nullable=True, comment="Operator notes"),
        sa.Column(
            "recovery_owner",
            sa.String(length=100),
            nullable=True,
            comment="On-call owner for needs_manual_recovery",
        ),
        sa.Column("recovery_opened_at", sa.DateTime(), nullable=True, comment="Recovery issue opened timestamp"),
        sa.Column(
            "recovery_ack_deadline",
            sa.DateTime(),
            nullable=True,
            comment="Recovery acknowledgement deadline",
        ),
        sa.Column("recovery_sla_deadline", sa.DateTime(), nullable=True, comment="Recovery mitigation deadline"),
        sa.Column("queued_at", sa.DateTime(), nullable=True, comment="Queue ack timestamp"),
        sa.Column("started_at", sa.DateTime(), nullable=True, comment="Worker started timestamp"),
        sa.Column("completed_at", sa.DateTime(), nullable=True, comment="Terminal completion timestamp"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="Creation time",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="Last update time",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Queue-first async memory write task lifecycle and journal metadata",
    )
    op.create_index("idx_memory_write_task_created_at", "memory_write_task", ["created_at"], unique=False)
    op.create_index("idx_memory_write_task_idempotency", "memory_write_task", ["idempotency_key"], unique=False)
    op.create_index("idx_memory_write_task_phase", "memory_write_task", ["phase"], unique=False)
    op.create_index("idx_memory_write_task_queue_status", "memory_write_task", ["queue_status"], unique=False)
    op.create_index("idx_memory_write_task_status", "memory_write_task", ["status"], unique=False)
    op.create_index("idx_memory_write_task_task_id", "memory_write_task", ["task_id"], unique=True)


def downgrade() -> None:
    op.drop_index("idx_memory_write_task_task_id", table_name="memory_write_task")
    op.drop_index("idx_memory_write_task_status", table_name="memory_write_task")
    op.drop_index("idx_memory_write_task_queue_status", table_name="memory_write_task")
    op.drop_index("idx_memory_write_task_phase", table_name="memory_write_task")
    op.drop_index("idx_memory_write_task_idempotency", table_name="memory_write_task")
    op.drop_index("idx_memory_write_task_created_at", table_name="memory_write_task")
    op.drop_table("memory_write_task")
