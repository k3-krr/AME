import pytest
import uuid
from datetime import datetime
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_graph.domain.entities import (
    Node,
    NodeType,
    EntityType,
    Relationship,
    RelationshipType,
    MemoryNodeMapping,
    normalize_canonical_name,
)
from app.knowledge_graph.exceptions import (
    EntityNotFoundError,
    RelationshipNotFoundError,
    DuplicateEntityError,
    DuplicateRelationshipError,
)
from app.knowledge_graph.models.models import (
    NodeTable,
    RelationshipTable,
    MemoryNodeMappingTable,
)
from app.knowledge_graph.repositories.sql_repositories import (
    SQLEntityRepository,
    SQLRelationshipRepository,
    SQLMemoryNodeMappingRepository,
    SQLGraphRepository,
)
from app.knowledge_graph.services.entity_service import EntityService
from app.knowledge_graph.services.relationship_service import RelationshipService
from app.knowledge_graph.services.graph_service import GraphService
from app.infrastructure.repositories.sql_repos import SQLMemoryRepository, SQLUserRepository
from app.domain.entities import Memory, MemoryType, MemoryStatus
from app.domain.memory_system import MemorySystem

pytestmark = pytest.mark.asyncio


# ==============================================================================
# 1. UNIT & DOMAIN TESTS
# ==============================================================================

def test_normalization_and_validation():
    # Normalization helper checks
    assert normalize_canonical_name("  FastAPI   ") == "fastapi"
    assert normalize_canonical_name("  Deep   Learning  ") == "deep learning"
    assert normalize_canonical_name(None) == ""

    # Node validation
    user_id = uuid.uuid4()
    node = Node(
        id=uuid.uuid4(),
        user_id=user_id,
        node_type=NodeType.ENTITY,
        name="FastAPI",
        canonical_name="fastapi",
        entity_type=EntityType.FRAMEWORK,
    )
    node.validate()  # Should not raise

    invalid_node = Node(
        id=uuid.uuid4(),
        user_id=user_id,
        node_type=NodeType.ENTITY,
        name="   ",
        canonical_name="fastapi",
        entity_type=EntityType.FRAMEWORK,
    )
    with pytest.raises(ValueError, match="Node name cannot be empty"):
        invalid_node.validate()

    invalid_node2 = Node(
        id=uuid.uuid4(),
        user_id=user_id,
        node_type=NodeType.ENTITY,
        name="FastAPI",
        canonical_name="   ",
        entity_type=EntityType.FRAMEWORK,
    )
    with pytest.raises(ValueError, match="Node canonical name cannot be empty"):
        invalid_node2.validate()

    invalid_node3 = Node(
        id=uuid.uuid4(),
        user_id=user_id,
        node_type=NodeType.ENTITY,
        name="FastAPI",
        canonical_name="fastapi",
        entity_type=None,
    )
    with pytest.raises(ValueError, match="EntityType is required for nodes of type ENTITY"):
        invalid_node3.validate()


def test_relationship_and_mapping_validation():
    # Relationship validation
    user_id = uuid.uuid4()
    source_id = uuid.uuid4()
    target_id = uuid.uuid4()

    rel = Relationship(
        id=uuid.uuid4(),
        user_id=user_id,
        source_node_id=source_id,
        target_node_id=target_id,
        relationship_type=RelationshipType.USES,
        confidence=0.85,
    )
    rel.validate()  # Should pass

    # Confidence check
    invalid_rel = Relationship(
        id=uuid.uuid4(),
        user_id=user_id,
        source_node_id=source_id,
        target_node_id=target_id,
        relationship_type=RelationshipType.USES,
        confidence=-0.1,
    )
    with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
        invalid_rel.validate()

    # Self-loop check
    invalid_rel2 = Relationship(
        id=uuid.uuid4(),
        user_id=user_id,
        source_node_id=source_id,
        target_node_id=source_id,
        relationship_type=RelationshipType.USES,
        confidence=0.5,
    )
    with pytest.raises(ValueError, match="Self-referential loops are not allowed"):
        invalid_rel2.validate()

    # Mapping validation
    mapping = MemoryNodeMapping(
        memory_id=uuid.uuid4(),
        node_id=uuid.uuid4(),
        confidence=0.9,
    )
    mapping.validate()

    invalid_mapping = MemoryNodeMapping(
        memory_id=uuid.uuid4(),
        node_id=uuid.uuid4(),
        confidence=1.5,
    )
    with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
        invalid_mapping.validate()


