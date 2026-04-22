"""add memory_conversation metadata table

Revision ID: c4b1a9e2f7d3
Revises: d7b9e3f4a1c2
Create Date: 2026-04-22 15:00:00
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "c4b1a9e2f7d3"
down_revision = "d7b9e3f4a1c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memory_conversation",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("conversation_id", sa.String(length=191), nullable=False, comment="Canonical conversation id"),
        sa.Column("external_source", sa.String(length=64), nullable=False, comment="External conversation source"),
        sa.Column(
            "external_session_id",
            sa.String(length=191),
            nullable=False,
            comment="External source session id",
        ),
        sa.Column("user_id", sa.String(length=100), nullable=False, comment="Owning user id"),
        sa.Column("agent_id", sa.String(length=100), nullable=True, comment="Owning agent id"),
        sa.Column("project_id", sa.String(length=255), nullable=True, comment="Project id"),
        sa.Column("title", sa.String(length=500), nullable=True, comment="Conversation title"),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
            comment="Conversation-level metadata",
        ),
        sa.Column(
            "message_store_type",
            sa.String(length=32),
            server_default=sa.text("'jsonl'"),
            nullable=False,
            comment="Message storage type",
        ),
        sa.Column("message_store_uri", sa.String(length=1024), nullable=False, comment="Authoritative jsonl locator"),
        sa.Column(
            "message_store_path",
            sa.String(length=1024),
            nullable=True,
            comment="Optional filesystem-compatible display path",
        ),
        sa.Column(
            "message_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
            comment="Count of message rows in the jsonl object",
        ),
        sa.Column(
            "modalities",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
            comment="Union of message content part types",
        ),
        sa.Column("content_sha256", sa.String(length=64), nullable=True, comment="Hash of current jsonl content"),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True, comment="Size of current jsonl object in bytes"),
        sa.Column(
            "version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
            comment="Monotonic conversation version",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'active'"),
            nullable=False,
            comment="Conversation resource status",
        ),
        sa.Column("first_message_at", sa.DateTime(), nullable=True, comment="Timestamp of first message"),
        sa.Column("last_message_at", sa.DateTime(), nullable=True, comment="Timestamp of latest message"),
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
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="Soft delete timestamp"),
        sa.PrimaryKeyConstraint("id"),
        comment="Programmer memory conversation metadata with external jsonl message storage",
    )
    op.create_index("idx_memory_conversation_last_message_at", "memory_conversation", ["last_message_at"], unique=False)
    op.create_index("idx_memory_conversation_project_updated_at", "memory_conversation", ["project_id", "updated_at"], unique=False)
    op.create_index("idx_memory_conversation_status", "memory_conversation", ["status"], unique=False)
    op.create_index("idx_memory_conversation_user_updated_at", "memory_conversation", ["user_id", "updated_at"], unique=False)
    op.create_index(
        "uq_memory_conversation_user_conversation_id",
        "memory_conversation",
        ["user_id", "conversation_id"],
        unique=True,
    )
    op.create_index(
        "uq_memory_conversation_user_source_session",
        "memory_conversation",
        ["user_id", "external_source", "external_session_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_memory_conversation_user_source_session", table_name="memory_conversation")
    op.drop_index("uq_memory_conversation_user_conversation_id", table_name="memory_conversation")
    op.drop_index("idx_memory_conversation_user_updated_at", table_name="memory_conversation")
    op.drop_index("idx_memory_conversation_status", table_name="memory_conversation")
    op.drop_index("idx_memory_conversation_project_updated_at", table_name="memory_conversation")
    op.drop_index("idx_memory_conversation_last_message_at", table_name="memory_conversation")
    op.drop_table("memory_conversation")
