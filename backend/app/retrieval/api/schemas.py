import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ContextElementDto(BaseModel):
    memory_id: uuid.UUID
    content: str
    relevance_score: float
    source_tier: str
    provenance_metadata: Dict[str, Any] = Field(default_factory=dict)


class GroundedContextPackageDto(BaseModel):
    request_id: uuid.UUID
    fused_elements: List[ContextElementDto]
    metadata: Dict[str, Any]
    compiled_at: datetime

    class Config:
        from_attributes = True


class RetrievalRequestDto(BaseModel):
    query: str = Field(..., min_length=1, max_length=5000)
    conversation_id: Optional[uuid.UUID] = None
    options: Optional[Dict[str, Any]] = None
