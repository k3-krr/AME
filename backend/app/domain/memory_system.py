"""
Hybrid memory system classification (Milestone 7).

MemorySystem describes the cognitive storage tier (Semantic, Episodic, Procedural, Working).
MemoryType (in entities.py) remains the fine-grained content label.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.domain.entities import MemoryType


class MemorySystem(str, Enum):
    """Hybrid memory tier classifying how a memory is stored and retrieved."""

    SEMANTIC = "Semantic"
    EPISODIC = "Episodic"
    PROCEDURAL = "Procedural"
    WORKING = "Working"


# Default content-type label → hybrid system mapping (used for migration backfill).
MEMORY_TYPE_TO_SYSTEM: dict[str, MemorySystem] = {
    "Event": MemorySystem.EPISODIC,
    "Instruction": MemorySystem.PROCEDURAL,
    "Skill": MemorySystem.PROCEDURAL,
    "Habit": MemorySystem.PROCEDURAL,
    "Task": MemorySystem.PROCEDURAL,
    "Preference": MemorySystem.SEMANTIC,
    "Fact": MemorySystem.SEMANTIC,
    "Goal": MemorySystem.SEMANTIC,
    "Profile": MemorySystem.SEMANTIC,
    "Relationship": MemorySystem.SEMANTIC,
    "Custom": MemorySystem.SEMANTIC,
    "Education": MemorySystem.SEMANTIC,
    "Work": MemorySystem.SEMANTIC,
    "Project": MemorySystem.SEMANTIC,
    "Correction": MemorySystem.SEMANTIC,
}


def default_memory_system_for_type(memory_type: MemoryType) -> MemorySystem:
    """Returns the default hybrid system for a content type (used in backfill)."""
    return MEMORY_TYPE_TO_SYSTEM.get(memory_type.value, MemorySystem.SEMANTIC)


def validate_memory_system_constraints(
    memory_system: MemorySystem,
    conversation_id: Optional[object],
    occurred_at: Optional[datetime],
    expires_at: Optional[datetime],
) -> None:
    """
    Validates cross-field rules for hybrid memory tiers.

    Raises:
        ValueError: When required fields for a system tier are missing or invalid.
    """
    if memory_system == MemorySystem.EPISODIC:
        if conversation_id is None:
            raise ValueError("Episodic memories require a conversation_id")
    elif memory_system == MemorySystem.WORKING:
        if conversation_id is None:
            raise ValueError("Working memories require a conversation_id")
        if expires_at is None:
            raise ValueError("Working memories require an expires_at timestamp")
    elif memory_system in (MemorySystem.SEMANTIC, MemorySystem.PROCEDURAL):
        # occurred_at and expires_at are optional; no hard conversation requirement
        pass

    if expires_at is not None and memory_system != MemorySystem.WORKING:
        raise ValueError("expires_at is only valid for Working memories")


def compute_working_memory_expiry(ttl_hours: float) -> datetime:
    """Computes a UTC expiry timestamp for a new working memory entry."""
    return datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
