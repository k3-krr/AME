import math
import uuid
from datetime import datetime, timezone
from typing import List, Tuple, Dict
from app.domain.entities import Memory, MemoryState

class RankingService:
    """
    Service responsible for applying adaptive weighted ranking calculation to memory matches.
    It combines semantic similarity with recency, access frequency, confidence, and decay penalties.
    """

    def __init__(
        self,
        w_semantic: float = 0.40,
        w_importance: float = 0.15,
        w_recency: float = 0.15,
        w_frequency: float = 0.10,
        w_decay: float = 0.10,
        w_confidence: float = 0.10,
        recency_half_life_hours: float = 168.0,
        frequency_threshold: int = 50,
    ):
        self.w_semantic = w_semantic
        self.w_importance = w_importance
        self.w_recency = w_recency
        self.w_frequency = w_frequency
        self.w_decay = w_decay
        self.w_confidence = w_confidence
        self.recency_half_life_hours = recency_half_life_hours
        self.frequency_threshold = frequency_threshold

    def calculate_recency_score(self, created_at: datetime) -> float:
        """
        Calculates exponential time recency score in range [0, 1].
        S_recency = exp(-lambda * t_age)
        """
        now = datetime.now(timezone.utc)
        # Handle naive/aware datetime conversion safely
        if created_at.tzinfo is not None:
            created_at_naive = created_at.astimezone(timezone.utc).replace(tzinfo=None)
            now_naive = now.replace(tzinfo=None)
        else:
            created_at_naive = created_at
            now_naive = now.replace(tzinfo=None)

        age_hours = max(0.0, (now_naive - created_at_naive).total_seconds() / 3600.0)
        decay_constant = math.log(2) / self.recency_half_life_hours
        return math.exp(-decay_constant * age_hours)

    def calculate_frequency_score(self, access_count: int) -> float:
        """
        Calculates logarithmic access frequency score in range [0, 1].
        S_frequency = ln(1 + access_count) / ln(1 + threshold)
        """
        if access_count <= 0:
            return 0.0
        return min(1.0, math.log(1 + access_count) / math.log(1 + self.frequency_threshold))

    def rank_memories(
        self,
        memories: List[Memory],
        states: List[MemoryState],
        semantic_scores: Dict[uuid.UUID, float]
    ) -> List[Tuple[Memory, float]]:
        """
        Combines candidates and state mappings using the adaptive scoring algorithm.
        """
        state_map = {state.memory_id: state for state in states}
        ranked_results: List[Tuple[Memory, float]] = []

        for memory in memories:
            state = state_map.get(memory.id)
            semantic_score = semantic_scores.get(memory.id, 0.0)

            # 1. Semantic component
            s_semantic = max(0.0, min(1.0, semantic_score))

            # 2. Recency component
            s_recency = self.calculate_recency_score(memory.created_at)

            # 3. State components
            if state:
                s_importance = state.importance_score
                s_confidence = state.confidence_score
                s_frequency = self.calculate_frequency_score(state.access_count)
                s_decay = state.decay_score
            else:
                # Fallback to core fields if state record is missing
                s_importance = memory.importance
                s_confidence = memory.confidence
                s_frequency = 0.0
                s_decay = 0.0

            # 4. Compute BaseScore
            base_score = (
                self.w_semantic * s_semantic +
                self.w_importance * s_importance +
                self.w_recency * s_recency +
                self.w_frequency * s_frequency +
                self.w_confidence * s_confidence
            )

            # Normalize base_score in case weights don't perfectly sum to 1.0 (excluding decay)
            total_weight = (
                self.w_semantic +
                self.w_importance +
                self.w_recency +
                self.w_frequency +
                self.w_confidence
            )
            if total_weight > 0:
                base_score /= total_weight

            # 5. Apply multiplicative decay penalty
            final_score = base_score * (1.0 - self.w_decay * s_decay)
            ranked_results.append((memory, final_score))

        # Sort descending by final score
        ranked_results.sort(key=lambda x: x[1], reverse=True)
        return ranked_results
