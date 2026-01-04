"""create task_cache table for orchestrator integration

Revision ID: task_cache_001
Revises: 3e3d1369dd34
Create Date: 2026-01-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'task_cache_001'
down_revision: Union[str, None] = '3e3d1369dd34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - create task_cache table."""
    op.create_table(
        'task_cache',
        sa.Column('id', sa.Integer(), nullable=False, comment='Task cache id'),
        sa.Column('request', sa.Text(), nullable=False, comment='Original request content'),
        sa.Column('request_hash', sa.String(length=64), nullable=False, comment='SHA256 hash of request:mode:backend'),
        sa.Column('mode', sa.String(length=32), nullable=False, comment='Execution mode: command/agent/prompt/skill/backend'),
        sa.Column('backend', sa.String(length=32), nullable=False, comment='Backend type: claude/gemini/codex'),
        sa.Column('success', sa.Boolean(), nullable=False, server_default=sa.text('true'), comment='Whether execution succeeded'),
        sa.Column('output', sa.Text(), nullable=False, comment='Task output content'),
        sa.Column('error', sa.Text(), nullable=True, comment='Error message if failed'),
        sa.Column('run_id', sa.String(length=64), nullable=True, comment='Memex-CLI run ID'),
        sa.Column('duration_seconds', sa.Float(), nullable=True, comment='Execution duration in seconds'),
        sa.Column('hit_count', sa.Integer(), nullable=False, server_default=sa.text('0'), comment='Cache hit count'),
        sa.Column('created_at', sa.DateTime(), nullable=False, comment='Task creation time'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, comment='Last update time'),
        sa.PrimaryKeyConstraint('id'),
        comment='Task cache and history table for Orchestrator integration'
    )

    # Create indexes
    op.create_index('ix_task_cache_id', 'task_cache', ['id'], unique=False)
    op.create_index('idx_request_hash_mode_backend', 'task_cache', ['request_hash', 'mode', 'backend'], unique=True)
    op.create_index('idx_created_at', 'task_cache', ['created_at'], unique=False)
    op.create_index('idx_mode', 'task_cache', ['mode'], unique=False)
    op.create_index('idx_backend', 'task_cache', ['backend'], unique=False)


def downgrade() -> None:
    """Downgrade schema - drop task_cache table."""
    op.drop_index('idx_backend', table_name='task_cache')
    op.drop_index('idx_mode', table_name='task_cache')
    op.drop_index('idx_created_at', table_name='task_cache')
    op.drop_index('idx_request_hash_mode_backend', table_name='task_cache')
    op.drop_index('ix_task_cache_id', table_name='task_cache')
    op.drop_table('task_cache')
