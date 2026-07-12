"""add_memory_system_column

Revision ID: a3f8c1d2e4b5
Revises: ee7f88ad8e6a
Create Date: 2026-07-12 01:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a3f8c1d2e4b5"
down_revision: Union[str, Sequence[str], None] = "ee7f88ad8e6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add hybrid memory system columns and backfill existing records."""
    op.add_column(
        "memories",
        sa.Column("memory_system", sa.String(length=20), nullable=False, server_default="Semantic"),
    )
    op.add_column(
        "memories",
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "memories",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Backfill hybrid tier from existing content type labels
    op.execute("UPDATE memories SET memory_system = 'Episodic' WHERE memory_type = 'Event'")
    op.execute(
        "UPDATE memories SET memory_system = 'Procedural' "
        "WHERE memory_type IN ('Instruction', 'Skill', 'Habit', 'Task')"
    )

    op.create_check_constraint(
        "check_memory_system",
        "memories",
        "memory_system IN ('Semantic', 'Episodic', 'Procedural', 'Working')",
    )
    op.create_index(
        "ix_memories_user_system_status",
        "memories",
        ["user_id", "memory_system", "status"],
        unique=False,
    )
    op.execute(
        "CREATE INDEX ix_memories_expires_at_working ON memories (expires_at) "
        "WHERE memory_system = 'Working' AND status = 'ACTIVE'"
    )


def downgrade() -> None:
    """Remove hybrid memory system columns."""
    op.execute("DROP INDEX IF EXISTS ix_memories_expires_at_working")
    op.drop_index("ix_memories_user_system_status", table_name="memories")
    op.drop_constraint("check_memory_system", "memories", type_="check")
    op.drop_column("memories", "expires_at")
    op.drop_column("memories", "occurred_at")
    op.drop_column("memories", "memory_system")
