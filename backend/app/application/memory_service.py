import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from app.domain.entities import Memory, MemoryStatus, MemoryType, normalize_memory_content
from app.domain.repositories import IConversationRepository, IMemoryRepository, IMemoryEmbeddingRepository, IMemoryStateRepository
from app.domain.embedding import MemoryEmbedding, IEmbeddingProvider

logger = logging.getLogger("ame_backend.application.memory_service")


class MemoryService:
    """
    Application service managing Memory CRUD and validation use cases.
    """

    def __init__(
        self,
        memory_repo: IMemoryRepository,
        conversation_repo: IConversationRepository,
        embedding_repo: IMemoryEmbeddingRepository,
        embedding_provider: IEmbeddingProvider,
        memory_state_repo: IMemoryStateRepository,
    ):
        self.memory_repo = memory_repo
        self.conversation_repo = conversation_repo
        self.embedding_repo = embedding_repo
        self.embedding_provider = embedding_provider
        self.memory_state_repo = memory_state_repo

    async def reinforce_memories(self, memory_ids: List[uuid.UUID]) -> None:
        """
        Applies reinforcement loops to memory states.
        """
        if not memory_ids:
            return
        await self.memory_state_repo.apply_reinforcement(memory_ids)

    async def decay_active_memories(self, decay_rate: float) -> int:
        """
        Recalculates decay score for active memories based on configuration-defined rates.
        """
        return await self.memory_state_repo.update_decay_scores(decay_rate)


    async def create_memory(
        self,
        user_id: uuid.UUID,
        conversation_id: Optional[uuid.UUID],
        content: str,
        memory_type: MemoryType,
        importance: float,
        confidence: float,
        metadata: Optional[dict] = None,
    ) -> Memory:
        """
        Creates and persists a new memory after validating inputs and checking for duplicates.
        """
        # 1. Validation & Normalization
        if not (0.0 <= importance <= 1.0):
            raise ValueError("importance must be between 0.0 and 1.0 inclusive")
        if not (0.0 <= confidence <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0 inclusive")

        normalized_content = normalize_memory_content(content)
        if not normalized_content:
            raise ValueError("Memory content cannot be empty")

        # 2. Conversation Ownership Verification
        if conversation_id:
            conversation = await self.conversation_repo.get_by_id(conversation_id)
            if not conversation:
                raise KeyError("Conversation not found")
            if conversation.user_id != user_id:
                raise PermissionError("User does not own this conversation")

            # 3. Duplicate Detection for ACTIVE memories inside the same conversation
            duplicate = await self.memory_repo.get_active_by_conversation_and_content(
                conversation_id=conversation_id, content=normalized_content
            )
            if duplicate:
                raise ValueError("An active memory with identical content already exists in this conversation")

        # 4. Create and Save Memory
        now = datetime.now(timezone.utc)
        memory = await self.memory_repo.create(
            user_id=user_id,
            conversation_id=conversation_id,
            content=content,  # Save the original layout/content, duplicate check runs on normalized content
            memory_type=memory_type,
            importance=importance,
            confidence=confidence,
            status=MemoryStatus.ACTIVE,
            last_accessed_at=now,
            version=1,
            metadata=metadata or {},
        )
        
        # 5. Generate and save embedding in the Embedding bounded context
        vector = await self.embedding_provider.get_embedding(content)
        embedding_entity = MemoryEmbedding(
            id=uuid.uuid4(),
            memory_id=memory.id,
            embedding=vector,
            provider=self.embedding_provider.provider_name,
            model=self.embedding_provider.model_name,
            dimension=self.embedding_provider.dimension,
            created_at=now,
            updated_at=now,
        )
        await self.embedding_repo.save(embedding_entity)

        logger.info(f"Memory successfully created: {memory.id} for user: {user_id}")
        return memory

    async def get_memory(self, user_id: uuid.UUID, memory_id: uuid.UUID) -> Memory:
        """
        Retrieves a single memory and validates user ownership.
        """
        memory = await self.memory_repo.get_by_id(memory_id)
        if not memory:
            raise KeyError("Memory not found")
        if memory.user_id != user_id:
            raise PermissionError("User does not own this memory")
        return memory

    async def update_memory(
        self,
        user_id: uuid.UUID,
        memory_id: uuid.UUID,
        content: Optional[str] = None,
        memory_type: Optional[MemoryType] = None,
        importance: Optional[float] = None,
        confidence: Optional[float] = None,
        status: Optional[MemoryStatus] = None,
        metadata: Optional[dict] = None,
    ) -> Memory:
        """
        Updates an existing memory after verifying ownership and validating the changes.
        """
        # Fetch current record and check ownership
        memory = await self.get_memory(user_id, memory_id)

        # Build proposed updates and validate bounds
        new_importance = importance if importance is not None else memory.importance
        new_confidence = confidence if confidence is not None else memory.confidence
        new_content = content if content is not None else memory.content
        new_status = status if status is not None else memory.status

        if not (0.0 <= new_importance <= 1.0):
            raise ValueError("importance must be between 0.0 and 1.0 inclusive")
        if not (0.0 <= new_confidence <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0 inclusive")

        normalized_content = normalize_memory_content(new_content)
        if not normalized_content:
            raise ValueError("Memory content cannot be empty")

        # Duplicate check: if the memory is active (or transitioning to active) inside a conversation,
        # and either content or status is changing, make sure we don't create a duplicate active memory.
        if memory.conversation_id and new_status == MemoryStatus.ACTIVE:
            content_changed = content is not None and normalized_content != normalize_memory_content(memory.content)
            status_changed = status is not None and memory.status != MemoryStatus.ACTIVE
            
            if content_changed or status_changed:
                duplicate = await self.memory_repo.get_active_by_conversation_and_content(
                    conversation_id=memory.conversation_id, content=normalized_content
                )
                if duplicate and duplicate.id != memory.id:
                    raise ValueError("An active memory with identical content already exists in this conversation")

        # Perform update
        now = datetime.now(timezone.utc)
        updated_memory = await self.memory_repo.update(
            memory_id=memory_id,
            content=content,
            memory_type=memory_type,
            importance=importance,
            confidence=confidence,
            status=status,
            last_accessed_at=now,
            version=memory.version + 1,
            metadata=metadata,
        )
        
        # If content changed, regenerate and update embedding
        if content is not None and normalized_content != normalize_memory_content(memory.content):
            vector = await self.embedding_provider.get_embedding(content)
            embedding_entity = MemoryEmbedding(
                id=uuid.uuid4(),
                memory_id=memory_id,
                embedding=vector,
                provider=self.embedding_provider.provider_name,
                model=self.embedding_provider.model_name,
                dimension=self.embedding_provider.dimension,
                created_at=now,
                updated_at=now,
            )
            await self.embedding_repo.save(embedding_entity)

        logger.info(f"Memory successfully updated: {memory_id} (Version: {updated_memory.version})")
        return updated_memory

    async def delete_memory(self, user_id: uuid.UUID, memory_id: uuid.UUID) -> Memory:
        """
        Soft-deletes a memory by updating its status to DELETED.
        """
        # Fetch current record and verify ownership
        await self.get_memory(user_id, memory_id)

        # Apply soft delete
        now = datetime.now(timezone.utc)
        deleted_memory = await self.memory_repo.update(
            memory_id=memory_id,
            status=MemoryStatus.DELETED,
            last_accessed_at=now,
        )
        logger.info(f"Memory soft-deleted: {memory_id}")
        return deleted_memory

    async def list_user_memories(
        self,
        user_id: uuid.UUID,
        memory_type: Optional[MemoryType] = None,
        status: Optional[MemoryStatus] = None,
        page: int = 1,
        limit: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> List[Memory]:
        """
        Lists paginated and sorted memories for the user.
        """
        return await self.memory_repo.list_by_user(
            user_id=user_id,
            memory_type=memory_type,
            status=status,
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    async def list_conversation_memories(
        self,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        memory_type: Optional[MemoryType] = None,
        status: Optional[MemoryStatus] = None,
        page: int = 1,
        limit: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> List[Memory]:
        """
        Lists memories linked to a specific conversation, after verifying conversation user ownership.
        """
        # Verify ownership of conversation
        conversation = await self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise KeyError("Conversation not found")
        if conversation.user_id != user_id:
            raise PermissionError("User does not own this conversation")

        return await self.memory_repo.list_by_conversation(
            conversation_id=conversation_id,
            memory_type=memory_type,
            status=status,
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    async def reindex_user_memories(self, user_id: uuid.UUID) -> int:
        """
        Finds all active memories for the user that are missing embeddings,
        generates embeddings for them, and persists them.
        """
        # Fetch memory IDs missing embeddings
        missing_ids = await self.embedding_repo.list_memories_missing_embeddings(user_id=user_id, limit=200)
        if not missing_ids:
            return 0

        # Retrieve the memories
        memories = await self.memory_repo.get_by_ids(missing_ids)
        if not memories:
            return 0

        now = datetime.now(timezone.utc)
        reindexed_count = 0
        
        # Process them one by one to avoid rate limit or timeout errors
        for memory in memories:
            try:
                vector = await self.embedding_provider.get_embedding(memory.content)
                embedding_entity = MemoryEmbedding(
                    id=uuid.uuid4(),
                    memory_id=memory.id,
                    embedding=vector,
                    provider=self.embedding_provider.provider_name,
                    model=self.embedding_provider.model_name,
                    dimension=self.embedding_provider.dimension,
                    created_at=now,
                    updated_at=now,
                )
                await self.embedding_repo.save(embedding_entity)
                reindexed_count += 1
            except Exception as e:
                logger.error(f"Failed to generate embedding during reindexing for memory {memory.id}: {e}", exc_info=True)
        
        return reindexed_count
