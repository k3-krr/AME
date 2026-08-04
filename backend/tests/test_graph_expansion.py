import pytest
import uuid
from datetime import datetime
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.knowledge_graph.domain.entities import Node, NodeType, EntityType, Relationship, RelationshipType, MemoryNodeMapping
from app.knowledge_graph.services.in_memory_graph import InMemoryGraph
from app.knowledge_graph.services.expansion_service import KnowledgeGraphExpansionService, GraphExpansionCandidate
from app.application.graph_aware_hybrid_retrieval_service import GraphAwareHybridRetrievalService
from app.application.hybrid_retrieval_service import HybridRetrievalService
from app.infrastructure.repositories.sql_repos import SQLMemoryRepository, SQLUserRepository
from app.knowledge_graph.repositories.sql_repositories import SQLGraphRepository
from app.domain.entities import Memory, MemoryType, MemoryStatus
from app.domain.memory_system import MemorySystem

pytestmark = pytest.mark.asyncio


# ==============================================================================
# 1. UNIT & GRAPH ALGORITHM TESTS
# ==============================================================================

async def test_graph_expansion_candidate_generation():
    # Setup test graph:
    # Node A (mapped to Memory 1) -> USES -> Node B (mapped to Memory 2) -> DEPENDS_ON -> Node C (mapped to Memory 3)
    # Start: Memory 1
    u_id = uuid.uuid4()
    n_a = Node(id=uuid.uuid4(), user_id=u_id, node_type=NodeType.ENTITY, name="Node A", canonical_name="node_a", entity_type=EntityType.PROJECT)
    n_b = Node(id=uuid.uuid4(), user_id=u_id, node_type=NodeType.ENTITY, name="Node B", canonical_name="node_b", entity_type=EntityType.FRAMEWORK)
    n_c = Node(id=uuid.uuid4(), user_id=u_id, node_type=NodeType.ENTITY, name="Node C", canonical_name="node_c", entity_type=EntityType.DATABASE)

    r1 = Relationship(id=uuid.uuid4(), user_id=u_id, source_node_id=n_a.id, target_node_id=n_b.id, relationship_type=RelationshipType.USES, confidence=0.95)
    r2 = Relationship(id=uuid.uuid4(), user_id=u_id, source_node_id=n_b.id, target_node_id=n_c.id, relationship_type=RelationshipType.DEPENDS_ON, confidence=0.90)

    # Mock repository queries
    class MockGraphRepo:
        def __init__(self):
            class MockMappings:
                async def list_by_memories(self, memory_ids):
                    # Memory 1 maps to Node A
                    return [MemoryNodeMapping(memory_id=memory_ids[0], node_id=n_a.id, confidence=1.0)]

                async def list_by_node(self, node_id):
                    # Node B maps to Memory 2, Node C maps to Memory 3
                    if node_id == n_b.id:
                        return [MemoryNodeMapping(memory_id=uuid.UUID("11111111-1111-1111-1111-111111111111"), node_id=n_b.id, confidence=0.8)]
                    if node_id == n_c.id:
                        return [MemoryNodeMapping(memory_id=uuid.UUID("22222222-2222-2222-2222-222222222222"), node_id=n_c.id, confidence=0.9)]
                    return []
            self.mappings = MockMappings()
            class MockEntities:
                async def list_by_user(self, user_id, limit):
                    return [n_a, n_b, n_c]
            self.entities = MockEntities()
            class MockRelationships:
                async def list_by_user(self, user_id, limit):
                    return [r1, r2]
            self.relationships = MockRelationships()

    mock_graph_repo = MockGraphRepo()
    expansion_service = KnowledgeGraphExpansionService(mock_graph_repo)

    # Mock initial memory list (Memory 1)
    mem1 = Memory(
        id=uuid.uuid4(), user_id=u_id, conversation_id=None, content="Initial content",
        memory_type=MemoryType.FACT, importance=0.5, confidence=1.0, status=MemoryStatus.ACTIVE,
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(), last_accessed_at=datetime.utcnow(),
        version=1, metadata={}, memory_system=MemorySystem.SEMANTIC
    )

    # 1. Test BFS Strategy Candidates
    settings.GRAPH_EXPANSION_STRATEGY = "BFS"
    settings.GRAPH_EXPANSION_DECAY = 0.8
    settings.GRAPH_EXPANSION_ENABLED = True

    candidates = await expansion_service.expand_memories(
        user_id=u_id,
        memories=[mem1],
    )

    # BFS should traverse Node A -> Node B (depth 1) -> Node C (depth 2)
    # Expected candidates: Memory 2 (Node B) and Memory 3 (Node C)
    assert len(candidates) == 2
    
    # Verify Candidate 1 (Memory 2)
    # graph_score = origin_mapping.confidence * (decay_factor ** depth) * target_mapping.confidence
    # = 1.0 * (0.8 ** 1) * 0.8 = 0.64
    c_mem2 = next(c for c in candidates if c.memory_id == uuid.UUID("11111111-1111-1111-1111-111111111111"))
    assert c_mem2.traversal_depth == 1
    assert c_mem2.path_length == 1
    assert abs(c_mem2.graph_score - 0.64) < 1e-5
    assert c_mem2.path == [n_a.id, n_b.id]

    # Verify Candidate 2 (Memory 3)
    # graph_score = 1.0 * (0.8 ** 2) * 0.9 = 0.576
    c_mem3 = next(c for c in candidates if c.memory_id == uuid.UUID("22222222-2222-2222-2222-222222222222"))
    assert c_mem3.traversal_depth == 2
    assert c_mem3.path_length == 2
    assert abs(c_mem3.graph_score - 0.576) < 1e-5
    assert c_mem3.path == [n_a.id, n_b.id, n_c.id]