# ==============================================================================
# 2. REPOSITORY SQL TESTS
# ==============================================================================

async def test_entity_repository(db_session: AsyncSession):
    user_repo = SQLUserRepository(db_session)
    user = await user_repo.create(email="entityrepo@example.com", password_hash="hash")
    await db_session.flush()

    repo = SQLEntityRepository(db_session)
    node_id = uuid.uuid4()
    node = Node(
        id=node_id,
        user_id=user.id,
        node_type=NodeType.ENTITY,
        name="FastAPI",
        canonical_name="fastapi",
        entity_type=EntityType.FRAMEWORK,
    )

    # Create
    created = await repo.create(node)
    assert created.id == node_id
    assert created.name == "FastAPI"

    # Get by ID
    fetched = await repo.get_by_id(node_id)
    assert fetched is not None
    assert fetched.name == "FastAPI"

    # Get by Name
    fetched_name = await repo.get_by_name(user.id, "fastapi")
    assert fetched_name is not None
    assert fetched_name.id == node_id

    # Update
    fetched.name = "FastAPI Updated"
    updated = await repo.update(fetched)
    assert updated.name == "FastAPI Updated"

    # List by user
    nodes = await repo.list_by_user(user.id)
    assert len(nodes) == 1
    assert nodes[0].id == node_id

    # Delete
    deleted = await repo.delete(node_id)
    assert deleted is True
    fetched_deleted = await repo.get_by_id(node_id)
    assert fetched_deleted is None


async def test_relationship_repository(db_session: AsyncSession):
    user_repo = SQLUserRepository(db_session)
    user = await user_repo.create(email="relrepo@example.com", password_hash="hash")
    await db_session.flush()

    node_repo = SQLEntityRepository(db_session)
    source = await node_repo.create(Node(
        id=uuid.uuid4(),
        user_id=user.id,
        node_type=NodeType.ENTITY,
        name="Node A",
        canonical_name="node a",
        entity_type=EntityType.TECHNOLOGY,
    ))
    target = await node_repo.create(Node(
        id=uuid.uuid4(),
        user_id=user.id,
        node_type=NodeType.ENTITY,
        name="Node B",
        canonical_name="node b",
        entity_type=EntityType.TECHNOLOGY,
    ))

    repo = SQLRelationshipRepository(db_session)
    rel_id = uuid.uuid4()
    rel = Relationship(
        id=rel_id,
        user_id=user.id,
        source_node_id=source.id,
        target_node_id=target.id,
        relationship_type=RelationshipType.USES,
        confidence=0.9,
    )

    # Create
    created = await repo.create(rel)
    assert created.id == rel_id
    assert created.relationship_type == RelationshipType.USES

    # Get by endpoints
    fetched_endpoints = await repo.get_by_endpoints(
        user.id, source.id, target.id, RelationshipType.USES
    )
    assert fetched_endpoints is not None
    assert fetched_endpoints.id == rel_id

    # Update
    created.confidence = 0.95
    updated = await repo.update(created)
    assert updated.confidence == 0.95

    # List by user
    rels = await repo.list_by_user(user.id)
    assert len(rels) == 1

    # Delete
    deleted = await repo.delete(rel_id)
    assert deleted is True


