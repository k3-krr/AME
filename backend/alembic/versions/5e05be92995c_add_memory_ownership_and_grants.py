"""add_memory_ownership_and_grants

Revision ID: 5e05be92995c
Revises: b891d5b0d688
Create Date: 2026-08-08 19:52:16.389264

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5e05be92995c'
down_revision: Union[str, Sequence[str], None] = 'b891d5b0d688'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Add agent_id to memories table
    op.add_column('memories', sa.Column('agent_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_memories_agent_id_agents',
        'memories',
        'agents',
        ['agent_id'],
        ['id'],
        ondelete='SET NULL'
    )
    op.create_index(op.f('ix_memories_agent_id'), 'memories', ['agent_id'], unique=False)

    # 2. Create memory_access_grants table
    op.create_table(
        'memory_access_grants',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('memory_id', sa.Uuid(), nullable=False),
        sa.Column('agent_id', sa.Uuid(), nullable=False),
        sa.Column('access_level', sa.String(length=20), nullable=False),
        sa.Column('granted_by_principal_type', sa.String(length=20), nullable=False),
        sa.Column('granted_by_user_id', sa.Uuid(), nullable=True),
        sa.Column('granted_by_agent_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ['memory_id'],
            ['memories.id'],
            name='fk_memory_access_grants_memory_id_memories',
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['agent_id'],
            ['agents.id'],
            name='fk_memory_access_grants_agent_id_agents',
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['granted_by_user_id'],
            ['users.id'],
            name='fk_memory_access_grants_granted_by_user_id_users',
            ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(
            ['granted_by_agent_id'],
            ['agents.id'],
            name='fk_memory_access_grants_granted_by_agent_id_agents',
            ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('memory_id', 'agent_id', name='uq_memory_access_grants_mem_agent')
    )
    op.create_index(op.f('ix_memory_access_grants_memory_id'), 'memory_access_grants', ['memory_id'], unique=False)
    op.create_index(op.f('ix_memory_access_grants_agent_id'), 'memory_access_grants', ['agent_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Drop memory_access_grants table
    op.drop_index(op.f('ix_memory_access_grants_agent_id'), table_name='memory_access_grants')
    op.drop_index(op.f('ix_memory_access_grants_memory_id'), table_name='memory_access_grants')
    op.drop_table('memory_access_grants')

    # 2. Remove agent_id index, constraint, and column from memories table
    op.drop_index(op.f('ix_memories_agent_id'), table_name='memories')
    op.drop_constraint('fk_memories_agent_id_agents', 'memories', type_='foreignkey')
    op.drop_column('memories', 'agent_id')
