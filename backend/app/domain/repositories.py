import abc
import uuid
from datetime import datetime
from typing import AsyncGenerator, Optional, Protocol

from app.infrastructure.db.models import UserTable, ConversationTable, MessageTable, AuthSessionTable
from app.domain.entities import Memory, MemoryType, MemoryStatus, MemoryState, MemorySourceType
from app.domain.embedding import MemoryEmbedding


class IMemoryService(abc.ABC):
    """Domain contract for AME memory management pipelines."""

    @abc.abstractmethod
    async def enrich_context(self, user_id: str, user_query: str) -> list[str]:
        """Queries memory indexes (Wait for v0.2). Returns matching reference facts."""
        raise NotImplementedError()

    @abc.abstractmethod
    async def enqueue_ingest(self, message_id: str) -> None:
        """Sends message to background queue for memory consolidation (Wait for v0.2)"""
        raise NotImplementedError()

    @abc.abstractmethod
    async def reinforce_memories(self, memory_ids: list[uuid.UUID]) -> None:
        """Applies reinforcement loop to retrieved memories."""
        raise NotImplementedError()



class ILLMService(abc.ABC):
    """Domain contract for LLM stream generation adapters."""

    @abc.abstractmethod
    async def generate_stream(
        self, system_prompt: str, prompt_messages: list[dict]
    ) -> AsyncGenerator[str, None]:
        """Abstracts vendor APIs (OpenAI, Anthropic, Ollama)."""
        raise NotImplementedError()


class IUserRepository(abc.ABC):
    """Domain repository contract enforcing User CRUD actions."""

    @abc.abstractmethod
    async def get_by_id(self, user_id: uuid.UUID) -> Optional[UserTable]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def get_by_email(self, email: str) -> Optional[UserTable]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def create(self, email: str, password_hash: str) -> UserTable:
        raise NotImplementedError()


class ISessionRepository(abc.ABC):
    """Domain repository contract managing active session identifiers."""

    @abc.abstractmethod
    async def get_by_token(self, token_hash: str) -> Optional[AuthSessionTable]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def create(
        self, user_id: uuid.UUID, token_hash: str, expires_at: any, ip_address: Optional[str], user_agent: Optional[str]
    ) -> AuthSessionTable:
        raise NotImplementedError()

    @abc.abstractmethod
    async def delete_by_token(self, token_hash: str) -> bool:
        raise NotImplementedError()


class IConversationRepository(abc.ABC):
    """Domain repository contract managing Conversation records."""

    @abc.abstractmethod
    async def get_by_id(self, conversation_id: uuid.UUID) -> Optional[ConversationTable]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def list_by_user(self, user_id: uuid.UUID, page: int, limit: int) -> list[ConversationTable]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def create(self, user_id: uuid.UUID, title: str, system_prompt: Optional[str]) -> ConversationTable:
        raise NotImplementedError()

    @abc.abstractmethod
    async def delete(self, conversation_id: uuid.UUID) -> bool:
        raise NotImplementedError()


class IMessageRepository(abc.ABC):
    """Domain repository contract managing message logs."""

    @abc.abstractmethod
    async def list_by_conversation(
        self, conversation_id: uuid.UUID, limit: int, before_id: Optional[uuid.UUID] = None
    ) -> list[MessageTable]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def create(
        self, conversation_id: uuid.UUID, sender_role: str, content: str, memory_status: str = "pending"
    ) -> MessageTable:
        raise NotImplementedError()


