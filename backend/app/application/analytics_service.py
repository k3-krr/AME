import uuid
from typing import Optional, List, Tuple
from app.domain.repositories import IMemoryAccessLogRepository, IMemoryStateRepository

class AnalyticsService:
    """
    Service responsible for access logging, retrieval statistics, and analytics persistence.
    Decoupled from core RetrievalService queries to maintain single responsibility.
    """

    def __init__(
        self,
        access_log_repo: IMemoryAccessLogRepository,
        memory_state_repo: IMemoryStateRepository
    ):
        self.access_log_repo = access_log_repo
        self.memory_state_repo = memory_state_repo

    async def record_retrievals(
        self,
        retrievals: List[Tuple[uuid.UUID, float, float]],  # (memory_id, similarity_score, ranking_score)
        conversation_id: Optional[uuid.UUID] = None
    ) -> None:
        """
        Logs details of memories returned in a retrieval turn and updates access counters in a batch.
        """
        if not retrievals:
            return

        memory_ids = [r[0] for r in retrievals]
        
        # 1. Batch increment access and retrieval counters in database
        try:
            await self.memory_state_repo.increment_access_counters(memory_ids, is_retrieval=True)
        except Exception as e:
            # We don't want analytics failures to block user flows
            import logging
            logging.getLogger("ame_backend.analytics_service").error(
                f"Failed to increment access counters: {e}", exc_info=True
            )

        # 2. Persist granular logs
        for memory_id, similarity, ranking in retrievals:
            try:
                await self.access_log_repo.log_access(
                    memory_id=memory_id,
                    similarity_score=similarity,
                    ranking_score=ranking,
                    conversation_id=conversation_id,
                    retrieval_success=True
                )
            except Exception as e:
                import logging
                logging.getLogger("ame_backend.analytics_service").error(
                    f"Failed to write access log for memory {memory_id}: {e}", exc_info=True
                )
