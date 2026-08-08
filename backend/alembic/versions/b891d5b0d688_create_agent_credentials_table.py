"""create_agent_credentials_table

Revision ID: b891d5b0d688
Revises: 858769994926
Create Date: 2026-08-08 19:36:49.577367

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b891d5b0d688'
down_revision: Union[str, Sequence[str], None] = '858769994926'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'agent_credentials',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('agent_id', sa.Uuid(), nullable=False),
        sa.Column('credential_hash', sa.String(length=64), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE', name='fk_agent_credentials_agent_id_agents'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('credential_hash', name='uq_agent_credentials_hash')
    )
    op.create_index(op.f('ix_agent_credentials_agent_id'), 'agent_credentials', ['agent_id'], unique=False)
    op.create_index(op.f('ix_agent_credentials_credential_hash'), 'agent_credentials', ['credential_hash'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_agent_credentials_credential_hash'), table_name='agent_credentials')
    op.drop_index(op.f('ix_agent_credentials_agent_id'), table_name='agent_credentials')
    op.drop_table('agent_credentials')

