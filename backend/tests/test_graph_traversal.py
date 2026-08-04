import pytest
import uuid
from datetime import datetime
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_graph.domain.entities import Node, NodeType, EntityType, Relationship, RelationshipType
from app.knowledge_graph.services.in_memory_graph import InMemoryGraph
from app.knowledge_graph.services.graph_traversal_service import GraphTraversalService
from app.knowledge_graph.dependencies.graph_deps import get_graph_traversal_service
from app.infrastructure.repositories.sql_repos import SQLMemoryRepository, SQLUserRepository
from app.domain.entities import Memory, MemoryType, MemoryStatus
from app.domain.memory_system import MemorySystem
from app.config import settings

pytestmark = pytest.mark.asyncio


# ==============================================================================
# 1. UNIT & GRAPH ALGORITHM TESTS
# ==============================================================================

async def test_in_memory_graph_algorithms():
    # Setup cyclic graph with weights:
    # AME (0) -> FastAPI (1) -> PostgreSQL (2) -> pgvector (3)
    # AME (0) -> pgvector (3) [shortcut path, but with lower confidence or just standard path]
    # PostgreSQL (2) -> AME (0) [cycle]
    u_id = uuid.uuid4()
    n_ame = Node(id=uuid.uuid4(), user_id=u_id, node_type=NodeType.ENTITY, name="AME", canonical_name="ame", entity_type=EntityType.PROJECT)
    n_fastapi = Node(id=uuid.uuid4(), user_id=u_id, node_type=NodeType.ENTITY, name="FastAPI", canonical_name="fastapi", entity_type=EntityType.FRAMEWORK)
    n_postgres = Node(id=uuid.uuid4(), user_id=u_id, node_type=NodeType.ENTITY, name="PostgreSQL", canonical_name="postgresql", entity_type=EntityType.DATABASE)
    n_pgvector = Node(id=uuid.uuid4(), user_id=u_id, node_type=NodeType.ENTITY, name="pgvector", canonical_name="pgvector", entity_type=EntityType.TECHNOLOGY)

    nodes = [n_ame, n_fastapi, n_postgres, n_pgvector]

    r1 = Relationship(id=uuid.uuid4(), user_id=u_id, source_node_id=n_ame.id, target_node_id=n_fastapi.id, relationship_type=RelationshipType.USES, confidence=0.98)
    r2 = Relationship(id=uuid.uuid4(), user_id=u_id, source_node_id=n_fastapi.id, target_node_id=n_postgres.id, relationship_type=RelationshipType.USES, confidence=0.95)
    r3 = Relationship(id=uuid.uuid4(), user_id=u_id, source_node_id=n_postgres.id, target_node_id=n_pgvector.id, relationship_type=RelationshipType.INDEXED_BY, confidence=0.98)
    r4 = Relationship(id=uuid.uuid4(), user_id=u_id, source_node_id=n_postgres.id, target_node_id=n_ame.id, relationship_type=RelationshipType.DEPENDS_ON, confidence=0.85)

    relationships = [r1, r2, r3, r4]

    graph = InMemoryGraph(nodes, relationships)

    # 1. Test deterministic neighbor sorting
    # AME neighbors should sort incoming/outgoing. Outgoing: FastAPI. Incoming: PostgreSQL.
    # Sorted order should be alphabetical by canonical name: "fastapi" then "postgresql" (if both).
    neighbors = graph.get_filtered_neighbors(n_ame.id, direction="both")
    assert len(neighbors) == 2
    assert neighbors[0][2].canonical_name == "fastapi"   # Outgoing target
    assert neighbors[1][0].canonical_name == "postgresql" # Incoming source

    # 2. Test BFS Traversal
    bfs_nodes, term_bfs = graph.bfs(start_node_id=n_ame.id, max_depth=2)
    # Depth 0: AME
    # Depth 1: FastAPI, PostgreSQL (via incoming)
    # Depth 2: pgvector (neighbor of PostgreSQL)
    assert len(bfs_nodes) == 4
    assert bfs_nodes[0]["node"].canonical_name == "ame"
    assert bfs_nodes[1]["node"].canonical_name == "fastapi"
    assert term_bfs == "MAX_DEPTH"

    # 3. Test DFS Traversal
    dfs_nodes, term_dfs = graph.dfs(start_node_id=n_ame.id, max_depth=1)
    assert len(dfs_nodes) == 3 # AME, FastAPI, PostgreSQL
    assert term_dfs == "MAX_DEPTH"

    # 4. Test Shortest Path (Dijkstra)
    path = graph.find_shortest_path(source_id=n_ame.id, target_id=n_pgvector.id, direction="outgoing")
    assert path is not None
    assert path["hop_count"] == 3
    assert path["nodes"][0].canonical_name == "ame"
    assert path["nodes"][1].canonical_name == "fastapi"
    assert path["nodes"][2].canonical_name == "postgresql"
    assert path["nodes"][3].canonical_name == "pgvector"
    assert path["termination_reason"] == "TARGET_FOUND"


