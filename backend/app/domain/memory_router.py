"""Memory Router for Hybrid Memory System classification (Milestone 7 Phase 2)."""

import logging
from typing import Optional
from app.domain.entities import Memory, MemoryType
from app.domain.memory_system import MemorySystem

logger = logging.getLogger("ame_backend.domain.memory_router")


class ClassificationResult:
    """Represents the structured outcome of a MemoryRouter classification."""

    def __init__(self, memory_system: MemorySystem, confidence_score: float, reason: str):
        self.memory_system = memory_system
        self.confidence_score = confidence_score
        self.reason = reason

    def __repr__(self) -> str:
        return (
            f"ClassificationResult(memory_system={self.memory_system.value}, "
            f"confidence_score={self.confidence_score}, reason='{self.reason}')"
        )


class MemoryRouter:
    """
    Cognitive router responsible for classifying a Memory into a hybrid system tier.
    It executes priority-driven rule evaluation strictly on Memory attributes,
    fully decoupled from persistence, SQLAlchemy, HTTP, and search indexes.
    """

    def classify(self, memory: Memory, explicit_system: Optional[MemorySystem] = None) -> ClassificationResult:
        """
        Classifies a Memory domain entity using priority-based rules.
        
        Priority order:
        1. Explicit memory_system (if provided)
        2. Metadata hints (e.g. metadata["memory_system"] or metadata["system_hint"])
        3. Specialized MemoryType -> MemorySystem mapping (Event/Instruction/Habit/Skill/Task)
        4. Keyword heuristics (fallback only for generic types)
        5. Default to Semantic
        """
        # 1. Explicit memory_system
        if explicit_system is not None:
            return ClassificationResult(
                memory_system=explicit_system,
                confidence_score=1.0,
                reason="Tier explicitly provided by caller"
            )

        # 2. Metadata hints
        metadata = memory.metadata or {}
        for hint_key in ["memory_system", "system_hint"]:
            if hint_key in metadata:
                val = metadata[hint_key]
                try:
                    matched_sys = MemorySystem(val)
                    return ClassificationResult(
                        memory_system=matched_sys,
                        confidence_score=1.0,
                        reason=f"Resolved from metadata hint key '{hint_key}': '{val}'"
                    )
                except ValueError:
                    logger.warning(f"Invalid memory system metadata hint value '{val}' for key '{hint_key}'")

        # 3. Specialized MemoryType mapping
        # Event maps to Episodic; Task/Instruction/Skill/Habit map to Procedural
        # We classify these specialized types immediately before running keywords
        specialized_mapping = {
            MemoryType.EVENT: MemorySystem.EPISODIC,
            MemoryType.INSTRUCTION: MemorySystem.PROCEDURAL,
            MemoryType.SKILL: MemorySystem.PROCEDURAL,
            MemoryType.HABIT: MemorySystem.PROCEDURAL,
            MemoryType.TASK: MemorySystem.PROCEDURAL,
        }

        if memory.memory_type in specialized_mapping:
            sys = specialized_mapping[memory.memory_type]
            # Verify constraints for Episodic (needs conversation_id)
            if sys == MemorySystem.EPISODIC and memory.conversation_id is None:
                # If conversation_id is missing, it cannot be Episodic; fall back to keywords/default
                logger.info(f"Specialized Event memory type lacks conversation_id; skipping episodic type mapping")
            else:
                return ClassificationResult(
                    memory_system=sys,
                    confidence_score=0.95 if sys == MemorySystem.EPISODIC else 1.0,
                    reason=f"Resolved from specialized MemoryType mapping: '{memory.memory_type.value}' -> '{sys.value}'"
                )

        # 4. Keyword heuristics (fallback for generic/default types like Fact, Custom, Preference, etc.)
        content_lower = (memory.content or "").lower()

        # Working memory keywords
        working_kws = ["temp", "temporary", "expires", "active conversation", "session", "working memory", "current session"]
        if memory.expires_at is not None or (any(kw in content_lower for kw in working_kws) and memory.conversation_id is not None):
            return ClassificationResult(
                memory_system=MemorySystem.WORKING,
                confidence_score=1.0 if memory.expires_at is not None else 0.9,
                reason="Classified as Working memory based on expires_at or content keywords with active conversation_id"
            )

        # Episodic memory keywords (experiential/temporal)
        episodic_kws = ["visited", "went to", "happened", "yesterday", "last week", "at that time"]
        if any(kw in content_lower for kw in episodic_kws) and memory.conversation_id is not None:
            return ClassificationResult(
                memory_system=MemorySystem.EPISODIC,
                confidence_score=0.8,
                reason="Classified as Episodic memory based on temporal or experiential keywords with active conversation_id"
            )

        # 5. Default to Semantic
        from app.domain.memory_system import MEMORY_TYPE_TO_SYSTEM
        default_sys = MEMORY_TYPE_TO_SYSTEM.get(memory.memory_type.value, MemorySystem.SEMANTIC)
        
        # If the type maps to Procedural by default but lacked specialized mapping (or Episodic lacked conversation_id),
        # we check the constraint. If Episodic lacks conversation_id, default to Semantic.
        if default_sys == MemorySystem.EPISODIC and memory.conversation_id is None:
            default_sys = MemorySystem.SEMANTIC

        return ClassificationResult(
            memory_system=default_sys,
            confidence_score=0.85,
            reason=f"Default fallback mapping for MemoryType '{memory.memory_type.value}' to system '{default_sys.value}'"
        )