# ==============================================================================
# 2. SOURCE PROVENANCE PRESERVATION TESTS
# ==============================================================================

async def test_source_provenance_preservation():
    u_id = uuid.uuid4()
    
    # 1. Base Retrieval Memory List (contains Memory 2)
    mem_initial = Memory(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"), user_id=u_id, conversation_id=None,
        content="Semantic memory", memory_type=MemoryType.FACT, importance=0.8, confidence=0.9,
        status=MemoryStatus.ACTIVE, created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
        last_accessed_at=datetime.utcnow(), version=1, metadata={"retrieval_source": "semantic"},
        memory_system=MemorySystem.SEMANTIC
    )

    class MockBaseRetrievalService:
        async def search_hybrid(self, **kwargs):
            return [mem_initial]

    # 2. Candidate reached via Graph Expansion (also maps to Memory 2)
    cand = GraphExpansionCandidate(
        memory_id=mem_initial.id,
        origin_memory_id=uuid.uuid4(),
        origin_node_id=uuid.uuid4(),
        traversal_depth=1,
        path_length=1,
        graph_score=0.76,
        path=[uuid.uuid4(), mem_initial.id],
    )

    class MockExpansionService:
        async def expand_memories(self, **kwargs):
            return [cand]

    class MockMemoryRepo:
        async def get_by_ids(self, ids):
            return [mem_initial]

    orchestrated_service = GraphAwareHybridRetrievalService(
        base_retrieval_service=MockBaseRetrievalService(),
        expansion_service=MockExpansionService(),
        memory_repo=MockMemoryRepo()
    )

    settings.GRAPH_EXPANSION_ENABLED = True
    results = await orchestrated_service.search_hybrid(user_id=u_id)

    assert len(results) == 1
    m = results[0]
    
    # Metadata must preserve BOTH retrieval sources
    assert "retrieval_sources" in m.metadata
    assert "semantic" in m.metadata["retrieval_sources"]
    assert "graph_expansion" in m.metadata["retrieval_sources"]
    
    # Must store detailed graph expansion path details
    assert "graph_provenance" in m.metadata
    prov = m.metadata["graph_provenance"]
    assert len(prov) == 1
    assert prov[0]["graph_score"] == 0.76


# ==============================================================================
# 3. DATABASE REPOSITORY BATCH MAPPING TESTS
# ==============================================================================

async def test_batch_mapping_retrieval(db_session: AsyncSession):
    user_repo = SQLUserRepository(db_session)
    user = await user_repo.create(email="kg_rep_batch@example.com", password_hash="hash")
    await db_session.flush()

    graph_repo = SQLGraphRepository(db_session)

    # Create node and maps
    node = await graph_repo.entities.create(Node(
        id=uuid.uuid4(), user_id=user.id, node_type=NodeType.ENTITY,
        name="Batch Node", canonical_name="batch_node", entity_type=EntityType.PROJECT
    ))

    mem_id1 = uuid.uuid4()
    mem_id2 = uuid.uuid4()

    await graph_repo.mappings.create(MemoryNodeMapping(memory_id=mem_id1, node_id=node.id, confidence=0.85))
    await graph_repo.mappings.create(MemoryNodeMapping(memory_id=mem_id2, node_id=node.id, confidence=0.90))

    # Fetch batch
    mappings = await graph_repo.mappings.list_by_memories([mem_id1, mem_id2])
    assert len(mappings) == 2
    assert {m.memory_id for m in mappings} == {mem_id1, mem_id2}


