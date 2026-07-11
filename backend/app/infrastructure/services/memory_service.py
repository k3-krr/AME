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
            logger.info(
                f"Memory enrichment requested for user {user_id} and query: '{user_query}' "
                f"- Retrieved {len(matches)} facts."
            )
            # Return list of memory text content strings
            return [memory.content for memory, _score in matches]
        except Exception as e:
            logger.error(f"Error enriching context: {e}", exc_info=True)
            return []

    async def enqueue_ingest(self, message_id: uuid.UUID) -> None:
        """
        Placeholder async ingestion hook. In v0.2/v0.3, this will send the message 
        to an ingestion queue. For now, logs the action.
        """
        logger.info(f"Message {message_id} enqueued for background memory consolidation.")
        return
