import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class MemoryType(str, Enum):
    PREFERENCE = "Preference"
    FACT = "Fact"
    GOAL = "Goal"
    TASK = "Task"
    PROFILE = "Profile"
    RELATIONSHIP = "Relationship"
    SKILL = "Skill"
    CUSTOM = "Custom"


class MemoryStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"


def normalize_memory_content(content: str) -> str:
    """
    Standard memory normalization logic:
    - trim whitespace
    - collapse repeated whitespace (spaces, tabs, newlines)
    - convert to lowercase
    """
    if not content:
        return ""
    # Trim leading/trailing whitespace and convert to lowercase
    cleaned = content.strip().lower()
    # Collapse multiple consecutive whitespace characters to a single space
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


@dataclass
class Memory:
    id: uuid.UUID
    user_id: uuid.UUID
    content: str
    memory_type: MemoryType
    importance: float
    confidence: float
    status: MemoryStatus
    created_at: datetime
    updated_at: datetime
    last_accessed_at: datetime
    conversation_id: Optional[uuid.UUID] = None
    version: int = 1
    metadata: dict = field(default_factory=dict)

    def validate(self) -> None:
        """
        Validates the entity instance against business rules:
        - 0.0 <= importance <= 1.0
        - 0.0 <= confidence <= 1.0
        - Reject empty content after normalization
        """
        if not (0.0 <= self.importance <= 1.0):
            raise ValueError("importance must be between 0.0 and 1.0 inclusive")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0 inclusive")
        
        normalized = normalize_memory_content(self.content)
        if not normalized:
            raise ValueError("Memory content cannot be empty")