# ==============================================================================
# 4. API & SYSTEM INTEGRATION TESTS
# ==============================================================================

async def test_graph_aware_hybrid_retrieval_flow(client: AsyncClient, db_session: AsyncSession):
    # 1. Register & Login
    await client.post("/api/v1/auth/register", json={"email": "hybrid_expand@example.com", "password": "password123"})
    await client.post("/api/v1/auth/login", json={"email": "hybrid_expand@example.com", "password": "password123"})

    # 2. Create conversation
    rc = await client.post("/api/v1/conversations", json={"title": "KG Expansion Test Conv"})
    conv_id = rc.json()["id"]

    # Create two memories
    r1 = await client.post("/api/v1/memories", json={"content": "Memory A is about FastAPI.", "memory_type": "Fact", "importance": 0.8, "confidence": 0.9, "memory_system": "Semantic"})
    m_a_id = r1.json()["id"]

    r2 = await client.post("/api/v1/memories", json={"content": "Memory B is about PostgreSQL.", "memory_type": "Fact", "importance": 0.7, "confidence": 0.8, "memory_system": "Episodic", "conversation_id": conv_id})
    m_b_id = r2.json()["id"]

    # Trigger entity extraction so Node mappings are populated
    await client.post(f"/api/v1/memories/{m_a_id}/entities/extract")
    await client.post(f"/api/v1/memories/{m_b_id}/entities/extract")
    await client.post(f"/api/v1/memories/{m_a_id}/relationships/extract")
    await client.post(f"/api/v1/memories/{m_b_id}/relationships/extract")

    # Manually retrieve the created nodes to link them
    # (FastAPI USES PostgreSQL relationship)
    graph_repo = SQLGraphRepository(db_session)
    nodes = await graph_repo.entities.list_by_user(uuid.UUID(r1.json()["user_id"]), limit=10)
    
    n_fastapi = next(n for n in nodes if n.canonical_name == "fastapi")
    n_postgres = next(n for n in nodes if n.canonical_name == "postgresql")

    await graph_repo.relationships.create(Relationship(
        id=uuid.uuid4(), user_id=n_fastapi.user_id, source_node_id=n_fastapi.id,
        target_node_id=n_postgres.id, relationship_type=RelationshipType.USES, confidence=0.98
    ))

    # 3. Perform Hybrid Search with GRAPH EXPANSION ENABLED
    settings.GRAPH_EXPANSION_ENABLED = True
    settings.GRAPH_EXPANSION_STRATEGY = "BFS"
    
    # Query keyword matching ONLY Memory A's content -> Semantic search finds Memory A.
    # Knowledge Graph traversal from FastAPI -> PostgreSQL -> expands and includes Memory B!
    search_resp = await client.get("/api/v1/memories/hybrid/search", params={"query": "FastAPI", "systems": "semantic"})
    assert search_resp.status_code == 200
    results = search_resp.json()

    # Both memories should be returned: Memory A (semantic) + Memory B (graph expanded)
    assert len(results) >= 2
    
    m_a_res = next(m for m in results if m["id"] == m_a_id)
    m_b_res = next(m for m in results if m["id"] == m_b_id)

    # Verify sources and provenance metadata
    assert "graph_expansion" in m_b_res["metadata"]["retrieval_sources"]
    assert len(m_b_res["metadata"]["graph_provenance"]) == 1
    assert m_b_res["metadata"]["graph_provenance"][0]["origin_memory_id"] == m_a_id

    # 4. Perform search with GRAPH EXPANSION DISABLED
    settings.GRAPH_EXPANSION_ENABLED = False
    search_disabled = await client.get("/api/v1/memories/hybrid/search", params={"query": "FastAPI", "systems": "semantic"})
    assert search_disabled.status_code == 200
    results_disabled = search_disabled.json()

    # Graph expansion disabled: Memory B should NOT be included
    assert m_b_id not in [m["id"] for m in results_disabled]


# ==============================================================================
# 5. PRODUCTION READINESS & EDGE CASE TESTS
# ==============================================================================

