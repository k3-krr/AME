import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from app.domain.entities import Memory
from app.retrieval.domain.entities import GroundedContextPackage
from app.retrieval.domain.value_objects import ContextFusionElement, RetrievalResult


class ContextFusionService:
    """Deduplicates and compiles retrieved memories into a GroundedContextPackage with multi-path provenance."""

    def fuse(
        self,
        request_id: uuid.UUID,
        ranked_memories: List[Tuple[Memory, float]],
        retrieval_results: List[RetrievalResult],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GroundedContextPackage:
        # Map memory_id to its retrieval results to build provenance tracking metadata
        result_map: Dict[uuid.UUID, List[RetrievalResult]] = {}
        for res in retrieval_results:
            result_map.setdefault(res.memory.id, []).append(res)
            
        fused_elements: List[ContextFusionElement] = []
        retrieved_memories: List[Memory] = []
        
        for memory, final_score in ranked_memories:
            retrieved_memories.append(memory)
            
            sources = result_map.get(memory.id, [])
            
            # Aggregate all contributing retrieval paths
            retrieval_paths = [
                {
                    "capability": s.capability.value,
                    "source_query": s.source_query,
                    "score": s.score,
                    "metadata": s.metadata,
                }
                for s in sources
            ]
            
            provenance = {
                "retrieval_paths": retrieval_paths,
                "final_score": final_score,
            }
            
            # Select primary source tier from the first source path
            source_tier = sources[0].capability.value if sources else "UNKNOWN"
            
            fused_elements.append(
                ContextFusionElement(
                    memory_id=memory.id,
                    content=memory.content,
                    relevance_score=final_score,
                    source_tier=source_tier,
                    provenance_metadata=provenance,
                )
            )
            
        return GroundedContextPackage(
            request_id=request_id,
            retrieved_memories=retrieved_memories,
            fused_elements=fused_elements,
            metadata=metadata or {},
        )
