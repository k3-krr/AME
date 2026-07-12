"""create_knowledge_graph_tables

Revision ID: f12a3b4c5d6e
Revises: a3f8c1d2e4b5
Create Date: 2026-07-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f12a3b4c5d6e'
down_revision: Union[str, Sequence[str], None] = 'a3f8c1d2e4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Create kg_nodes table
    op.create_table(
        'kg_nodes',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('node_type', sa.String(length=50), nullable=False, server_default='ENTITY'),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('canonical_name', sa.String(length=255), nullable=False),
        sa.Column('entity_type', sa.String(length=100), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'canonical_name', name='uq_kg_nodes_user_canonical_name')
    )
    op.create_index(op.f('ix_kg_nodes_user_id'), 'kg_nodes', ['user_id'], unique=False)
    op.create_index('idx_kg_nodes_user_entity_type', 'kg_nodes', ['user_id', 'entity_type'], unique=False)

    # 2. Create kg_relationships table
    op.create_table(
        'kg_relationships',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('source_node_id', sa.Uuid(), nullable=False),
        sa.Column('target_node_id', sa.Uuid(), nullable=False),
        sa.Column('relationship_type', sa.String(length=100), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_node_id'], ['kg_nodes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_node_id'], ['kg_nodes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'user_id', 'source_node_id', 'target_node_id', 'relationship_type',
            name='uq_kg_relationships_user_source_target_type'
        )
    )
    op.create_index(op.f('ix_kg_relationships_user_id'), 'kg_relationships', ['user_id'], unique=False)
    op.create_index(op.f('ix_kg_relationships_source_node_id'), 'kg_relationships', ['source_node_id'], unique=False)
    op.create_index(op.f('ix_kg_relationships_target_node_id'), 'kg_relationships', ['target_node_id'], unique=False)
    op.create_index(op.f('ix_kg_relationships_relationship_type'), 'kg_relationships', ['relationship_type'], unique=False)

    # 3. Create kg_memory_node_mappings table
    op.create_table(
        'kg_memory_node_mappings',
        sa.Column('memory_id', sa.Uuid(), nullable=False),
        sa.Column('node_id', sa.Uuid(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['memory_id'], ['memories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['node_id'], ['kg_nodes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('memory_id', 'node_id')
    )
    op.create_index(op.f('ix_kg_memory_node_mappings_memory_id'), 'kg_memory_node_mappings', ['memory_id'], unique=False)
    op.create_index(op.f('ix_kg_memory_node_mappings_node_id'), 'kg_memory_node_mappings', ['node_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_kg_memory_node_mappings_node_id'), table_name='kg_memory_node_mappings')
    op.drop_index(op.f('ix_kg_memory_node_mappings_memory_id'), table_name='kg_memory_node_mappings')
    op.drop_table('kg_memory_node_mappings')

    op.drop_index(op.f('ix_kg_relationships_relationship_type'), table_name='kg_relationships')
    op.drop_index(op.f('ix_kg_relationships_target_node_id'), table_name='kg_relationships')
    op.drop_index(op.f('ix_kg_relationships_source_node_id'), table_name='kg_relationships')
    op.drop_index(op.f('ix_kg_relationships_user_id'), table_name='kg_relationships')
    op.drop_table('kg_relationships')

    op.drop_index('idx_kg_nodes_user_entity_type', table_name='kg_nodes')
    op.drop_index(op.f('ix_kg_nodes_user_id'), table_name='kg_nodes')
    op.drop_table('kg_nodes')