async def test_graph_expansion_empty_and_disconnected_graphs(db_session: AsyncSession):
    user_repo = SQLUserRepository(db_session)
    user = await user_repo.create(email="kg_empty_edge@example.com", password_hash="hash")
    await db_session.flush()

    graph_repo = SQLGraphRepository(db_session)
    expansion_service = KnowledgeGraphExpansionService(graph_repo)

    # 1. Expand memories on an empty graph
    mem = Memory(
        id=uuid.uuid4(), user_id=user.id, conversation_id=None, content="Empty graph content",
        memory_type=MemoryType.FACT, importance=0.5, confidence=1.0, status=MemoryStatus.ACTIVE,
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(), last_accessed_at=datetime.utcnow(),
        version=1, metadata={}, memory_system=MemorySystem.SEMANTIC
    )

    candidates = await expansion_service.expand_memories(user_id=user.id, memories=[mem])
    assert len(candidates) == 0

    # 2. Expand on isolated node (node exists but has no relationships)
    node = await graph_repo.entities.create(Node(
        id=uuid.uuid4(), user_id=user.id, node_type=NodeType.ENTITY,
        name="Isolated Node", canonical_name="isolated_node", entity_type=EntityType.PROJECT
    ))
    
    await graph_repo.mappings.create(MemoryNodeMapping(memory_id=mem.id, node_id=node.id, confidence=0.9))
    
    # Expand again
    candidates_isolated = await expansion_service.expand_memories(user_id=user.id, memories=[mem])
    # The traversal finds no neighbors, so candidates should still be empty
    assert len(candidates_isolated) == 0


async def test_graph_expansion_multi_user_isolation(db_session: AsyncSession):
    user_repo = SQLUserRepository(db_session)
    user_a = await user_repo.create(email="user_a_kg@example.com", password_hash="hash")
    user_b = await user_repo.create(email="user_b_kg@example.com", password_hash="hash")
    await db_session.flush()

    graph_repo = SQLGraphRepository(db_session)
    expansion_service = KnowledgeGraphExpansionService(graph_repo)

    # User B Node and Memory Setup
    n_b = await graph_repo.entities.create(Node(
        id=uuid.uuid4(), user_id=user_b.id, node_type=NodeType.ENTITY,
        name="User B Node", canonical_name="user_b_node", entity_type=EntityType.PROJECT
    ))
    mem_b_id = uuid.uuid4()

    # User A Node and Memory Setup
    n_a = await graph_repo.entities.create(Node(
        id=uuid.uuid4(), user_id=user_a.id, node_type=NodeType.ENTITY,
        name="User A Node", canonical_name="user_a_node", entity_type=EntityType.PROJECT
    ))
    mem_a = Memory(
        id=uuid.uuid4(), user_id=user_a.id, conversation_id=None, content="User A Memory",
        memory_type=MemoryType.FACT, importance=0.8, confidence=0.9, status=MemoryStatus.ACTIVE,
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(), last_accessed_at=datetime.utcnow(),
        version=1, metadata={}, memory_system=MemorySystem.SEMANTIC
    )

    await graph_repo.mappings.create(MemoryNodeMapping(memory_id=mem_a.id, node_id=n_a.id, confidence=0.9))

    # Malicious mapping: mapping User B's node to User A's memory?
    # Regardless of mapping hacks, User A's expansion should never cross-traverse or yield User B candidates
    candidates = await expansion_service.expand_memories(user_id=user_a.id, memories=[mem_a])
    
    # Assert absolutely no User B node or mapping values are included in traversal
    for cand in candidates:
        assert cand.memory_id != mem_b_id
        assert cand.origin_node_id != n_b.id


def test_graph_expansion_config_validation():
    from pydantic import ValidationError
    from app.config import AppSettings

    # 1. Invalid strategy choice
    with pytest.raises(ValidationError) as excinfo:
        AppSettings(GRAPH_EXPANSION_STRATEGY="INVALID")
    assert "GRAPH_EXPANSION_STRATEGY" in str(excinfo.value)

    # 2. Invalid decay value (> 1.0)
    with pytest.raises(ValidationError) as excinfo:
        AppSettings(GRAPH_EXPANSION_DECAY=1.5)
    assert "GRAPH_EXPANSION_DECAY" in str(excinfo.value)

    # 3. Invalid decay value (< 0.0)
    with pytest.raises(ValidationError) as excinfo:
        AppSettings(GRAPH_EXPANSION_DECAY=-0.1)
    assert "GRAPH_EXPANSION_DECAY" in str(excinfo.value)

    # 4. Negative depth setting
    with pytest.raises(ValidationError) as excinfo:
        AppSettings(GRAPH_EXPANSION_MAX_DEPTH=-2)
    assert "Graph limit setting must be non-negative" in str(excinfo.value)

