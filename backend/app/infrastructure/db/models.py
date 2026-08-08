import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, DateTime, ForeignKey, func, CheckConstraint, Integer, JSON, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    """Common declarative base schema layer."""
    pass


class UserTable(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # ORM Relationships
    sessions: Mapped[list["AuthSessionTable"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    conversations: Mapped[list["ConversationTable"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class AuthSessionTable(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # ORM Relationships
    user: Mapped["UserTable"] = relationship(back_populates="sessions")


class ConversationTable(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False, default="New Conversation")
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # ORM Relationships
    user: Mapped["UserTable"] = relationship(back_populates="conversations")
    messages: Mapped[list["MessageTable"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class MessageTable(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(
            "sender_role IN ('user', 'assistant', 'system')", 
            name="check_sender_role"
        ),
        CheckConstraint(
            "memory_status IN ('pending', 'consolidated', 'ignored')", 
            name="check_memory_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), 
        nullable=False
    )
    sender_role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    memory_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # ORM Relationships
    conversation: Mapped["ConversationTable"] = relationship(back_populates="messages")


class MemoryTable(Base):
    __tablename__ = "memories"
    __table_args__ = (
        CheckConstraint(
            "memory_system IN ('Semantic', 'Episodic', 'Procedural', 'Working')",
            name="check_memory_system",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        index=True, 
        nullable=False
    )
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), 
        index=True, 
        nullable=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    memory_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    importance: Mapped[float] = mapped_column(nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(20), index=True, nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    metadata_dict: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, server_default="{}")
    memory_system: Mapped[str] = mapped_column(
        String(20), nullable=False, default="Semantic", index=True
    )
    occurred_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), 
        index=True, 
        nullable=True
    )

    # ORM Relationships
    user: Mapped["UserTable"] = relationship()
    conversation: Mapped[Optional["ConversationTable"]] = relationship()
    embedding_relation: Mapped[Optional["MemoryEmbeddingTable"]] = relationship(
        back_populates="memory", cascade="all, delete-orphan", uselist=False
    )
    state_relation: Mapped[Optional["MemoryStateTable"]] = relationship(
        back_populates="memory", cascade="all, delete-orphan", uselist=False
    )
    agent: Mapped[Optional["AgentTable"]] = relationship()



class MemoryEmbeddingTable(Base):
    __tablename__ = "memory_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    memory_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memories.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ORM Relationship
    memory: Mapped["MemoryTable"] = relationship(back_populates="embedding_relation")


class MemoryStateTable(Base):
    __tablename__ = "memory_states"

    memory_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True
    )
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retrieval_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reinforcement_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_reinforced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    decay_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    confidence_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    importance_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="user")

    # ORM Relationship
    memory: Mapped["MemoryTable"] = relationship(back_populates="state_relation")


class MemoryAccessLogTable(Base):
    __tablename__ = "memory_access_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    memory_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memories.id", ondelete="CASCADE"), index=True, nullable=False
    )
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    similarity_score: Mapped[float] = mapped_column(nullable=False)
    ranking_score: Mapped[float] = mapped_column(nullable=False)
    retrieval_success: Mapped[bool] = mapped_column(nullable=False, default=True)

    # ORM Relationship
    memory: Mapped["MemoryTable"] = relationship()
    conversation: Mapped[Optional["ConversationTable"]] = relationship()


class MemoryExtractionTable(Base):
    __tablename__ = "memory_extractions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), index=True, nullable=True
    )
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    candidates: Mapped[list["MemoryExtractionCandidateTable"]] = relationship(
        back_populates="extraction", cascade="all, delete-orphan"
    )


class MemoryExtractionCandidateTable(Base):
    __tablename__ = "memory_extraction_candidates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    extraction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memory_extractions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    memory_type: Mapped[str] = mapped_column(String(50), nullable=False)
    importance_score: Mapped[float] = mapped_column(nullable=False)
    confidence_score: Mapped[float] = mapped_column(nullable=False)
    action_taken: Mapped[str] = mapped_column(String(30), nullable=False)
    target_memory_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("memories.id", ondelete="SET NULL"), nullable=True
    )

    # Relationship
    extraction: Mapped["MemoryExtractionTable"] = relationship(back_populates="candidates")
    memory: Mapped[Optional["MemoryTable"]] = relationship()


class AgentTable(Base):
    __tablename__ = "agents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'SUSPENDED', 'REVOKED')",
            name="check_agent_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    
    # Phase 1 compatibility ownership boundary: tenant_id is represented by the 
    # authenticated user's ID because AME does not yet have a first-class Tenant entity.
    # This design is a compatibility mapping rather than implying User == Tenant conceptually.
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), index=True, nullable=False, default="ACTIVE")
    configuration: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ORM Relationship
    tenant: Mapped["UserTable"] = relationship()
    credentials: Mapped[List["AgentCredentialTable"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )


class AgentCredentialTable(Base):
    __tablename__ = "agent_credentials"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    credential_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # ORM Relationship
    agent: Mapped["AgentTable"] = relationship(back_populates="credentials")


class MemoryAccessGrantTable(Base):
    __tablename__ = "memory_access_grants"
    __table_args__ = (
        UniqueConstraint("memory_id", "agent_id", name="uq_memory_access_grants_mem_agent"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    memory_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memories.id", ondelete="CASCADE"), index=True, nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    access_level: Mapped[str] = mapped_column(String(20), nullable=False)
    granted_by_principal_type: Mapped[str] = mapped_column(String(20), nullable=False)
    granted_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    granted_by_agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # ORM Relationships
    memory: Mapped["MemoryTable"] = relationship(foreign_keys=[memory_id])
    agent: Mapped["AgentTable"] = relationship(foreign_keys=[agent_id])


# Register Knowledge Graph Bounded Context models
from app.knowledge_graph.models.models import NodeTable, RelationshipTable, MemoryNodeMappingTable





