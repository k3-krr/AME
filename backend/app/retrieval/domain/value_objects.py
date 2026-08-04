import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, List

@dataclass(frozen=True)
class ContextFusionElement:
    """Identifies fused, deduplicated memories augmented with retrieval score and provenance."""
    memory_id: uuid.UUID
    content: str
    relevance_score: float
    source_tier: str  # "semantic", "episodic", "procedural", "working", "graph_expansion"
    provenance_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QueryIntent:
    """Captures analyzed query types to govern strategy routing."""
    intent_category: str  # "factual", "relational", "temporal", "procedural"
    confidence_score: float
    detected_keywords: List[str] = field(default_factory=list)
