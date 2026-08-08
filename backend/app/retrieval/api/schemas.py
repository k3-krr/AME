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
    status: str = "SUCCESS"

    class Config:
        from_attributes = True


class RetrievalRequestDto(BaseModel):
    query: str = Field(..., min_length=1, max_length=5000)
    conversation_id: Optional[uuid.UUID] = None
    options: Optional[Dict[str, Any]] = None


class RetrievalPlanDto(BaseModel):
    intent: str
    recommended_capabilities: List[str]
    confidence: float
    metadata: Dict[str, Any]


class QueryAnalysisResultDto(BaseModel):
    original_query: str
    normalized_query: str
    retrieval_plan: RetrievalPlanDto


class RetrievalQueryDto(BaseModel):
    query: str
    priority: float
    reason: str
    source: str


class QueryRewriteResultDto(BaseModel):
    original_query: str
    rewritten_query: str
    retrieval_queries: List[RetrievalQueryDto]
    metadata: Dict[str, Any]


class CitationDto(BaseModel):
    index: int
    memory_id: uuid.UUID
    source_tier: str
    content: str
    relevance_score: float
    originating_queries: List[str]

    class Config:
        from_attributes = True


class GroundedPromptPackageDto(BaseModel):
    request_id: uuid.UUID
    user_query: str
    system_prompt: str
    formatted_context: str
    citations: List[CitationDto]
    grounding_metadata: Dict[str, Any]
    compiled_at: datetime
    status: str = "SUCCESS"

    class Config:
        from_attributes = True
