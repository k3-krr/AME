import logging
import uuid
from typing import List, Optional, Tuple

from app.domain.entities import Memory, MemoryType
from app.domain.embedding import IEmbeddingProvider
from app.domain.repositories import IMemoryRepository, IMemoryEmbeddingRepository

logger = logging.getLogger("ame_backend.application.retrieval_service")


class RetrievalService:
    """
    Application service managing semantic memory retrieval and context enrichment.
    Coordinates between the Memory bounded context and the Embedding bounded context.
    """

    def __init__(
        self,
        memory_repo: IMemoryRepository,
        embedding_repo: IMemoryEmbeddingRepository,
        embedding_provider: IEmbeddingProvider,
    ):
        self.memory_repo = memory_repo
        self.embedding_repo = embedding_repo
        self.embedding_provider = embedding_provider

    async def retrieve_relevant_memories(
        self,
        user_id: uuid.UUID,
        query: str,
        top_k: int = 5,
        memory_type: Optional[MemoryType] = None,
    ) -> List[Tuple[Memory, float]]:
        """
        Retrieves a list of memories matching the query semantically.
        
        Steps:
        1. Embed the query string into a vector.
        2. Query the embedding repository for similar active memory IDs.
        3. Bulk fetch the corresponding memories.
        4. Pair each memory with its similarity score and return them sorted.
        """
        if not query or not query.strip():
            return []

        # 1. Generate embedding for user query
        try:
            query_embedding = await self.embedding_provider.get_embedding(query)
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}", exc_info=True)
            return []

        # 2. Query similarity search for matching memory_ids and similarity scores
        try:
            matches = await self.embedding_repo.similarity_search(
                user_id=user_id,
                query_embedding=query_embedding,
                top_k=top_k,
                memory_type=memory_type,
            )
        except Exception as e:
            logger.error(f"Failed to query similarity search: {e}", exc_info=True)
            return []

        if not matches:
            return []

        # Separate IDs and scores preserving order
        memory_ids = [m[0] for m in matches]
        scores_map = {m[0]: m[1] for m in matches}

        # 3. Bulk fetch matching memory entities
        try:
            memories = await self.memory_repo.get_by_ids(memory_ids)
        except Exception as e:
            logger.error(f"Failed to bulk fetch memories: {e}", exc_info=True)
            return []

        # 4. Map and sort final hydrated results (ensure they are sorted by score descending)
        hydrated_results: List[Tuple[Memory, float]] = []
        for memory in memories:
            if memory.id in scores_map:
                hydrated_results.append((memory, scores_map[memory.id]))

        # Re-sort to guarantee the order matches the similarity search results
        hydrated_results.sort(key=lambda x: x[1], reverse=True)
        return hydrated_results
