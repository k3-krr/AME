import logging
import uuid
from typing import List

from app.domain.repositories import IMemoryService

logger = logging.getLogger("ame_backend.memory_service")


class MemoryService(IMemoryService):
    """
    Pass-through implementation of IMemoryService.
    Prepares hooks for vector search and background reflection pipelines in v0.2/v0.3.
    """

    async def enrich_context(self, user_id: uuid.UUID, user_query: str) -> List[str]:
        """
        Placeholder context enrichment. In v0.2, this will query pgvector.
        For now, returns an empty list.
        """
        logger.info(f"Memory enrichment requested for user {user_id} and query: '{user_query}' - Retressed 0 facts.")
        return []

    async def enqueue_ingest(self, message_id: uuid.UUID) -> None:
        """
        Placeholder async ingestion hook. In v0.2/v0.3, this will send the message 
        to an ingestion queue. For now, logs the action.
        """
        logger.info(f"Message {message_id} enqueued for background memory consolidation.")
        return
