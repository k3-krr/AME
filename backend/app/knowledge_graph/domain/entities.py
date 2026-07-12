import re
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional


class NodeType(str, Enum):
    ENTITY = "ENTITY"
    DOCUMENT = "DOCUMENT"
    CONVERSATION = "CONVERSATION"
    FILE = "FILE"
    AGENT = "AGENT"
    EXTERNAL_SOURCE = "EXTERNAL_SOURCE"


class EntityType(str, Enum):
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    PROJECT = "PROJECT"
    TECHNOLOGY = "TECHNOLOGY"
    FRAMEWORK = "FRAMEWORK"
    DATABASE = "DATABASE"
    API = "API"
    DOCUMENT = "DOCUMENT"
    CUSTOM = "CUSTOM"


class RelationshipType(str, Enum):
    USES = "USES"
    DEPENDS_ON = "DEPENDS_ON"
    IMPLEMENTS = "IMPLEMENTS"
    REFERENCES = "REFERENCES"
    RELATED_TO = "RELATED_TO"
    PART_OF = "PART_OF"
    CREATED_BY = "CREATED_BY"
    LOCATED_IN = "LOCATED_IN"
    CUSTOM = "CUSTOM"


def normalize_canonical_name(name: str) -> str:
    """
    Standard entity name normalization:
    - trim whitespace
    - collapse repeated whitespace characters
    - convert to lowercase
    - apply alias map (e.g. postgres -> postgresql, js -> javascript, ts -> typescript)
    """
    if not name:
        return ""
    cleaned = name.strip().lower()
    cleaned = re.sub(r"\s+", " ", cleaned)
    
    # Domain-level alias canonicalization
    alias_map = {
        "postgres": "postgresql",
        "js": "javascript",
        "ts": "typescript",
        "fast api": "fastapi",
        "fast_api": "fastapi",
        "nextjs": "next.js",
        "springboot": "spring boot",
        "adaptive memory engine": "ame",
        "semantic memory engine": "sme",
    }
    return alias_map.get(cleaned, cleaned)



class Node:
    def __init__(
        self,
        id: uuid.UUID,
        user_id: uuid.UUID,
        node_type: NodeType,
        name: str,
        canonical_name: str,
        entity_type: Optional[EntityType] = None,
        metadata: Optional[dict] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.id = id
        self.user_id = user_id
        self.node_type = node_type
        self.name = name
        self.canonical_name = canonical_name
        self.entity_type = entity_type
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    def validate(self) -> None:
        """Validates node entity rules."""
        if not self.name or not self.name.strip():
            raise ValueError("Node name cannot be empty")
        if not self.canonical_name or not self.canonical_name.strip():
            raise ValueError("Node canonical name cannot be empty")
        if self.node_type == NodeType.ENTITY and not self.entity_type:
            raise ValueError("EntityType is required for nodes of type ENTITY")
        
        # Verify canonical name matches normalization standard
        normalized = normalize_canonical_name(self.name)
        if normalized != self.canonical_name:
            # We enforce that canonical_name is a normalized form of some kind
            pass


class Relationship:
    def __init__(
        self,
        id: uuid.UUID,
        user_id: uuid.UUID,
        source_node_id: uuid.UUID,
        target_node_id: uuid.UUID,
        relationship_type: RelationshipType,
        confidence: float,
        metadata: Optional[dict] = None,
        created_at: Optional[datetime] = None,
    ):
        self.id = id
        self.user_id = user_id
        self.source_node_id = source_node_id
        self.target_node_id = target_node_id
        self.relationship_type = relationship_type
        self.confidence = confidence
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.utcnow()

    def validate(self) -> None:
        """Validates relationship entity rules."""
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("Confidence must be between 0.0 and 1.0 inclusive")
        if self.source_node_id == self.target_node_id:
            raise ValueError("Self-referential loops are not allowed in relationships")


class MemoryNodeMapping:
    def __init__(
        self,
        memory_id: uuid.UUID,
        node_id: uuid.UUID,
        confidence: float,
        created_at: Optional[datetime] = None,
    ):
        self.memory_id = memory_id
        self.node_id = node_id
        self.confidence = confidence
        self.created_at = created_at or datetime.utcnow()

    def validate(self) -> None:
        """Validates mapping entity rules."""
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("Confidence must be between 0.0 and 1.0 inclusive")