class IMemoryRepository(abc.ABC):
    """Domain repository contract managing Memory records."""

    @abc.abstractmethod
    async def get_by_id(self, memory_id: uuid.UUID) -> Optional[Memory]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def create(
        self,
        user_id: uuid.UUID,
        conversation_id: Optional[uuid.UUID],
        content: str,
        memory_type: MemoryType,
        importance: float,
        confidence: float,
        status: MemoryStatus,
        last_accessed_at: datetime,
        version: int,
        metadata: dict,
    ) -> Memory:
        raise NotImplementedError()


    @abc.abstractmethod
    async def update(
        self,
        memory_id: uuid.UUID,
        content: Optional[str] = None,
        memory_type: Optional[MemoryType] = None,
        importance: Optional[float] = None,
        confidence: Optional[float] = None,
        status: Optional[MemoryStatus] = None,
        last_accessed_at: Optional[any] = None,
        version: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> Memory:
        raise NotImplementedError()

    @abc.abstractmethod
    async def list_by_user(
        self,
        user_id: uuid.UUID,
        memory_type: Optional[MemoryType] = None,
        status: Optional[MemoryStatus] = None,
        page: int = 1,
        limit: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> list[Memory]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def list_by_conversation(
        self,
        conversation_id: uuid.UUID,
        memory_type: Optional[MemoryType] = None,
        status: Optional[MemoryStatus] = None,
        page: int = 1,
        limit: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> list[Memory]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def get_active_by_conversation_and_content(
        self, conversation_id: uuid.UUID, content: str
    ) -> Optional[Memory]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def get_by_ids(self, memory_ids: list[uuid.UUID]) -> list[Memory]:
        """Retrieves memories by their IDs, preserving order where possible."""
        raise NotImplementedError()


class IMemoryEmbeddingRepository(abc.ABC):
    """Domain repository contract managing MemoryEmbedding records."""

    @abc.abstractmethod
    async def save(self, embedding: MemoryEmbedding) -> None:
        """Saves or updates a MemoryEmbedding in the store."""
        raise NotImplementedError()

    @abc.abstractmethod
    async def get_by_memory_id(self, memory_id: uuid.UUID) -> Optional[MemoryEmbedding]:
        """Fetches the embedding linked to a memory."""
        raise NotImplementedError()

    @abc.abstractmethod
    async def delete_by_memory_id(self, memory_id: uuid.UUID) -> None:
        """Deletes the embedding linked to a memory."""
        raise NotImplementedError()

    @abc.abstractmethod
    async def similarity_search(
        self,
        user_id: uuid.UUID,
        query_embedding: list[float],
        top_k: int = 5,
        memory_type: Optional[MemoryType] = None,
    ) -> list[tuple[uuid.UUID, float]]:
        """Performs vector search, returning memory_ids and similarity scores."""
        raise NotImplementedError()

    @abc.abstractmethod
    async def list_memories_missing_embeddings(
        self, user_id: Optional[uuid.UUID] = None, limit: int = 100
    ) -> list[uuid.UUID]:
        """Lists active memory IDs that do not have an embedding."""
        raise NotImplementedError()


class IMemoryStateRepository(abc.ABC):
    """Domain repository contract managing MemoryState records."""

    @abc.abstractmethod
    async def get_by_memory_id(self, memory_id: uuid.UUID) -> Optional[MemoryState]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def get_by_memory_ids(self, memory_ids: list[uuid.UUID]) -> list[MemoryState]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def create(
        self,
        memory_id: uuid.UUID,
        access_count: int,
        retrieval_count: int,
        reinforcement_count: int,
        last_accessed_at: datetime,
        last_reinforced_at: Optional[datetime],
        decay_score: float,
        confidence_score: float,
        importance_score: float,
        source_type: MemorySourceType,
    ) -> MemoryState:
        raise NotImplementedError()

    @abc.abstractmethod
    async def update(
        self,
        memory_id: uuid.UUID,
        access_count: Optional[int] = None,
        retrieval_count: Optional[int] = None,
        reinforcement_count: Optional[int] = None,
        last_accessed_at: Optional[datetime] = None,
        last_reinforced_at: Optional[datetime] = None,
        decay_score: Optional[float] = None,
        confidence_score: Optional[float] = None,
        importance_score: Optional[float] = None,
        source_type: Optional[MemorySourceType] = None,
    ) -> MemoryState:
        raise NotImplementedError()

    @abc.abstractmethod
    async def increment_access_counters(
        self, memory_ids: list[uuid.UUID], is_retrieval: bool = True
    ) -> None:
        """Batch increments access_count and retrieval_count in the database."""
        raise NotImplementedError()

    @abc.abstractmethod
    async def apply_reinforcement(
        self, memory_ids: list[uuid.UUID], reinforcement_step: float = 0.02
    ) -> None:
        """Increments reinforcement_count, resets decay_score, updates last_reinforced_at, and bumps importance_score."""
        raise NotImplementedError()

    @abc.abstractmethod
    async def update_decay_scores(self, decay_rate: float) -> int:
        """Recalculates and updates decay_score for active memory states based on elapsed idle time."""
        raise NotImplementedError()


class IMemoryAccessLogRepository(abc.ABC):
    """Domain repository contract managing MemoryAccessLog records."""

    @abc.abstractmethod
    async def log_access(
        self,
        memory_id: uuid.UUID,
        similarity_score: float,
        ranking_score: float,
        conversation_id: Optional[uuid.UUID] = None,
        retrieval_success: bool = True
    ) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    async def list_logs_by_memory(self, memory_id: uuid.UUID, limit: int = 100) -> list[any]:
        raise NotImplementedError()



