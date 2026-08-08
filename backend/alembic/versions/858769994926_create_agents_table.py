"""create_agents_table

Revision ID: 858769994926
Revises: f12a3b4c5d6e
Create Date: 2026-08-08 19:19:20.260056

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '858769994926'
down_revision: Union[str, Sequence[str], None] = 'f12a3b4c5d6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create agents table
    # Compatibility ownership boundary: tenant_id references users.id for Phase 1
    # compatibility, but represents the tenant boundary conceptually.
    op.create_table(
        'agents',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='ACTIVE', nullable=False),
        sa.Column('configuration', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['users.id'], ondelete='CASCADE', name='fk_agents_tenant_id_users'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("status IN ('ACTIVE', 'SUSPENDED', 'REVOKED')", name='check_agent_status')
    )
    op.create_index(op.f('ix_agents_tenant_id'), 'agents', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_agents_status'), 'agents', ['status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_agents_status'), table_name='agents')
    op.drop_index(op.f('ix_agents_tenant_id'), table_name='agents')
    op.drop_table('agents')