# ==============================================================================
# 2. SERVICE LAYER & DEDUPLICATED MEMORIES TESTS
# ==============================================================================

async def test_traversal_service_connected_memories(db_session: AsyncSession):
    user_repo = SQLUserRepository(db_session)
    user = await user_repo.create(email="traversalserv@example.com", password_hash="hash")
    await db_session.flush()

    graph_service = get_graph_traversal_service(db_session)

    # Create nodes
    n_fastapi = await graph_service.graph_repo.entities.create(Node(
        id=uuid.uuid4(), user_id=user.id, node_type=NodeType.ENTITY,
        name="FastAPI", canonical_name="fastapi", entity_type=EntityType.FRAMEWORK
    ))
    n_postgres = await graph_service.graph_repo.entities.create(Node(
        id=uuid.uuid4(), user_id=user.id, node_type=NodeType.ENTITY,
        name="PostgreSQL", canonical_name="postgresql", entity_type=EntityType.DATABASE
    ))

    # Link nodes
    await graph_service.graph_repo.relationships.create(Relationship(
        id=uuid.uuid4(), user_id=user.id, source_node_id=n_fastapi.id,
        target_node_id=n_postgres.id, relationship_type=RelationshipType.USES, confidence=0.98
    ))

    # Create memory mapped to PostgreSQL
    memory_repo = SQLMemoryRepository(db_session)
    mem1 = await memory_repo.create(
        user_id=user.id, conversation_id=None, content="PostgreSQL database.",
        memory_type=MemoryType.FACT, importance=0.5, confidence=0.9,
        status=MemoryStatus.ACTIVE, last_accessed_at=datetime.utcnow(),
        version=1, metadata={}, memory_system=MemorySystem.SEMANTIC
    )

    # Map PostgreSQL -> Memory
    from app.knowledge_graph.domain.entities import MemoryNodeMapping
    await graph_service.graph_repo.mappings.create(MemoryNodeMapping(
        memory_id=mem1.id, node_id=n_postgres.id, confidence=0.95
    ))

    # Map FastAPI -> Memory (same memory, to test de-duplication)
    await graph_service.graph_repo.mappings.create(MemoryNodeMapping(
        memory_id=mem1.id, node_id=n_fastapi.id, confidence=0.95
    ))

    # Fetch connected memories of FastAPI with max_depth=1 (traverses to PostgreSQL)
    memories = await graph_service.get_connected_memories(
        user_id=user.id,
        node_id=n_fastapi.id,
        max_depth=1,
        memory_repo=memory_repo
    )

    # Should return exactly 1 memory, verified de-duplicated
    assert len(memories) == 1
    assert memories[0].id == mem1.id


# ==============================================================================
# 3. API LAYER INTEGRATION TESTS
# ==============================================================================

async def test_traversal_unauthorized(client: AsyncClient):
    node_id = uuid.uuid4()
    resp1 = await client.get(f"/api/v1/graph/nodes/{node_id}/neighbors")
    assert resp1.status_code == 401

    resp2 = await client.get(f"/api/v1/graph/nodes/{node_id}/connected")
    assert resp2.status_code == 401

    resp3 = await client.get("/api/v1/graph/path", params={"source_node_id": str(node_id), "target_node_id": str(uuid.uuid4())})
    assert resp3.status_code == 401

    resp4 = await client.get("/api/v1/graph/traverse", params={"start_node_id": str(node_id)})
    assert resp4.status_code == 401


