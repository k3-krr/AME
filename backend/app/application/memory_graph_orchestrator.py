import uuid
import logging
from typing import Optional, Any

from app.application.memory_extraction_service import MemoryExtractionService

logger = logging.getLogger("ame_backend.memory_graph_orchestrator")


class MemoryGraphOrchestrator:
    """
    Orchestration layer coordinating memory extraction (Memory context)
    and entity extraction (Knowledge Graph context) to keep them decoupled.
    Exposes the same interface as MemoryExtractionService for seamless integration.
    """

    def __init__(
        self,
        memory_extraction_service: MemoryExtractionService,
        entity_extraction_service: Any,  # EntityExtractionService
        memory_repo: Any,  # IMemoryRepository
        extraction_repo: Any,  # IMemoryExtractionRepository
    ):
        self.memory_extraction_service = memory_extraction_service
        self.entity_extraction_service = entity_extraction_service
        self.memory_repo = memory_repo
        self.extraction_repo = extraction_repo

    async def extract_memories_from_turns(
        self, conversation_id: uuid.UUID, message_id: Optional[uuid.UUID] = None
    ) -> uuid.UUID:
        """
        Orchestrates the consolidated pipeline:
        1. Invokes the underlying memory extraction pipeline to generate/reinforce memories.
        2. Retrieves the generated memory candidates from the audit trail.
        3. Invokes the entity extraction service to extract concepts and map them to the memories.
        """
        # 1. Run core dialogue memory extraction
        extraction_id = await self.memory_extraction_service.extract_memories_from_turns(
            conversation_id=conversation_id, message_id=message_id
        )

        # 2. Extract and map entities for any consolidated memories in the background/sync path
        try:
            result = await self.extraction_repo.get_extraction_with_candidates(extraction_id)
            if result:
                _, candidates = result
                for candidate in candidates:
                    resolved_id = candidate.target_memory_id
                    if resolved_id:
                        memory = await self.memory_repo.get_by_id(resolved_id)
                        if memory:
                            await self.entity_extraction_service.extract_and_map_entities(
                                user_id=memory.user_id,
                                memory_id=memory.id,
                                content=memory.content,
                            )
        except Exception as e:
            logger.error(
                f"Failed to run entity extraction orchestration for extraction {extraction_id}: {e}",
                exc_info=True,
            )

        return extraction_id
