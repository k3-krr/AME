import uuid
from typing import Optional
from app.domain.entities import MemoryType, ExtractionAction
from app.domain.repositories import IMemoryRepository, IMemoryStateRepository, IConversationRepository
from app.application.memory_service import MemoryService

class MemoryUpdateService:
    """
    Service responsible for applying updates to memories and states
    based on the extraction decision.
    """

    def __init__(
        self,
        memory_service: MemoryService,
        memory_repo: IMemoryRepository,
        memory_state_repo: IMemoryStateRepository,
        conversation_repo: IConversationRepository
    ):
        self.memory_service = memory_service
        self.memory_repo = memory_repo
        self.memory_state_repo = memory_state_repo
        self.conversation_repo = conversation_repo

    async def apply_action(
        self,
        conversation_id: uuid.UUID,
        content: str,
        memory_type: MemoryType,
        importance: float,
        confidence: float,
        action: ExtractionAction,
        target_memory_id: Optional[uuid.UUID] = None
    ) -> Optional[uuid.UUID]:
        """
        Executes DB changes corresponding to the action.
        Returns the updated/created memory ID.
        """
        # Fetch user_id from conversation
        conversation = await self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise KeyError("Conversation not found")
        user_id = conversation.user_id

        if action == ExtractionAction.CREATE:
            memory = await self.memory_service.create_memory(
                user_id=user_id,
                conversation_id=conversation_id,
                content=content,
                memory_type=memory_type,
                importance=importance,
                confidence=confidence,
                metadata={"extraction_source": "autonomous"}
            )
            return memory.id

        elif action == ExtractionAction.REINFORCE:
            if target_memory_id:
                await self.memory_state_repo.apply_reinforcement([target_memory_id])
                return target_memory_id

        elif action == ExtractionAction.MERGE:
            if target_memory_id:
                # Update core memory content (this regenerates the embedding)
                await self.memory_service.update_memory(
                    user_id=user_id,
                    memory_id=target_memory_id,
                    content=content
                )
                # Apply reinforcement
                await self.memory_state_repo.apply_reinforcement([target_memory_id])
                return target_memory_id

        elif action == ExtractionAction.CONFLICT_UPDATE:
            if target_memory_id:
                # Overwrite core content (regenerating embedding)
                await self.memory_service.update_memory(
                    user_id=user_id,
                    memory_id=target_memory_id,
                    content=content,
                    importance=importance,
                    confidence=confidence
                )
                # Reset stats
                await self.memory_state_repo.update(
                    memory_id=target_memory_id,
                    decay_score=0.0,
                    access_count=0,
                    retrieval_count=0,
                    reinforcement_count=0
                )
                return target_memory_id

        return None
