import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from app.domain.memory_system import MemorySystem, validate_memory_system_constraints


class MemoryType(str, Enum):
    PREFERENCE = "Preference"
    FACT = "Fact"
    GOAL = "Goal"
    TASK = "Task"
    PROFILE = "Profile"
    RELATIONSHIP = "Relationship"
    SKILL = "Skill"
    CUSTOM = "Custom"
    EDUCATION = "Education"
    WORK = "Work"
    PROJECT = "Project"
    HABIT = "Habit"
    EVENT = "Event"
    CORRECTION = "Correction"
    INSTRUCTION = "Instruction"


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
    memory_system: MemorySystem = MemorySystem.SEMANTIC
    occurred_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    agent_id: Optional[uuid.UUID] = None

    def validate(self) -> None:
        """
        Validates the entity instance against business rules:
        - 0.0 <= importance <= 1.0
        - 0.0 <= confidence <= 1.0
        - Reject empty content after normalization
        - Hybrid memory system cross-field constraints
        """
        if not (0.0 <= self.importance <= 1.0):
            raise ValueError("importance must be between 0.0 and 1.0 inclusive")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0 inclusive")

        normalized = normalize_memory_content(self.content)
        if not normalized:
            raise ValueError("Memory content cannot be empty")

        validate_memory_system_constraints(
            memory_system=self.memory_system,
            conversation_id=self.conversation_id,
            occurred_at=self.occurred_at,
            expires_at=self.expires_at,
        )


class MemorySourceType(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    EXTRACTED = "extracted"
    MANUAL = "manual"


@dataclass
class MemoryState:
    memory_id: uuid.UUID
    access_count: int = 0
    retrieval_count: int = 0
    reinforcement_count: int = 0
    last_accessed_at: datetime = field(default_factory=datetime.utcnow)
    last_reinforced_at: Optional[datetime] = None
    decay_score: float = 0.0
    confidence_score: float = 0.0
    importance_score: float = 0.0
    source_type: MemorySourceType = MemorySourceType.USER

    def validate(self) -> None:
        """
        Validates the memory state instance bounds:
        - 0.0 <= importance_score <= 1.0
        - 0.0 <= confidence_score <= 1.0
        - 0.0 <= decay_score <= 1.0
        """
        if not (0.0 <= self.importance_score <= 1.0):
            raise ValueError("importance_score must be between 0.0 and 1.0 inclusive")
        if not (0.0 <= self.confidence_score <= 1.0):
            raise ValueError("confidence_score must be between 0.0 and 1.0 inclusive")
        if not (0.0 <= self.decay_score <= 1.0):
            raise ValueError("decay_score must be between 0.0 and 1.0 inclusive")


class ExtractionStatus(str, Enum):
    SUCCESS = "success"
    IGNORED = "ignored"
    FAILED = "failed"


class ExtractionAction(str, Enum):
    CREATE = "create"
    REINFORCE = "reinforce"
    MERGE = "merge"
    CONFLICT_UPDATE = "conflict_update"
    IGNORE = "ignore"


@dataclass
class MemoryExtraction:
    id: uuid.UUID
    conversation_id: uuid.UUID
    message_id: Optional[uuid.UUID]
    extracted_at: datetime
    status: ExtractionStatus
    error_message: Optional[str] = None


@dataclass
class MemoryExtractionCandidate:
    id: uuid.UUID
    extraction_id: uuid.UUID
    content: str
    memory_type: MemoryType
    importance_score: float
    confidence_score: float
    action_taken: ExtractionAction
    target_memory_id: Optional[uuid.UUID] = None


class AgentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"


@dataclass
class Agent:
    """
    Agent Domain Entity.

    Phase 1 compatibility ownership boundary: tenant_id is represented by the 
    authenticated user's ID because AME does not yet have a first-class Tenant entity.
    This design is a compatibility mapping rather than implying User == Tenant,
    allowing a real Tenant context to be introduced in the future without changing Agent.
    """
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: Optional[str]
    status: AgentStatus
    configuration: dict
    created_at: datetime
    updated_at: datetime

    def validate(self) -> None:
        """Validates Agent domain rules."""
        if not self.name or not self.name.strip():
            raise ValueError("Agent name cannot be empty")
        if not self.tenant_id:
            raise ValueError("tenant_id is required")


@dataclass
class AgentCredential:
    id: uuid.UUID
    agent_id: uuid.UUID
    credential_hash: str
    description: Optional[str]
    created_at: datetime
    expires_at: Optional[datetime]
    revoked_at: Optional[datetime]
    last_used_at: Optional[datetime]

    def is_active(self, current_time: datetime, agent_status: AgentStatus) -> bool:
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None:
            expires_at = self.expires_at
            if expires_at.tzinfo is not None and current_time.tzinfo is None:
                current_time = current_time.replace(tzinfo=expires_at.tzinfo)
            elif expires_at.tzinfo is None and current_time.tzinfo is not None:
                expires_at = expires_at.replace(tzinfo=current_time.tzinfo)
            if expires_at <= current_time:
                return False
        if agent_status != AgentStatus.ACTIVE:
            return False
        return True


class PrincipalType(str, Enum):
    USER = "USER"
    AGENT = "AGENT"


@dataclass
class AgentPrincipal:
    agent_id: uuid.UUID
    tenant_id: uuid.UUID
    principal_type: PrincipalType = PrincipalType.AGENT
    name: str = ""


@dataclass
class UserPrincipal:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    principal_type: PrincipalType = PrincipalType.USER
    email: str = ""


@dataclass
class AccessContext:
    tenant_id: uuid.UUID
    principal_type: PrincipalType
    user_id: Optional[uuid.UUID] = None
    agent_id: Optional[uuid.UUID] = None


class MemoryAccessLevel(str, Enum):
    READ = "READ"
    WRITE = "WRITE"
    MANAGE = "MANAGE"


@dataclass
class MemoryAccessGrant:
    id: uuid.UUID
    memory_id: uuid.UUID
    agent_id: uuid.UUID
    access_level: MemoryAccessLevel
    granted_by_principal_type: PrincipalType
    granted_by_user_id: Optional[uuid.UUID]
    granted_by_agent_id: Optional[uuid.UUID]
    created_at: datetime
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None

    def is_active(self, current_time: datetime) -> bool:
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None:
            expires_at = self.expires_at
            if expires_at.tzinfo is not None and current_time.tzinfo is None:
                current_time = current_time.replace(tzinfo=expires_at.tzinfo)
            elif expires_at.tzinfo is None and current_time.tzinfo is not None:
                expires_at = expires_at.replace(tzinfo=current_time.tzinfo)
            if expires_at <= current_time:
                return False
        return True





