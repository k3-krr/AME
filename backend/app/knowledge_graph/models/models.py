import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, func, JSON, Float, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.models import Base


class NodeTable(Base):
    __tablename__ = "kg_nodes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    node_type: Mapped[str] = mapped_column(String(50), nullable=False, default="ENTITY")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=True)
    metadata_dict: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ORM Relationship
    user = relationship("UserTable")

    __table_args__ = (
        UniqueConstraint("user_id", "canonical_name", name="uq_kg_nodes_user_canonical_name"),
        Index("idx_kg_nodes_user_entity_type", "user_id", "entity_type"),
    )


class RelationshipTable(Base):
    __tablename__ = "kg_relationships"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kg_nodes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kg_nodes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    relationship_type: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    metadata_dict: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # ORM Relationships
    user = relationship("UserTable")
    source_node = relationship("NodeTable", foreign_keys=[source_node_id])
    target_node = relationship("NodeTable", foreign_keys=[target_node_id])

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "source_node_id",
            "target_node_id",
            "relationship_type",
            name="uq_kg_relationships_user_source_target_type",
        ),
    )


class MemoryNodeMappingTable(Base):
    __tablename__ = "kg_memory_node_mappings"

    memory_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True, index=True, nullable=False
    )
    node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kg_nodes.id", ondelete="CASCADE"), primary_key=True, index=True, nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # ORM Relationships
    memory = relationship("MemoryTable")
    node = relationship("NodeTable")
