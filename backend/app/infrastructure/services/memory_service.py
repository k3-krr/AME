import logging
import uuid
from typing import List

from app.domain.repositories import IMemoryService
from app.application.retrieval_service import RetrievalService

logger = logging.getLogger("ame_backend.memory_service")


class MemoryService(IMemoryService):
    """
    Implementation of IMemoryService leveraging RetrievalService for vector search
    and context enrichment.
    """

    def __init__(self, retrieval_service: RetrievalService):
        self.retrieval_service = retrieval_service
        self.last_retrieved_ids: List[uuid.UUID] = []

    async def enrich_context(self, user_id: uuid.UUID, user_query: str) -> List[str]:
        """
        Enriches LLM context by semantically retrieving memories matching the user query.
        """
        try:
            matches = await self.retrieval_service.retrieve_relevant_memories(
                user_id=user_id,
                query=user_query,
                top_k=5,
            )
            # Store the retrieved memory IDs for later reinforcement on successful delivery
            self.last_retrieved_ids = [memory.id for memory, _score in matches]

            logger.info(
                f"Memory enrichment requested for user {user_id} and query: '{user_query}' "
                f"- Retrieved {len(matches)} facts."
            )
            # Return list of memory text content strings
            return [memory.content for memory, _score in matches]
        except Exception as e:
            logger.error(f"Error enriching context: {e}", exc_info=True)
            self.last_retrieved_ids = []
            return []

    async def enqueue_ingest(self, message_id: uuid.UUID) -> None:
        """
        Placeholder async ingestion hook. In v0.2/v0.3, this will send the message 
        to an ingestion queue. For now, logs the action.
        """
        logger.info(f"Message {message_id} enqueued for background memory consolidation.")
        return

    async def reinforce_memories(self, memory_ids: List[uuid.UUID]) -> None:
        """
        Applies reinforcement to the specified memories by delegating to the memory state repository.
        """
        if not memory_ids:
            return
        try:
            await self.retrieval_service.memory_state_repo.apply_reinforcement(memory_ids)
            logger.info(f"Reinforced memory states: {memory_ids}")
        except Exception as e:
            logger.error(f"Error reinforcing memories {memory_ids}: {e}", exc_info=True)

