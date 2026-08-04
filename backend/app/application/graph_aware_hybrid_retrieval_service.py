import uuid
import logging
from typing import List, Optional, Union

from app.config import settings
from app.domain.entities import Memory
from app.domain.memory_system import MemorySystem
from app.domain.repositories import IMemoryRepository
from app.application.hybrid_retrieval_service import HybridRetrievalService
from app.knowledge_graph.services.expansion_service import KnowledgeGraphExpansionService

logger = logging.getLogger("ame_backend.application.graph_aware_hybrid_retrieval_service")


class GraphAwareHybridRetrievalService:
    """
    Orchestration retrieval service that wraps the baseline HybridRetrievalService
    and augments the candidate set by calling KnowledgeGraphExpansionService.
    Composes existing services instead of using subclass inheritance.
    """

    def __init__(
        self,
        base_retrieval_service: HybridRetrievalService,
        expansion_service: KnowledgeGraphExpansionService,
        memory_repo: IMemoryRepository,
    ):
        self.base_retrieval_service = base_retrieval_service
        self.expansion_service = expansion_service
        self.memory_repo = memory_repo

    async def search_hybrid(
        self,
        user_id: uuid.UUID,
        query_embedding: Optional[List[float]] = None,
        systems: Optional[List[MemorySystem]] = None,
        limit_per_system: int = 10,
        conversation_id: Optional[uuid.UUID] = None,
    ) -> List[Memory]:
        """
        Retrieves baseline candidates from hybrid tiers, expands using Knowledge Graph,
        and merges/deduplicates the results.
        """
        # 1. Fetch initial baseline memories from hybrid tiers
        initial_memories = await self.base_retrieval_service.search_hybrid(
            user_id=user_id,
            query_embedding=query_embedding,
            systems=systems,
            limit_per_system=limit_per_system,
            conversation_id=conversation_id,
        )

        # 2. Check if Knowledge Graph expansion is enabled
        if not settings.GRAPH_EXPANSION_ENABLED or not initial_memories:
            return initial_memories

        try:
            # 3. Retrieve lightweight expansion candidates (Memory IDs + Graph Metadata)
            candidates = await self.expansion_service.expand_memories(
                user_id=user_id,
                memories=initial_memories,
            )
            if not candidates:
                return initial_memories

            # Map target_memory_id -> candidate metadata
            candidate_map = {c.memory_id: c for c in candidates}

            # Gather target memory IDs that need database resolution
            target_ids = list(candidate_map.keys())

            # 4. Resolve actual Memory objects in batch to prevent N+1 queries
            resolved_memories = await self.memory_repo.get_by_ids(target_ids)

            # Filter out memories not belonging to the user
            resolved_memories = [m for m in resolved_memories if m.user_id == user_id]

            # 5. Merge and update metadata
            merged_results: List[Memory] = []
            seen_ids = set()

            # Process initial memories first
            for memory in initial_memories:
                seen_ids.add(memory.id)
                # Parse existing retrieval source
                current_source = memory.metadata.get("retrieval_source")
                sources = [current_source] if current_source else []
                
                # Check if this initial memory was also reached via graph expansion
                if memory.id in candidate_map:
                    cand = candidate_map[memory.id]
                    sources.append("graph_expansion")
                    
                    # Record provenance path metadata
                    provenance = memory.metadata.setdefault("graph_provenance", [])
                    provenance.append({
                        "origin_memory_id": str(cand.origin_memory_id),
                        "origin_node_id": str(cand.origin_node_id),
                        "traversal_depth": cand.traversal_depth,
                        "path_length": cand.path_length,
                        "graph_score": round(cand.graph_score, 4),
                        "path": [str(nid) for nid in cand.path],
                    })
                    
                # Update sources list (preserving multiple sources)
                if sources:
                    memory.metadata["retrieval_sources"] = list(sorted(set(sources)))
                merged_results.append(memory)

            # Process newly expanded memories (limit check applied here)
            limit_memories = settings.GRAPH_EXPANSION_MAX_MEMORIES
            added_expanded_count = 0

            for memory in resolved_memories:
                if memory.id not in seen_ids:
                    if added_expanded_count >= limit_memories:
                        break

                    seen_ids.add(memory.id)
                    cand = candidate_map[memory.id]

                    # Attach graph expansion metadata and multiple sources list
                    memory.metadata["retrieval_source"] = "graph_expansion"
                    memory.metadata["retrieval_sources"] = ["graph_expansion"]
                    
                    provenance = memory.metadata.setdefault("graph_provenance", [])
                    provenance.append({
                        "origin_memory_id": str(cand.origin_memory_id),
                        "origin_node_id": str(cand.origin_node_id),
                        "traversal_depth": cand.traversal_depth,
                        "path_length": cand.path_length,
                        "graph_score": round(cand.graph_score, 4),
                        "path": [str(nid) for nid in cand.path],
                    })
                    
                    merged_results.append(memory)
                    added_expanded_count += 1

            return merged_results

        except Exception as e:
            logger.error(f"Error during Knowledge Graph expansion: {e}", exc_info=True)
            # Graceful fallback: return initial retrieved memories
            return initial_memories


HybridRetrievalService.register(GraphAwareHybridRetrievalService)