async def test_mapping_repository(db_session: AsyncSession):
    user_repo = SQLUserRepository(db_session)
    user = await user_repo.create(email="mappingrepo@example.com", password_hash="hash")
    await db_session.flush()

    memory_repo = SQLMemoryRepository(db_session)
    memory = await memory_repo.create(
        user_id=user.id,
        conversation_id=None,
        content="Testing memory content",
        memory_type=MemoryType.FACT,
        importance=0.5,
        confidence=0.8,
        status=MemoryStatus.ACTIVE,
        last_accessed_at=datetime.utcnow(),
        version=1,
        metadata={},
        memory_system=MemorySystem.SEMANTIC,
    )

    node_repo = SQLEntityRepository(db_session)
    node = await node_repo.create(Node(
        id=uuid.uuid4(),
        user_id=user.id,
        node_type=NodeType.ENTITY,
        name="Node A",
        canonical_name="node a",
        entity_type=EntityType.TECHNOLOGY,
    ))

    repo = SQLMemoryNodeMappingRepository(db_session)
    mapping = MemoryNodeMapping(
        memory_id=memory.id,
        node_id=node.id,
        confidence=0.9,
    )

    # Create
    created = await repo.create(mapping)
    assert created.memory_id == memory.id
    assert created.node_id == node.id

    # Get by IDs
    fetched = await repo.get_by_ids(memory.id, node.id)
    assert fetched is not None
    assert fetched.confidence == 0.9

    # List
    list_mem = await repo.list_by_memory(memory.id)
    assert len(list_mem) == 1
    list_node = await repo.list_by_node(node.id)
    assert len(list_node) == 1

    # Delete
    deleted = await repo.delete(memory.id, node.id)
    assert deleted is True


# ==============================================================================
# 3. SERVICE LAYER TESTS
# ==============================================================================

async def test_entity_service(db_session: AsyncSession):
    user_repo = SQLUserRepository(db_session)
    user = await user_repo.create(email="entserv@example.com", password_hash="hash")
    await db_session.flush()

    repo = SQLEntityRepository(db_session)
    service = EntityService(repo)

    # Create entity
    entity = await service.create_entity(
        user_id=user.id,
        name="FastAPI",
        entity_type=EntityType.FRAMEWORK,
        metadata={"version": "0.110"},
    )
    assert entity.canonical_name == "fastapi"

    # Try duplicate creation
    with pytest.raises(DuplicateEntityError, match="already exists"):
        await service.create_entity(
            user_id=user.id,
            name="  fastapi  ",
            entity_type=EntityType.FRAMEWORK,
        )

    # Retrieve
    fetched = await service.get_entity(user.id, entity.id)
    assert fetched.name == "FastAPI"

    # Non-existent
    with pytest.raises(EntityNotFoundError):
        await service.get_entity(user.id, uuid.uuid4())

    # Update
    updated = await service.update_entity(
        user_id=user.id,
        entity_id=entity.id,
        name="FastAPI Core",
    )
    assert updated.name == "FastAPI Core"
    assert updated.canonical_name == "fastapi core"

    # Delete
    deleted = await service.delete_entity(user.id, entity.id)
    assert deleted is True


async def test_relationship_service(db_session: AsyncSession):
    user_repo = SQLUserRepository(db_session)
    user = await user_repo.create(email="relserv@example.com", password_hash="hash")
    await db_session.flush()

    node_repo = SQLEntityRepository(db_session)
    source = await node_repo.create(Node(
        id=uuid.uuid4(),
        user_id=user.id,
        node_type=NodeType.ENTITY,
        name="FastAPI",
        canonical_name="fastapi",
        entity_type=EntityType.FRAMEWORK,
    ))
    target = await node_repo.create(Node(
        id=uuid.uuid4(),
        user_id=user.id,
        node_type=NodeType.ENTITY,
        name="Uvicorn",
        canonical_name="uvicorn",
        entity_type=EntityType.TECHNOLOGY,
    ))

    rel_repo = SQLRelationshipRepository(db_session)
    service = RelationshipService(rel_repo, node_repo)

    # Create relationship
    rel = await service.create_relationship(
        user_id=user.id,
        source_node_id=source.id,
        target_node_id=target.id,
        relationship_type=RelationshipType.USES,
        confidence=0.9,
    )
    assert rel.relationship_type == RelationshipType.USES

    # Duplicate creation
    with pytest.raises(DuplicateRelationshipError):
        await service.create_relationship(
            user_id=user.id,
            source_node_id=source.id,
            target_node_id=target.id,
            relationship_type=RelationshipType.USES,
        )

    # Validate target node belonging to different user
    other_user = await user_repo.create(email="other_user@example.com", password_hash="hash")
    await db_session.flush()
    other_node = await node_repo.create(Node(
        id=uuid.uuid4(),
        user_id=other_user.id,
        node_type=NodeType.ENTITY,
        name="Other Node",
        canonical_name="other node",
        entity_type=EntityType.TECHNOLOGY,
    ))

    with pytest.raises(EntityNotFoundError):
        await service.create_relationship(
            user_id=user.id,
            source_node_id=source.id,
            target_node_id=other_node.id,
            relationship_type=RelationshipType.USES,
        )


