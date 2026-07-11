import logging
import uuid
from typing import List, Optional, Tuple

from app.domain.entities import Memory, MemoryType
from app.domain.embedding import IEmbeddingProvider
from app.domain.repositories import IMemoryRepository, IMemoryEmbeddingRepository, IMemoryStateRepository
from app.application.ranking_service import RankingService
from app.application.analytics_service import AnalyticsService

logger = logging.getLogger("ame_backend.application.retrieval_service")


class RetrievalService:
    """
    Application service managing semantic memory retrieval and context enrichment.
    Coordinates between the Memory bounded context and the Embedding bounded context,
    handing candidates to RankingService and tracking outcomes in AnalyticsService.
    """

    def __init__(
        self,
        memory_repo: IMemoryRepository,
        embedding_repo: IMemoryEmbeddingRepository,
        embedding_provider: IEmbeddingProvider,
        memory_state_repo: IMemoryStateRepository,
        ranking_service: RankingService,
        analytics_service: AnalyticsService,
    ):
        self.memory_repo = memory_repo
        self.embedding_repo = embedding_repo
        self.embedding_provider = embedding_provider
        self.memory_state_repo = memory_state_repo
        self.ranking_service = ranking_service
        self.analytics_service = analytics_service

    async def retrieve_relevant_memories(
        self,
        user_id: uuid.UUID,
        query: str,
        top_k: int = 5,
        memory_type: Optional[MemoryType] = None,
        min_score: float = 0.15,
        conversation_id: Optional[uuid.UUID] = None,
    ) -> List[Tuple[Memory, float]]:
        """
        Retrieves a list of memories matching the query semantically, ranked adaptively.
        
        Steps:
        1. Embed the query string into a vector.
        2. Query the embedding repository for a broader candidate set.
        3. Fetch core memories and their state metadata in parallel.
        4. Apply adaptive weighting to rank memories.
        5. Filter out memories below min_score and limit to top_k.
        6. Record retrieval footprints via AnalyticsService.
        """
        if not query or not query.strip():
            return []

        # 1. Generate embedding for user query
        try:
            query_embedding = await self.embedding_provider.get_embedding(query)
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}", exc_info=True)
            return []

        # 2. Extract broader candidate set (top_k * 4 or at least 15 candidates)
        candidate_k = max(15, top_k * 4)
        try:
            matches = await self.embedding_repo.similarity_search(
                user_id=user_id,
                query_embedding=query_embedding,
                top_k=candidate_k,
                memory_type=memory_type,
            )
        except Exception as e:
            logger.error(f"Failed to query similarity search: {e}", exc_info=True)
            return []

        if not matches:
            return []

        # Map scores
        memory_ids = [m[0] for m in matches]
        scores_map = {m[0]: m[1] for m in matches}

        # 3. Fetch matching core memory entities and state entities
        try:
            memories = await self.memory_repo.get_by_ids(memory_ids)
            states = await self.memory_state_repo.get_by_memory_ids(memory_ids)
        except Exception as e:
            logger.error(f"Failed to fetch memories or states: {e}", exc_info=True)
            return []

        # 4. Perform weighted adaptive ranking
        try:
            ranked_results = self.ranking_service.rank_memories(memories, states, scores_map)
        except Exception as e:
            logger.error(f"Failed during memory ranking calculation: {e}", exc_info=True)
            # Fallback: return unranked memories pairing with raw similarity scores
            fallback_map = {m.id: m for m in memories}
            return [(fallback_map[mid], score) for mid, score in matches if mid in fallback_map][:top_k]

        # 5. Filter threshold & restrict to top_k
        filtered_results = [
            (memory, score) for memory, score in ranked_results
            if score >= min_score
        ]
        results = filtered_results[:top_k]

        # 6. Increment counters & Log access footprints asynchronously via AnalyticsService
        if results:
            log_data = [(m.id, scores_map.get(m.id, 0.0), score) for m, score in results]
            try:
                await self.analytics_service.record_retrievals(log_data, conversation_id)
            except Exception as e:
                logger.error(f"Failed to write analytics records: {e}", exc_info=True)

        return results

