import uuid
from typing import List, Optional, Dict, Any
from app.domain.entities import Memory
from app.domain.memory_system import MemorySystem
from app.domain.repositories import IMemoryRepository
from app.domain.embedding import IEmbeddingProvider
from app.application.graph_aware_hybrid_retrieval_service import GraphAwareHybridRetrievalService
from app.knowledge_graph.repositories.sql_repositories import SQLGraphRepository
from app.knowledge_graph.domain.entities import normalize_canonical_name
from app.retrieval.domain.executor import IRetrievalExecutor
from app.retrieval.domain.value_objects import RetrievalCapability, RetrievalQuery, RetrievalResult


class HybridRetrievalExecutor(IRetrievalExecutor):
    """Executes retrieval across episodic, semantic, and procedural memory tiers."""
    
    def __init__(
        self,
        capability: RetrievalCapability,
        hybrid_retrieval_service: GraphAwareHybridRetrievalService,
        embedding_provider: IEmbeddingProvider,
    ):
        self._capability = capability
        self.hybrid_retrieval_service = hybrid_retrieval_service
        self.embedding_provider = embedding_provider

    @property
    def capability(self) -> RetrievalCapability:
        return self._capability

    async def execute(
        self,
        user_id: uuid.UUID,
        subqueries: List[RetrievalQuery],
        conversation_id: Optional[uuid.UUID] = None,
        limit: int = 10,
    ) -> List[RetrievalResult]:
        system_map = {
            RetrievalCapability.SEMANTIC_SEARCH: MemorySystem.SEMANTIC,
            RetrievalCapability.EPISODIC_SEARCH: MemorySystem.EPISODIC,
            RetrievalCapability.PROCEDURAL_SEARCH: MemorySystem.PROCEDURAL,
        }
        target_system = system_map.get(self._capability, MemorySystem.SEMANTIC)
        
        results: List[RetrievalResult] = []
        for subquery in subqueries:
            try:
                # Generate embedding for vector similarity search
                embedding = await self.embedding_provider.get_embedding(subquery.query)
            except Exception:
                embedding = None

            memories = await self.hybrid_retrieval_service.search_hybrid(
                user_id=user_id,
                query_embedding=embedding,
                systems=[target_system],
                limit_per_system=limit,
                conversation_id=conversation_id,
            )
            
            for memory in memories:
                results.append(
                    RetrievalResult(
                        memory=memory,
                        score=subquery.priority,
                        source_query=subquery.query,
                        capability=self._capability,
                        metadata={
                            "reason": subquery.reason,
                            "source_priority": subquery.priority,
                        }
                    )
                )
        return results


class WorkingMemoryExecutor(IRetrievalExecutor):
    """Executes retrieval against the Working Memory tier."""
    
    def __init__(
        self,
        hybrid_retrieval_service: GraphAwareHybridRetrievalService,
        embedding_provider: IEmbeddingProvider,
    ):
        self.hybrid_retrieval_service = hybrid_retrieval_service
        self.embedding_provider = embedding_provider

    @property
    def capability(self) -> RetrievalCapability:
        return RetrievalCapability.WORKING_MEMORY

    async def execute(
        self,
        user_id: uuid.UUID,
        subqueries: List[RetrievalQuery],
        conversation_id: Optional[uuid.UUID] = None,
        limit: int = 10,
    ) -> List[RetrievalResult]:
        results: List[RetrievalResult] = []
        for subquery in subqueries:
            try:
                embedding = await self.embedding_provider.get_embedding(subquery.query)
            except Exception:
                embedding = None

            memories = await self.hybrid_retrieval_service.search_hybrid(
                user_id=user_id,
                query_embedding=embedding,
                systems=[MemorySystem.WORKING],
                limit_per_system=limit,
                conversation_id=conversation_id,
            )
            for memory in memories:
                results.append(
                    RetrievalResult(
                        memory=memory,
                        score=subquery.priority,
                        source_query=subquery.query,
                        capability=RetrievalCapability.WORKING_MEMORY,
                        metadata={
                            "reason": subquery.reason,
                            "source_priority": subquery.priority,
                        }
                    )
                )
        return results


class GraphRetrievalExecutor(IRetrievalExecutor):
    """Executes retrieval against the Knowledge Graph entities mapped to memories."""
    
    def __init__(
        self,
        graph_repo: SQLGraphRepository,
        memory_repo: IMemoryRepository,
    ):
        self.graph_repo = graph_repo
        self.memory_repo = memory_repo

    @property
    def capability(self) -> RetrievalCapability:
        return RetrievalCapability.KNOWLEDGE_GRAPH

    async def execute(
        self,
        user_id: uuid.UUID,
        subqueries: List[RetrievalQuery],
        conversation_id: Optional[uuid.UUID] = None,
        limit: int = 10,
    ) -> List[RetrievalResult]:
        results: List[RetrievalResult] = []
        for subquery in subqueries:
            canonical = normalize_canonical_name(subquery.query)
            node = await self.graph_repo.entities.get_by_name(user_id, canonical)
            
            if node:
                mappings = await self.graph_repo.mappings.list_by_node(node.id)
                memory_ids = [m.memory_id for m in mappings]
                if memory_ids:
                    # Enforce the system page/limit limit for query retrieval safety
                    memories = await self.memory_repo.get_by_ids(memory_ids[:limit])
                    for memory in memories:
                        results.append(
                            RetrievalResult(
                                memory=memory,
                                score=subquery.priority,
                                source_query=subquery.query,
                                capability=RetrievalCapability.KNOWLEDGE_GRAPH,
                                metadata={
                                    "node_id": str(node.id),
                                    "node_name": node.name,
                                    "reason": subquery.reason,
                                }
                            )
                        )
        return results
