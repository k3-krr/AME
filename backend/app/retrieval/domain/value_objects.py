import uuid
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Dict, Any, List
from app.domain.entities import Memory


class QueryIntent(str, Enum):
    FACT_LOOKUP = "FACT_LOOKUP"
    SUMMARY = "SUMMARY"
    TIMELINE = "TIMELINE"
    RELATIONSHIP = "RELATIONSHIP"
    COMPARISON = "COMPARISON"
    INSTRUCTION = "INSTRUCTION"
    SEARCH = "SEARCH"
    MEMORY_RECALL = "MEMORY_RECALL"
    QUESTION = "QUESTION"
    UNKNOWN = "UNKNOWN"


class RetrievalCapability(str, Enum):
    SEMANTIC_SEARCH = "SEMANTIC_SEARCH"
    EPISODIC_SEARCH = "EPISODIC_SEARCH"
    PROCEDURAL_SEARCH = "PROCEDURAL_SEARCH"
    WORKING_MEMORY = "WORKING_MEMORY"
    KNOWLEDGE_GRAPH = "KNOWLEDGE_GRAPH"


class RetrievalQuerySource(str, Enum):
    REWRITER = "REWRITER"
    EXPANSION = "EXPANSION"
    GENERATOR = "GENERATOR"


class PipelineStatus(str, Enum):
    SUCCESS = "SUCCESS"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ContextFusionElement:
    """Identifies fused, deduplicated memories augmented with retrieval score and provenance."""
    memory_id: uuid.UUID
    content: str
    relevance_score: float
    source_tier: str  # "semantic", "episodic", "procedural", "working", "graph_expansion"
    provenance_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalPlan:
    """Encapsulates resolved query intent, recommended capabilities, confidence, and metadata."""
    intent: QueryIntent
    recommended_capabilities: List[RetrievalCapability]
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QueryAnalysisResult:
    """Immutable representation of finalized query understanding and classification."""
    original_query: str
    normalized_query: str
    retrieval_plan: RetrievalPlan


@dataclass(frozen=True)
class RetrievalQuery:
    """Represents a generated retrieval query candidate with priority and source verification."""
    query: str
    priority: float  # Normalized score (e.g. 0.95 for primary, 0.80 for expansion)
    reason: str
    source: RetrievalQuerySource


@dataclass(frozen=True)
class QueryRewriteResult:
    """Encapsulates the output of the query rewriting and query generation steps."""
    original_query: str
    rewritten_query: str
    retrieval_queries: List[RetrievalQuery]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalResult:
    """Represents a candidate memory retrieved by a capability-specific executor."""
    memory: Memory
    score: float
    source_query: str
    capability: RetrievalCapability
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Citation:
    """Represents a human-readable and machine-verifiable source reference."""
    index: int
    memory_id: uuid.UUID
    source_tier: str
    content: str
    relevance_score: float
    originating_queries: List[str]


@dataclass(frozen=True)
class GroundedPromptPackage:
    """A provider-agnostic, LLM-ready prompt payload containing grounded context."""
    request_id: uuid.UUID
    user_query: str
    system_prompt: str
    formatted_context: str
    citations: List[Citation]
    grounding_metadata: Dict[str, Any] = field(default_factory=dict)
    compiled_at: datetime = field(default_factory=datetime.utcnow)
    status: PipelineStatus = PipelineStatus.SUCCESS
