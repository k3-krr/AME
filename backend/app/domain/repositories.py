import abc
import uuid
from datetime import datetime
from typing import AsyncGenerator, Optional, Protocol

from app.infrastructure.db.models import UserTable, ConversationTable, MessageTable, AuthSessionTable
from app.domain.entities import Memory, MemoryType, MemoryStatus


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

