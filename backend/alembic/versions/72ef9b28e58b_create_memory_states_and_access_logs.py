"""create_memory_states_and_access_logs

Revision ID: 72ef9b28e58b
Revises: da19d5beb9a7
Create Date: 2026-07-12 00:31:08.839716

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '72ef9b28e58b'
down_revision: Union[str, Sequence[str], None] = 'da19d5beb9a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create memory_states table
    op.create_table('memory_states',
    sa.Column('memory_id', sa.Uuid(), nullable=False),
    sa.Column('access_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('retrieval_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('reinforcement_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('last_accessed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_reinforced_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('decay_score', sa.Float(), server_default='0.0', nullable=False),
    sa.Column('confidence_score', sa.Float(), server_default='0.0', nullable=False),
    sa.Column('importance_score', sa.Float(), server_default='0.0', nullable=False),
    sa.Column('source_type', sa.String(length=50), server_default='user', nullable=False),
    sa.ForeignKeyConstraint(['memory_id'], ['memories.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('memory_id')
    )
    
    # Create memory_access_logs table
    op.create_table('memory_access_logs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('memory_id', sa.Uuid(), nullable=False),
    sa.Column('conversation_id', sa.Uuid(), nullable=True),
    sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('similarity_score', sa.Float(), nullable=False),
    sa.Column('ranking_score', sa.Float(), nullable=False),
    sa.Column('retrieval_success', sa.Boolean(), server_default='true', nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['memory_id'], ['memories.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_memory_access_logs_memory_id'), 'memory_access_logs', ['memory_id'], unique=False)
    op.create_index(op.f('ix_memory_access_logs_conversation_id'), 'memory_access_logs', ['conversation_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_memory_access_logs_conversation_id'), table_name='memory_access_logs')
    op.drop_index(op.f('ix_memory_access_logs_memory_id'), table_name='memory_access_logs')
    op.drop_table('memory_access_logs')
    op.drop_table('memory_states')

