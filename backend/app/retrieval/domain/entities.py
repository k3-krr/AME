import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from app.domain.entities import Memory
from app.retrieval.domain.value_objects import ContextFusionElement

@dataclass
class RetrievalRequest:
    """In-memory domain model representing the incoming query execution parameters."""
    id: uuid.UUID
    user_id: uuid.UUID
    query: str
    conversation_id: Optional[uuid.UUID] = None
    options: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def validate(self) -> None:
        if not self.query or not self.query.strip():
            raise ValueError("Query string cannot be empty")
        if not self.user_id:
            raise ValueError("User ID is required")


@dataclass
class GroundedContextPackage:
    """Provider-agnostic context package containing retrieved elements and original memories."""
    request_id: uuid.UUID
    retrieved_memories: List[Memory]
    fused_elements: List[ContextFusionElement]
    metadata: Dict[str, Any] = field(default_factory=dict)
    compiled_at: datetime = field(default_factory=datetime.utcnow)