# ==============================================================================
# 4. API LAYER INTEGRATION TESTS
# ==============================================================================

async def test_kg_unauthorized_access(client: AsyncClient):
    # Verify unauthorized checks
    resp = await client.get("/api/v1/entities")
    assert resp.status_code == 401

    resp2 = await client.post(
        "/api/v1/entities",
        json={"name": "test", "entity_type": "TECHNOLOGY"}
    )
    assert resp2.status_code == 401

    resp3 = await client.get("/api/v1/relationships")
    assert resp3.status_code == 401


async def test_kg_entity_api_crud_cycle(client: AsyncClient):
    # 1. Register & Authenticate User A
    await client.post(
        "/api/v1/auth/register",
        json={"email": "kgtesta@example.com", "password": "password123"}
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "kgtesta@example.com", "password": "password123"}
    )
    assert login_resp.status_code == 200

    # 2. Create Entity
    create_resp = await client.post(
        "/api/v1/entities",
        json={
            "name": "FastAPI",
            "entity_type": "FRAMEWORK",
            "metadata": {"awesome": True}
        }
    )
    assert create_resp.status_code == 201
    data = create_resp.json()
    assert data["id"] is not None
    assert data["name"] == "FastAPI"
    assert data["canonical_name"] == "fastapi"
    assert data["entity_type"] == "FRAMEWORK"
    assert data["metadata"] == {"awesome": True}
    entity_id = data["id"]

    # 3. Read specific entity detail
    get_resp = await client.get(f"/api/v1/entities/{entity_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "FastAPI"

    # 4. Update entity details
    update_resp = await client.put(
        f"/api/v1/entities/{entity_id}",
        json={
            "name": "FastAPI Framework",
            "metadata": {"awesome": True, "version": "0.100"}
        }
    )
    assert update_resp.status_code == 200
    updated_data = update_resp.json()
    assert updated_data["name"] == "FastAPI Framework"
    assert updated_data["canonical_name"] == "fastapi framework"
    assert updated_data["metadata"]["version"] == "0.100"

    # 5. List entities
    list_resp = await client.get("/api/v1/entities?entity_type=FRAMEWORK")
    assert list_resp.status_code == 200
    entities = list_resp.json()
    assert len(entities) >= 1
    assert any(e["id"] == entity_id for e in entities)

    # 6. Delete entity
    delete_resp = await client.delete(f"/api/v1/entities/{entity_id}")
    assert delete_resp.status_code == 204

    # 7. Verify deletion
    get_deleted_resp = await client.get(f"/api/v1/entities/{entity_id}")
    assert get_deleted_resp.status_code == 404


async def test_kg_relationship_api_crud_cycle(client: AsyncClient):
    # Register & Login User A
    await client.post(
        "/api/v1/auth/register",
        json={"email": "kgtestb@example.com", "password": "password123"}
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "kgtestb@example.com", "password": "password123"}
    )

    # Create Source Entity
    r_src = await client.post(
        "/api/v1/entities",
        json={"name": "FastAPI", "entity_type": "FRAMEWORK"}
    )
    src_id = r_src.json()["id"]

    # Create Target Entity
    r_tgt = await client.post(
        "/api/v1/entities",
        json={"name": "Uvicorn", "entity_type": "TECHNOLOGY"}
    )
    tgt_id = r_tgt.json()["id"]

    # Create Relationship
    create_resp = await client.post(
        "/api/v1/relationships",
        json={
            "source_entity_id": src_id,
            "target_entity_id": tgt_id,
            "relationship_type": "USES",
            "confidence": 0.95,
            "metadata": {"speed": "high"}
        }
    )
    assert create_resp.status_code == 201
    data = create_resp.json()
    assert data["id"] is not None
    assert data["source_entity_id"] == src_id
    assert data["target_entity_id"] == tgt_id
    assert data["relationship_type"] == "USES"
    assert data["confidence"] == 0.95
    assert data["metadata"] == {"speed": "high"}
    rel_id = data["id"]

    # Read specific relationship
    get_resp = await client.get(f"/api/v1/relationships/{rel_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["relationship_type"] == "USES"

    # Update relationship
    update_resp = await client.put(
        f"/api/v1/relationships/{rel_id}",
        json={
            "relationship_type": "DEPENDS_ON",
            "confidence": 0.99
        }
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["relationship_type"] == "DEPENDS_ON"
    assert update_resp.json()["confidence"] == 0.99

    # List relationships
    list_resp = await client.get(f"/api/v1/relationships?source_entity_id={src_id}")
    assert list_resp.status_code == 200
    rels = list_resp.json()
    assert len(rels) >= 1
    assert rels[0]["id"] == rel_id

    # Delete relationship
    delete_resp = await client.delete(f"/api/v1/relationships/{rel_id}")
    assert delete_resp.status_code == 204

    # Verify deletion
    get_deleted_resp = await client.get(f"/api/v1/relationships/{rel_id}")
    assert get_deleted_resp.status_code == 404


async def test_kg_authorization_boundaries(client: AsyncClient):
    # 1. Register and login User A
    await client.post(
        "/api/v1/auth/register",
        json={"email": "kga@example.com", "password": "password123"}
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "kga@example.com", "password": "password123"}
    )

    # User A creates an entity
    r_ent = await client.post(
        "/api/v1/entities",
        json={"name": "User A Entity", "entity_type": "TECHNOLOGY"}
    )
    ent_a_id = r_ent.json()["id"]

    # 2. Register and login User B
    await client.post(
        "/api/v1/auth/register",
        json={"email": "kgb@example.com", "password": "password123"}
    )
    client.cookies.clear()
    await client.post(
        "/api/v1/auth/login",
        json={"email": "kgb@example.com", "password": "password123"}
    )

    # User B tries to read User A's entity -> 404 or 403. Our implementation returns 404
    # (or 404 detail matches EntityNotFound exception from entity_service.get_entity)
    get_resp = await client.get(f"/api/v1/entities/{ent_a_id}")
    assert get_resp.status_code == 404

    # User B tries to update User A's entity -> 404
    put_resp = await client.put(f"/api/v1/entities/{ent_a_id}", json={"name": "Hacked"})
    assert put_resp.status_code == 404

    # User B tries to delete User A's entity -> 404
    delete_resp = await client.delete(f"/api/v1/entities/{ent_a_id}")
    assert delete_resp.status_code == 404


async def test_kg_validation_and_duplicate_blocking(client: AsyncClient):
    # Register & Login User
    await client.post(
        "/api/v1/auth/register",
        json={"email": "kgvalidation@example.com", "password": "password123"}
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "kgvalidation@example.com", "password": "password123"}
    )

    # 1. Duplicate Entities checks
    r1 = await client.post(
        "/api/v1/entities",
        json={"name": "FastAPI", "entity_type": "FRAMEWORK"}
    )
    assert r1.status_code == 201

    r2 = await client.post(
        "/api/v1/entities",
        json={"name": "   fastapi  ", "entity_type": "FRAMEWORK"}
    )
    assert r2.status_code == 409
    assert "already exists" in r2.json()["message"]

    # 2. Validation constraints
    r3 = await client.post(
        "/api/v1/entities",
        json={"name": "   ", "entity_type": "FRAMEWORK"}
    )
    assert r3.status_code == 422
