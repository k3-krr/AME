import pytest
import uuid
from typing import List, Dict, Any
from datetime import datetime, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Memory, MemoryType, MemoryStatus
from app.domain.memory_system import MemorySystem
from app.retrieval.domain.value_objects import RetrievalCapability, RetrievalResult
from app.retrieval.domain.context_fusion_service import ContextFusionService
from app.retrieval.application.executor_registry import ExecutorRegistry


class MockExecutor:
    def __init__(self, capability: RetrievalCapability, memories: List[Memory]):
        self._capability = capability
        self.memories = memories

    @property
    def capability(self) -> RetrievalCapability:
        return self._capability

    async def execute(self, user_id: uuid.UUID, subqueries, conversation_id=None, limit=10):
        return [
            RetrievalResult(
                memory=m,
                score=0.9,
                source_query="test query",
                capability=self._capability,
                metadata={"test": True}
            )
            for m in self.memories
        ]


def test_context_fusion_service_deduplication_and_provenance():
    """Verify ContextFusionService merges duplicates and preserves all contributing paths."""
    fusion_service = ContextFusionService()
    
    memory_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    memory = Memory(
        id=memory_id,
        user_id=uuid.uuid4(),
        content="User loves playing tennis",
        memory_type=MemoryType.PREFERENCE,
        status=MemoryStatus.ACTIVE,
        importance=0.9,
        confidence=0.9,
        created_at=now,
        updated_at=now,
        last_accessed_at=now,
    )
    
    # Simulate the memory being retrieved by two different capabilities (e.g. SEMANTIC and WORKING)
    res1 = RetrievalResult(
        memory=memory,
        score=0.95,
        source_query="tennis",
        capability=RetrievalCapability.SEMANTIC_SEARCH,
        metadata={"match": "keyword"}
    )
    res2 = RetrievalResult(
        memory=memory,
        score=0.80,
        source_query="our chat",
        capability=RetrievalCapability.WORKING_MEMORY,
        metadata={"match": "active"}
    )
    
    ranked_memories = [(memory, 0.90)]
    retrieval_results = [res1, res2]
    
    package = fusion_service.fuse(
        request_id=uuid.uuid4(),
        ranked_memories=ranked_memories,
        retrieval_results=retrieval_results,
    )
    
    assert len(package.fused_elements) == 1
    element = package.fused_elements[0]
    assert element.memory_id == memory_id
    assert element.relevance_score == 0.90
    
    # Assert multi-path provenance is recorded
    paths = element.provenance_metadata["retrieval_paths"]
    assert len(paths) == 2
    
    semantic_path = next(p for p in paths if p["capability"] == "SEMANTIC_SEARCH")
    assert semantic_path["source_query"] == "tennis"
    assert semantic_path["score"] == 0.95
    
    working_path = next(p for p in paths if p["capability"] == "WORKING_MEMORY")
    assert working_path["source_query"] == "our chat"
    assert working_path["score"] == 0.80


def test_executor_registry_resolves_capability():
    """Verify ExecutorRegistry resolves executors by capability."""
    m_list = []
    exec1 = MockExecutor(RetrievalCapability.SEMANTIC_SEARCH, m_list)
    exec2 = MockExecutor(RetrievalCapability.KNOWLEDGE_GRAPH, m_list)
    
    registry = ExecutorRegistry([exec1, exec2])
    assert registry.get_executor(RetrievalCapability.SEMANTIC_SEARCH) is exec1
    assert registry.get_executor(RetrievalCapability.KNOWLEDGE_GRAPH) is exec2
    assert registry.get_executor(RetrievalCapability.WORKING_MEMORY) is None


@pytest.mark.asyncio
async def test_api_retrieval_retrieve_endpoint_flow(client: AsyncClient, db_session: AsyncSession):
    """Verify end-to-end retrieve endpoint maps, routes, and fuses correctly."""
    # 1. Register and login
    await client.post(
        "/api/v1/auth/register",
        json={"email": "retrieve_flow@example.com", "password": "securepassword123"}
    )
    
    # 2. Create conversation
    conv_resp = await client.post("/api/v1/conversations", json={"title": "Test Chat"})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["id"]

    # 3. Create a semantic memory fact
    mem_resp = await client.post(
        "/api/v1/memories",
        json={
            "content": "User owns a red bicycle.",
            "memory_type": "Fact",
            "importance": 0.8,
            "confidence": 0.95,
        }
    )
    assert mem_resp.status_code == 201
    
    # 4. Call /retrieve endpoint
    # The QueryIntent will match FACT_LOOKUP (due to "who owns/what is red bicycle")
    # which classifies to SEMANTIC_SEARCH capability, executing HybridRetrievalExecutor
    retrieve_resp = await client.post(
        "/api/v1/retrieval/retrieve",
        json={
            "query": "Tell me details about the red bicycle",
            "conversation_id": conv_id,
        }
    )
    
    assert retrieve_resp.status_code == 200
    data = retrieve_resp.json()
    assert "request_id" in data
    assert len(data["fused_elements"]) >= 1
    
    # Assert primary element fields
    element = data["fused_elements"][0]
    assert "red bicycle" in element["content"]
    assert element["source_tier"] == "SEMANTIC_SEARCH"
    
    # Assert provenance structure
    prov = element["provenance_metadata"]
    assert "retrieval_paths" in prov
    assert len(prov["retrieval_paths"]) >= 1
    path = prov["retrieval_paths"][0]
    assert path["capability"] == "SEMANTIC_SEARCH"
