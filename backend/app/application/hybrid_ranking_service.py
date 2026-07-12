"""Hybrid Memory-Aware Ranking Service (Milestone 7 Phase 5)."""

import uuid
from typing import List, Tuple, Dict, Optional
from app.domain.entities import Memory, MemoryState, MemoryStatus
from app.domain.memory_system import MemorySystem
from app.application.ranking_service import RankingService
from app.config import settings


class HybridRankingService:
    """
    Service responsible for applying memory-system-aware weightings to retrieved memories,
    combining system-tier parameters with the adaptive scores produced by the base RankingService.
    """

    def __init__(
        self,
        adaptive_ranking_service: RankingService,
        # System-tier weights
        semantic_system_weight: Optional[float] = None,
        episodic_system_weight: Optional[float] = None,
        procedural_system_weight: Optional[float] = None,
        working_system_weight: Optional[float] = None,
        # Inner-attribute weights
        semantic_similarity_weight: Optional[float] = None,
        semantic_importance_weight: Optional[float] = None,
        semantic_frequency_weight: Optional[float] = None,
        episodic_similarity_weight: Optional[float] = None,
        episodic_recency_weight: Optional[float] = None,
        episodic_importance_weight: Optional[float] = None,
        procedural_similarity_weight: Optional[float] = None,
        procedural_frequency_weight: Optional[float] = None,
        procedural_success_weight: Optional[float] = None,
        working_priority_weight: Optional[float] = None,
        working_recency_weight: Optional[float] = None,
        working_active_weight: Optional[float] = None,
        # Combine factors
        w_hybrid_adaptive: Optional[float] = None,
        w_hybrid_system: Optional[float] = None,
    ):
        self.adaptive_ranking_service = adaptive_ranking_service

        # Load weights from inputs or configuration/settings defaults
        self.semantic_system_weight = (
            semantic_system_weight if semantic_system_weight is not None 
            else getattr(settings, "SEMANTIC_MEMORY_WEIGHT", settings.SEMANTIC_WEIGHT)
        )
        self.episodic_system_weight = (
            episodic_system_weight if episodic_system_weight is not None 
            else getattr(settings, "EPISODIC_MEMORY_WEIGHT", settings.EPISODIC_WEIGHT)
        )
        self.procedural_system_weight = (
            procedural_system_weight if procedural_system_weight is not None 
            else getattr(settings, "PROCEDURAL_MEMORY_WEIGHT", settings.PROCEDURAL_WEIGHT)
        )
        self.working_system_weight = (
            working_system_weight if working_system_weight is not None 
            else getattr(settings, "WORKING_MEMORY_WEIGHT", settings.WORKING_WEIGHT)
        )

        self.semantic_similarity_weight = (
            semantic_similarity_weight if semantic_similarity_weight is not None else settings.SEMANTIC_SIMILARITY_WEIGHT
        )
        self.semantic_importance_weight = (
            semantic_importance_weight if semantic_importance_weight is not None else settings.SEMANTIC_IMPORTANCE_WEIGHT
        )
        self.semantic_frequency_weight = (
            semantic_frequency_weight if semantic_frequency_weight is not None else settings.SEMANTIC_FREQUENCY_WEIGHT
        )

        self.episodic_similarity_weight = (
            episodic_similarity_weight if episodic_similarity_weight is not None else settings.EPISODIC_SIMILARITY_WEIGHT
        )
        self.episodic_recency_weight = (
            episodic_recency_weight if episodic_recency_weight is not None else settings.EPISODIC_RECENCY_WEIGHT
        )
        self.episodic_importance_weight = (
            episodic_importance_weight if episodic_importance_weight is not None else settings.EPISODIC_IMPORTANCE_WEIGHT
        )

        self.procedural_similarity_weight = (
            procedural_similarity_weight if procedural_similarity_weight is not None else settings.PROCEDURAL_SIMILARITY_WEIGHT
        )
        self.procedural_frequency_weight = (
            procedural_frequency_weight if procedural_frequency_weight is not None else settings.PROCEDURAL_FREQUENCY_WEIGHT
        )
        self.procedural_success_weight = (
            procedural_success_weight if procedural_success_weight is not None else settings.PROCEDURAL_SUCCESS_WEIGHT
        )

        self.working_priority_weight = (
            working_priority_weight if working_priority_weight is not None else settings.WORKING_PRIORITY_WEIGHT
        )
        self.working_recency_weight = (
            working_recency_weight if working_recency_weight is not None else settings.WORKING_RECENCY_WEIGHT
        )
        self.working_active_weight = (
            working_active_weight if working_active_weight is not None else settings.WORKING_ACTIVE_WEIGHT
        )

        self.w_hybrid_adaptive = (
            w_hybrid_adaptive if w_hybrid_adaptive is not None else settings.W_HYBRID_ADAPTIVE
        )
        self.w_hybrid_system = (
            w_hybrid_system if w_hybrid_system is not None else settings.W_HYBRID_SYSTEM
        )

    def rank_hybrid_memories(
        self,
        memories: List[Memory],
        states: List[MemoryState],
        semantic_scores: Dict[uuid.UUID, float],
    ) -> List[Tuple[Memory, float]]:
        """
        Calculates hybrid scores combining tier-specific factors and baseline adaptive scores.
        Returns a sorted list of (Memory, final_score) tuples descending.
        """
        state_map = {state.memory_id: state for state in states}
        ranked_results: List[Tuple[Memory, float]] = []

        for memory in memories:
            state = state_map.get(memory.id)
            system = memory.memory_system or MemorySystem.SEMANTIC

            # 1. Retrieve subscore inputs
            s_similarity = semantic_scores.get(memory.id, 0.0)
            s_importance = state.importance_score if state else memory.importance
            s_recency = self.adaptive_ranking_service.calculate_recency_score(
                memory.occurred_at or memory.created_at
            )
            s_frequency = (
                self.adaptive_ranking_service.calculate_frequency_score(state.access_count)
                if state
                else 0.0
            )
            s_success = memory.metadata.get("success_score", 1.0)
            s_priority = memory.metadata.get("conversation_priority", 1.0)
            s_active = 1.0 if memory.status == MemoryStatus.ACTIVE else 0.0

            # 2. Compute MemorySystem-specific subscores
            system_score = 0.0

            if system == MemorySystem.SEMANTIC:
                subscore = (
                    self.semantic_similarity_weight * s_similarity
                    + self.semantic_importance_weight * s_importance
                    + self.semantic_frequency_weight * s_frequency
                )
                total_inner = (
                    self.semantic_similarity_weight
                    + self.semantic_importance_weight
                    + self.semantic_frequency_weight
                )
                if total_inner > 0:
                    subscore /= total_inner
                system_score = self.semantic_system_weight * subscore

            elif system == MemorySystem.EPISODIC:
                subscore = (
                    self.episodic_similarity_weight * s_similarity
                    + self.episodic_recency_weight * s_recency
                    + self.episodic_importance_weight * s_importance
                )
                total_inner = (
                    self.episodic_similarity_weight
                    + self.episodic_recency_weight
                    + self.episodic_importance_weight
                )
                if total_inner > 0:
                    subscore /= total_inner
                system_score = self.episodic_system_weight * subscore

            elif system == MemorySystem.PROCEDURAL:
                subscore = (
                    self.procedural_similarity_weight * s_similarity
                    + self.procedural_frequency_weight * s_frequency
                    + self.procedural_success_weight * s_success
                )
                total_inner = (
                    self.procedural_similarity_weight
                    + self.procedural_frequency_weight
                    + self.procedural_success_weight
                )
                if total_inner > 0:
                    subscore /= total_inner
                system_score = self.procedural_system_weight * subscore

            elif system == MemorySystem.WORKING:
                subscore = (
                    self.working_priority_weight * s_priority
                    + self.working_recency_weight * s_recency
                    + self.working_active_weight * s_active
                )
                total_inner = (
                    self.working_priority_weight
                    + self.working_recency_weight
                    + self.working_active_weight
                )
                if total_inner > 0:
                    subscore /= total_inner
                system_score = self.working_system_weight * subscore

            # 3. Fetch baseline adaptive score from Adaptive Ranking Engine
            adaptive_scores_list = self.adaptive_ranking_service.rank_memories(
                memories=[memory],
                states=[state] if state else [],
                semantic_scores=semantic_scores,
            )
            adaptive_score = adaptive_scores_list[0][1] if adaptive_scores_list else 0.0

            # 4. Mix system-aware score and baseline adaptive score
            final_score = (
                self.w_hybrid_adaptive * adaptive_score
                + self.w_hybrid_system * system_score
            )
            ranked_results.append((memory, final_score))

        # 5. Sort descending, using memory ID as tie-breaker for stable ordering
        ranked_results.sort(key=lambda x: (-x[1], str(x[0].id)))
        return ranked_results
