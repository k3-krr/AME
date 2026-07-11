import abc
import uuid
from typing import List, Tuple, Dict, Any

class IExtractionProvider(abc.ABC):
    """
    Interface for structured LLM extraction.
    Decoupled from specific vendor API details to support future model migrations.
    """

    @abc.abstractmethod
    async def extract_candidates(self, dialogue_turns: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Extracts new memory candidates from dialogue turns.
        Each candidate is returned as a dictionary:
        {
            "content": str,
            "memory_type": str (should match MemoryType enum values),
            "importance": float (0.0 to 1.0),
            "confidence": float (0.0 to 1.0)
        }
        """
        raise NotImplementedError()

    @abc.abstractmethod
    async def evaluate_relationship(
        self, candidate_content: str, existing_memories: List[Tuple[uuid.UUID, str]]
    ) -> Dict[str, Any]:
        """
        Compares a candidate with existing similar memories to resolve duplication/conflicts.
        Returns:
        {
            "relationship": "create" | "reinforce" | "merge" | "conflict_update",
            "target_id": Optional[uuid.UUID],
            "merged_content": Optional[str]
        }
        """
        raise NotImplementedError()
