import abc
import uuid
from datetime import datetime
from typing import AsyncGenerator, Optional, Protocol, List


from app.infrastructure.db.models import UserTable, ConversationTable, MessageTable, AuthSessionTable
from app.domain.entities import (
    Memory,
    MemoryType,
    MemoryStatus,
    MemoryState,
    MemorySourceType,
    MemoryExtraction,
    MemoryExtractionCandidate,
    ExtractionStatus,
    ExtractionAction,
    Agent,
    AgentStatus,
    AgentCredential,
    MemoryAccessGrant,
    MemoryAccessLevel,
)
from app.domain.memory_system import MemorySystem
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

    async def get_by_ids(self, memory_ids: List[uuid.UUID]) -> List[Memory]:
        """Fetch memories in batch with default parallel lookup to keep mock compatibility."""
        import asyncio
        tasks = [self.get_by_id(mid) for mid in memory_ids]
        results = await asyncio.gather(*tasks)
        return [m for m in results if m is not None]


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
        memory_system: MemorySystem = MemorySystem.SEMANTIC,
        occurred_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        agent_id: Optional[uuid.UUID] = None,
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
        memory_system: Optional[MemorySystem] = None,
        occurred_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
    ) -> Memory:
        raise NotImplementedError()

    @abc.abstractmethod
    async def list_by_user(
        self,
        user_id: uuid.UUID,
        memory_type: Optional[MemoryType] = None,
        status: Optional[MemoryStatus] = None,
        memory_system: Optional[MemorySystem] = None,
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
        memory_system: Optional[MemorySystem] = None,
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


class ISemanticMemoryRepository(IMemoryRepository):
    """Domain repository contract for Semantic memory system."""

    @abc.abstractmethod
    async def list_semantic_memories(self, user_id: uuid.UUID, page: int = 1, limit: int = 20) -> list[Memory]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def get_semantic_memories_by_type(self, user_id: uuid.UUID, memory_types: list[MemoryType]) -> list[Memory]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def retrieve_semantic(
        self,
        user_id: uuid.UUID,
        query_embedding: Optional[list[float]] = None,
        limit: int = 20,
    ) -> list[Memory]:
        raise NotImplementedError()


class IEpisodicMemoryRepository(IMemoryRepository):
    """Domain repository contract for Episodic memory system."""

    @abc.abstractmethod
    async def get_timeline(
        self,
        user_id: uuid.UUID,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        limit: int = 20,
    ) -> list[Memory]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def list_by_conversation_episodic(
        self,
        conversation_id: uuid.UUID,
        page: int = 1,
        limit: int = 20,
    ) -> list[Memory]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def retrieve_episodic(
        self,
        user_id: uuid.UUID,
        conversation_id: Optional[uuid.UUID] = None,
        limit: int = 20,
    ) -> list[Memory]:
        raise NotImplementedError()


class IProceduralMemoryRepository(IMemoryRepository):
    """Domain repository contract for Procedural memory system."""

    @abc.abstractmethod
    async def get_procedural_memories(self, user_id: uuid.UUID, page: int = 1, limit: int = 20) -> list[Memory]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def get_frequent_procedures(
        self,
        user_id: uuid.UUID,
        limit: int = 10,
    ) -> list[Memory]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def retrieve_procedural(
        self,
        user_id: uuid.UUID,
        limit: int = 20,
    ) -> list[Memory]:
        raise NotImplementedError()


class IWorkingMemoryRepository(IMemoryRepository):
    """Domain repository contract for Working memory system."""

    @abc.abstractmethod
    async def get_active_working_memories(self, user_id: uuid.UUID) -> list[Memory]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def list_active_session_context(self, conversation_id: uuid.UUID) -> list[Memory]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def retrieve_working(
        self,
        user_id: uuid.UUID,
        conversation_id: Optional[uuid.UUID] = None,
    ) -> list[Memory]:
        raise NotImplementedError()


class IRepositoryFactory(abc.ABC):
    """Domain factory contract responsible for selecting repository by memory system tier."""

    @abc.abstractmethod
    def get(self, memory_system: MemorySystem) -> IMemoryRepository:
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


class IMemoryExtractionRepository(abc.ABC):
    """Domain repository contract managing MemoryExtraction and candidate logs."""

    @abc.abstractmethod
    async def create_extraction(
        self,
        conversation_id: uuid.UUID,
        message_id: Optional[uuid.UUID],
        status: ExtractionStatus,
        error_message: Optional[str] = None
    ) -> MemoryExtraction:
        raise NotImplementedError()

    @abc.abstractmethod
    async def add_candidate(
        self,
        extraction_id: uuid.UUID,
        content: str,
        memory_type: MemoryType,
        importance_score: float,
        confidence_score: float,
        action_taken: ExtractionAction,
        target_memory_id: Optional[uuid.UUID] = None
    ) -> MemoryExtractionCandidate:
        raise NotImplementedError()

    @abc.abstractmethod
    async def get_extraction_with_candidates(
        self, extraction_id: uuid.UUID
    ) -> Optional[tuple[MemoryExtraction, list[MemoryExtractionCandidate]]]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def list_extractions_by_conversation(
        self, conversation_id: uuid.UUID, page: int = 1, limit: int = 20
    ) -> list[MemoryExtraction]:
        raise NotImplementedError()


class IAgentRepository(abc.ABC):
    """Domain repository contract managing Agent records."""

    @abc.abstractmethod
    async def get_by_id(self, agent_id: uuid.UUID) -> Optional[Agent]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def create(
        self,
        tenant_id: uuid.UUID,
        name: str,
        description: Optional[str],
        status: AgentStatus,
        configuration: dict,
    ) -> Agent:
        raise NotImplementedError()

    @abc.abstractmethod
    async def update(
        self,
        agent_id: uuid.UUID,
        name: Optional[str],
        description: Optional[str],
        configuration: Optional[dict],
    ) -> Optional[Agent]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def update_status(
        self,
        agent_id: uuid.UUID,
        status: AgentStatus,
    ) -> Optional[Agent]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def list_by_tenant(self, tenant_id: uuid.UUID) -> List[Agent]:
        raise NotImplementedError()


class IAgentCredentialRepository(abc.ABC):
    """Repository interface for Agent Credentials."""

    @abc.abstractmethod
    async def get_by_id(self, credential_id: uuid.UUID) -> Optional[AgentCredential]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def get_by_hash(self, credential_hash: str) -> Optional[AgentCredential]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def create(
        self,
        agent_id: uuid.UUID,
        credential_hash: str,
        description: Optional[str],
        expires_at: Optional[datetime],
    ) -> AgentCredential:
        raise NotImplementedError()

    @abc.abstractmethod
    async def revoke(self, credential_id: uuid.UUID) -> Optional[AgentCredential]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def list_by_agent(self, agent_id: uuid.UUID) -> List[AgentCredential]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def update_last_used(self, credential_id: uuid.UUID, last_used_at: datetime) -> None:
        raise NotImplementedError()


class IMemoryAccessGrantRepository(abc.ABC):
    """Domain repository contract for memory access grants."""

    @abc.abstractmethod
    async def get_by_memory_and_agent(self, memory_id: uuid.UUID, agent_id: uuid.UUID) -> Optional[MemoryAccessGrant]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def save(self, grant: MemoryAccessGrant) -> MemoryAccessGrant:
        raise NotImplementedError()

    @abc.abstractmethod
    async def list_active_by_memory(self, memory_id: uuid.UUID) -> List[MemoryAccessGrant]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def get_active_grant(self, memory_id: uuid.UUID, agent_id: uuid.UUID) -> Optional[MemoryAccessGrant]:
        raise NotImplementedError()