async def test_traversal_api_success_and_isolation(client: AsyncClient, db_session: AsyncSession):
    # 1. Register & Login User A
    r_reg = await client.post("/api/v1/auth/register", json={"email": "usera_trav@example.com", "password": "password123"})
    print("REG:", r_reg.status_code, r_reg.text)
    r_log = await client.post("/api/v1/auth/login", json={"email": "usera_trav@example.com", "password": "password123"})
    print("LOG:", r_log.status_code, r_log.text)

    # Create Node 1 (FastAPI) and Node 2 (Uvicorn)
    r_n1 = await client.post("/api/v1/entities", json={"name": "FastAPI", "entity_type": "FRAMEWORK"})
    print("N1:", r_n1.status_code, r_n1.text)
    n1_id = r_n1.json()["id"]

    r_n2 = await client.post("/api/v1/entities", json={"name": "Uvicorn", "entity_type": "TECHNOLOGY"})
    print("N2:", r_n2.status_code, r_n2.text)
    n2_id = r_n2.json()["id"]

    # Link Node 1 -> Node 2
    r_rel = await client.post("/api/v1/relationships", json={
        "source_entity_id": n1_id,
        "target_entity_id": n2_id,
        "relationship_type": "USES",
        "confidence": 0.95
    })
    print("REL:", r_rel.status_code, r_rel.text)


    # 2. Test Neighbors API
    neigh_resp = await client.get(f"/api/v1/graph/nodes/{n1_id}/neighbors")
    if neigh_resp.status_code != 200:
        print("NEIGHBORS ERROR:", neigh_resp.text)
    assert neigh_resp.status_code == 200
    neighbors = neigh_resp.json()
    assert len(neighbors) == 1
    assert neighbors[0]["node"]["canonical_name"] == "uvicorn"
    assert neighbors[0]["direction"] == "outgoing"

    # 3. Test Path API
    path_resp = await client.get("/api/v1/graph/path", params={
        "source_node_id": n1_id,
        "target_node_id": n2_id
    })
    if path_resp.status_code != 200:
        print("PATH ERROR:", path_resp.text)
    assert path_resp.status_code == 200
    path = path_resp.json()
    assert path["hop_count"] == 1
    assert path["metadata"]["termination_reason"] == "TARGET_FOUND"

    # 4. Test Traverse API
    trav_resp = await client.get("/api/v1/graph/traverse", params={
        "start_node_id": n1_id,
        "max_depth": 2
    })
    if trav_resp.status_code != 200:
        print("TRAVERSE ERROR:", trav_resp.text)
    assert trav_resp.status_code == 200
    trav = trav_resp.json()
    assert len(trav["nodes"]) == 2
    assert trav["metadata"]["visited_node_count"] == 2
    assert trav["metadata"]["termination_reason"] == "NO_MORE_NEIGHBORS"

    # Add a third node (SQLite) and link Uvicorn -> SQLite to test MAX_DEPTH termination
    r_n3 = await client.post("/api/v1/entities", json={"name": "SQLite", "entity_type": "DATABASE"})
    n3_id = r_n3.json()["id"]
    await client.post("/api/v1/relationships", json={
        "source_entity_id": n2_id,
        "target_entity_id": n3_id,
        "relationship_type": "DEPENDS_ON",
        "confidence": 0.90
    })

    # Traverse again with max_depth=1 (should terminate with MAX_DEPTH because SQLite is at depth 2)
    trav_resp_depth = await client.get("/api/v1/graph/traverse", params={
        "start_node_id": n1_id,
        "max_depth": 1
    })
    assert trav_resp_depth.status_code == 200
    trav_depth = trav_resp_depth.json()
    assert len(trav_depth["nodes"]) == 2
    assert trav_depth["metadata"]["termination_reason"] == "MAX_DEPTH"

    # 5. Register & Login User B to verify Resource Isolation
    await client.post("/api/v1/auth/register", json={"email": "userb_trav@example.com", "password": "password123"})
    client.cookies.clear()
    await client.post("/api/v1/auth/login", json={"email": "userb_trav@example.com", "password": "password123"})

    # User B tries to traverse from User A's start node -> Should return 404 Node Not Found
    trav_resp_b = await client.get("/api/v1/graph/traverse", params={"start_node_id": n1_id})
    assert trav_resp_b.status_code == 404


async def test_traversal_api_invalid_parameters(client: AsyncClient):
    # Authenticate user
    await client.post("/api/v1/auth/register", json={"email": "invalid_trav@example.com", "password": "password123"})
    await client.post("/api/v1/auth/login", json={"email": "invalid_trav@example.com", "password": "password123"})

    n_id = uuid.uuid4()

    # 1. Invalid direction parameter
    r1 = await client.get(f"/api/v1/graph/nodes/{n_id}/neighbors", params={"direction": "hacked"})
    assert r1.status_code == 422

    # 2. Negative max depth
    r2 = await client.get("/api/v1/graph/traverse", params={"start_node_id": str(n_id), "max_depth": -1})
    assert r2.status_code == 422

    # 3. Exceeded max depth
    r3 = await client.get("/api/v1/graph/traverse", params={"start_node_id": str(n_id), "max_depth": 100})
    assert r3.status_code == 422

    # 4. Invalid relationship type filters
    r4 = await client.get("/api/v1/graph/traverse", params={"start_node_id": str(n_id), "relationship_types": "INVALID_TYPE"})
    assert r4.status_code == 422
