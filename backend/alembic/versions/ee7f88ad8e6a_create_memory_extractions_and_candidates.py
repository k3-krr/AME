"""create_memory_extractions_and_candidates

Revision ID: ee7f88ad8e6a
Revises: 72ef9b28e58b
Create Date: 2026-07-12 00:39:51.086530

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ee7f88ad8e6a'
down_revision: Union[str, Sequence[str], None] = '72ef9b28e58b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create memory_extractions table
    op.create_table('memory_extractions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('conversation_id', sa.Uuid(), nullable=False),
    sa.Column('message_id', sa.Uuid(), nullable=True),
    sa.Column('extracted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_memory_extractions_conversation_id'), 'memory_extractions', ['conversation_id'], unique=False)
    op.create_index(op.f('ix_memory_extractions_message_id'), 'memory_extractions', ['message_id'], unique=False)

    # Create memory_extraction_candidates table
    op.create_table('memory_extraction_candidates',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('extraction_id', sa.Uuid(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('memory_type', sa.String(length=50), nullable=False),
    sa.Column('importance_score', sa.Float(), nullable=False),
    sa.Column('confidence_score', sa.Float(), nullable=False),
    sa.Column('action_taken', sa.String(length=30), nullable=False),
    sa.Column('target_memory_id', sa.Uuid(), nullable=True),
    sa.ForeignKeyConstraint(['extraction_id'], ['memory_extractions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['target_memory_id'], ['memories.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_memory_extraction_candidates_extraction_id'), 'memory_extraction_candidates', ['extraction_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_memory_extraction_candidates_extraction_id'), table_name='memory_extraction_candidates')
    op.drop_table('memory_extraction_candidates')
    
    op.drop_index(op.f('ix_memory_extractions_message_id'), table_name='memory_extractions')
    op.drop_index(op.f('ix_memory_extractions_conversation_id'), table_name='memory_extractions')
    op.drop_table('memory_extractions')

