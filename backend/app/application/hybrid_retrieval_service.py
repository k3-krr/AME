"""Hybrid Retrieval Service for merging and deduplicating memories across system tiers (Milestone 7 Phase 4)."""

import logging
import uuid
from typing import List, Optional
from app.domain.entities import Memory
from app.domain.memory_system import MemorySystem
from app.domain.repositories import IRepositoryFactory

logger = logging.getLogger("ame_backend.application.hybrid_retrieval_service")


class HybridRetrievalService:
    """
    Application service managing unified retrieval across multiple hybrid memory repositories.
    It orchestrates queries across Semantic, Episodic, Procedural, and Working tiers,
    merging and deduplicating results deterministically by memory ID.
    """

    def __init__(self, repository_factory: IRepositoryFactory):
        self.repository_factory = repository_factory

    async def search_hybrid(
        self,
        user_id: uuid.UUID,
        query_embedding: Optional[List[float]] = None,
        systems: Optional[List[MemorySystem]] = None,
        limit_per_system: int = 10,
        conversation_id: Optional[uuid.UUID] = None,
    ) -> List[Memory]:
        """
        Orchestrates retrieval across the specified hybrid memory systems.
        
        Steps:
        1. Resolve active target systems (default to all if systems is None or empty).
        2. Query each system-specific repository using its appropriate retrieval method.
        3. Merge and deduplicate results by memory ID.
        4. Return a unified list of unique Memory entities.
        """
        # Resolve target systems
        target_systems = systems
        if not target_systems:
            target_systems = [
                MemorySystem.SEMANTIC,
                MemorySystem.EPISODIC,
                MemorySystem.PROCEDURAL,
                MemorySystem.WORKING,
            ]

        results: List[Memory] = []
        
        for system in target_systems:
            try:
                repo = self.repository_factory.get(system)
                system_memories: List[Memory] = []
                
                if system == MemorySystem.SEMANTIC:
                    # Semantic repository retrieval (uses existing similarity search if query embedding is provided)
                    system_memories = await repo.retrieve_semantic(
                        user_id=user_id,
                        query_embedding=query_embedding,
                        limit=limit_per_system
                    )
                elif system == MemorySystem.EPISODIC:
                    # Episodic repository chronological retrieval
                    system_memories = await repo.retrieve_episodic(
                        user_id=user_id,
                        conversation_id=conversation_id,
                        limit=limit_per_system
                    )
                elif system == MemorySystem.PROCEDURAL:
                    # Procedural repository frequency workflow retrieval
                    system_memories = await repo.retrieve_procedural(
                        user_id=user_id,
                        limit=limit_per_system
                    )
                elif system == MemorySystem.WORKING:
                    # Working repository active session context retrieval
                    system_memories = await repo.retrieve_working(
                        user_id=user_id,
                        conversation_id=conversation_id
                    )

                results.extend(system_memories)
                
            except Exception as e:
                logger.error(
                    f"Error querying specialized repository for system '{system.value}': {e}",
                    exc_info=True
                )
                # Fail-safe: continue gathering results from other repositories

        # Merge and Deduplicate deterministically by memory ID, preserving ordering
        seen_ids = set()
        deduplicated_results: List[Memory] = []
        for mem in results:
            if mem.id not in seen_ids:
                seen_ids.add(mem.id)
                deduplicated_results.append(mem)

        return deduplicated_results
