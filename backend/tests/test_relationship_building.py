import pytest
import uuid
from datetime import datetime
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_graph.domain.entities import Node, NodeType, EntityType, Relationship, RelationshipType
from app.knowledge_graph.services.relationship_provider import RuleBasedRelationshipProvider
from app.knowledge_graph.services.relationship_builder import RelationshipBuilder
from app.knowledge_graph.services.relationship_extraction_service import RelationshipExtractionService
from app.knowledge_graph.dependencies.graph_deps import get_relationship_service, get_entity_service, get_graph_service
from app.infrastructure.repositories.sql_repos import SQLMemoryRepository, SQLUserRepository
from app.domain.entities import Memory, MemoryType, MemoryStatus
from app.domain.memory_system import MemorySystem

pytestmark = pytest.mark.asyncio


# ==============================================================================
# 1. UNIT & PROVIDER TESTS
# ==============================================================================

async def test_rule_based_relationship_provider():
    provider = RuleBasedRelationshipProvider()
    builder = RelationshipBuilder(provider)

    node_ame = Node(
        id=uuid.uuid4(), user_id=uuid.uuid4(), node_type=NodeType.ENTITY,
        name="AME", canonical_name="ame", entity_type=EntityType.PROJECT
    )
    node_fastapi = Node(
        id=uuid.uuid4(), user_id=uuid.uuid4(), node_type=NodeType.ENTITY,
        name="FastAPI", canonical_name="fastapi", entity_type=EntityType.FRAMEWORK
    )
    node_postgres = Node(
        id=uuid.uuid4(), user_id=uuid.uuid4(), node_type=NodeType.ENTITY,
        name="PostgreSQL", canonical_name="postgresql", entity_type=EntityType.DATABASE
    )
    node_pgvector = Node(
        id=uuid.uuid4(), user_id=uuid.uuid4(), node_type=NodeType.ENTITY,
        name="pgvector", canonical_name="pgvector", entity_type=EntityType.TECHNOLOGY
    )

    nodes = [node_ame, node_fastapi, node_postgres, node_pgvector]

    # Test sentence: "AME uses FastAPI and PostgreSQL. PostgreSQL indexed by pgvector."
    # This checks proximity extraction and coordinate objects: "uses" should connect AME to BOTH FastAPI and PostgreSQL.
    text = "AME uses FastAPI and PostgreSQL. PostgreSQL indexed by pgvector."
    triples = await builder.build_relationships(text, nodes)

    # We expect 3 relationships:
    # 1. AME --USES--> FastAPI
    # 2. AME --USES--> PostgreSQL
    # 3. PostgreSQL --INDEXED_BY--> pgvector
    assert len(triples) == 3

    # Check triple 1
    t1 = triples[0]
    assert t1["source_node"].name == "AME"
    assert t1["target_node"].name == "FastAPI"
    assert t1["relationship_type"] == RelationshipType.USES
    assert t1["confidence"] == 0.98
    assert t1["matched_pattern"] == "uses"
    assert t1["sentence_index"] == 0

    # Check triple 2
    t2 = triples[1]
    assert t2["source_node"].name == "AME"
    assert t2["target_node"].name == "PostgreSQL"
    assert t2["relationship_type"] == RelationshipType.USES
    assert t2["confidence"] == 0.98
    assert t2["matched_pattern"] == "uses"
    assert t2["sentence_index"] == 0

    # Check triple 3
    t3 = triples[2]
    assert t3["source_node"].name == "PostgreSQL"
    assert t3["target_node"].name == "pgvector"
    assert t3["relationship_type"] == RelationshipType.INDEXED_BY
    assert t3["confidence"] == 0.98
    assert t3["matched_pattern"] == "indexed by"
    assert t3["sentence_index"] == 1


# ==============================================================================
# 2. SELF-LOOP CONFIGURATION TESTS
# ==============================================================================

async def test_self_loops_configuration(db_session: AsyncSession):
    user_repo = SQLUserRepository(db_session)
    user = await user_repo.create(email="kg_loops@example.com", password_hash="hash")
    await db_session.flush()

    entity_service = get_entity_service(db_session)
    node = await entity_service.create_entity(
        user_id=user.id,
        name="FastAPI",
        entity_type=EntityType.FRAMEWORK
    )

    rel_service = get_relationship_service(db_session)

    # 1. Try creating a self-loop with prevent_self_loops=True -> Should raise ValueError
    with pytest.raises(ValueError, match="Self-referential loops are not allowed"):
        await rel_service.create_relationship(
            user_id=user.id,
            source_node_id=node.id,
            target_node_id=node.id,
            relationship_type=RelationshipType.USES,
            confidence=1.0,
            prevent_self_loops=True
        )

    # 2. Try creating a self-loop with prevent_self_loops=False -> Should succeed
    self_loop = await rel_service.create_relationship(
        user_id=user.id,
        source_node_id=node.id,
        target_node_id=node.id,
        relationship_type=RelationshipType.USES,
        confidence=1.0,
        prevent_self_loops=False
    )
    assert self_loop.source_node_id == self_loop.target_node_id


# ==============================================================================
# 3. RELATIONSHIP RESOLUTION & METADATA TESTS
# ==============================================================================

async def test_relationship_resolution_and_metadata(db_session: AsyncSession):
    user_repo = SQLUserRepository(db_session)
    user = await user_repo.create(email="kg_res_meta@example.com", password_hash="hash")
    await db_session.flush()

    entity_service = get_entity_service(db_session)
    n1 = await entity_service.create_entity(user.id, "AME", EntityType.PROJECT)
    n2 = await entity_service.create_entity(user.id, "FastAPI", EntityType.FRAMEWORK)

    rel_service = get_relationship_service(db_session)

    # 1. Resolve first time (creates relationship)
    r1 = await rel_service.resolve_relationship(
        user_id=user.id,
        source_node_id=n1.id,
        target_node_id=n2.id,
        relationship_type=RelationshipType.USES,
        confidence=0.98,
        metadata={"extraction_source": "rule_based", "sentence_index": 0}
    )

    # 2. Resolve second time (should reuse/return same relationship)
    r2 = await rel_service.resolve_relationship(
        user_id=user.id,
        source_node_id=n1.id,
        target_node_id=n2.id,
        relationship_type=RelationshipType.USES,
        confidence=0.98,
        metadata={"extraction_source": "rule_based", "sentence_index": 0}
    )
    assert r1.id == r2.id
    assert r2.metadata["extraction_source"] == "rule_based"
    assert r2.metadata["sentence_index"] == 0


# ==============================================================================
# 4. SERVICE WORKFLOW TESTS
# ==============================================================================

async def test_relationship_extraction_service_workflow(db_session: AsyncSession):
    user_repo = SQLUserRepository(db_session)
    user = await user_repo.create(email="kg_serv_workflow@example.com", password_hash="hash")
    await db_session.flush()

    entity_service = get_entity_service(db_session)
    n_ame = await entity_service.create_entity(user.id, "AME", EntityType.PROJECT)
    n_fastapi = await entity_service.create_entity(user.id, "FastAPI", EntityType.FRAMEWORK)

    memory_repo = SQLMemoryRepository(db_session)
    memory = await memory_repo.create(
        user_id=user.id,
        conversation_id=None,
        content="AME uses FastAPI.",
        memory_type=MemoryType.FACT,
        importance=0.5,
        confidence=0.8,
        status=MemoryStatus.ACTIVE,
        last_accessed_at=datetime.utcnow(),
        version=1,
        metadata={},
        memory_system=MemorySystem.SEMANTIC,
    )

    provider = RuleBasedRelationshipProvider()
    builder = RelationshipBuilder(provider)
    rel_service = get_relationship_service(db_session)

    extraction_service = RelationshipExtractionService(builder, rel_service)

    # Trigger relationship building
    relationships = await extraction_service.extract_and_build_relationships(
        user_id=user.id,
        memory_id=memory.id,
        content=memory.content,
        nodes=[n_ame, n_fastapi]
    )

    assert len(relationships) == 1
    rel = relationships[0]
    assert rel.source_node_id == n_ame.id
    assert rel.target_node_id == n_fastapi.id
    assert rel.relationship_type == RelationshipType.USES
    
    # Verify metadata contains extraction details
    assert rel.metadata["extraction_source"] == "rule_based"
    assert rel.metadata["source_memory_id"] == str(memory.id)
    assert rel.metadata["matched_pattern"] == "uses"
    assert rel.metadata["sentence_index"] == 0
    assert rel.metadata["confidence"] == 0.98


# ==============================================================================
# 5. API LAYER INTEGRATION TESTS
# ==============================================================================

async def test_kg_relationship_extraction_unauthorized(client: AsyncClient):
    memory_id = uuid.uuid4()
    resp = await client.post(f"/api/v1/memories/{memory_id}/relationships/extract")
    assert resp.status_code == 401


async def test_kg_manual_relationship_extraction(client: AsyncClient, db_session: AsyncSession):
    # 1. Register and Login
    await client.post(
        "/api/v1/auth/register",
        json={"email": "relapi@example.com", "password": "password123"}
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "relapi@example.com", "password": "password123"}
    )

    # 2. Create memory with multiple entities
    mem_resp = await client.post(
        "/api/v1/memories",
        json={
            "content": "AME uses FastAPI. FastAPI requires python.",
            "memory_type": "Fact",
            "importance": 0.5,
            "confidence": 0.9,
        }
    )
    assert mem_resp.status_code == 201
    mem_id = mem_resp.json()["id"]

    # 3. Trigger manual entity extraction first (creates nodes and maps them to memory)
    ent_extract_resp = await client.post(f"/api/v1/memories/{mem_id}/entities/extract")
    assert ent_extract_resp.status_code == 200

    # 4. Trigger manual relationship extraction on this memory
    rel_extract_resp = await client.post(f"/api/v1/memories/{mem_id}/relationships/extract")
    assert rel_extract_resp.status_code == 200
    relationships = rel_extract_resp.json()

    # Should resolve 2 relationships:
    # 1. AME --USES--> FastAPI
    # 2. FastAPI --DEPENDS_ON--> Python
    assert len(relationships) == 2
    types = [r["relationship_type"] for r in relationships]
    assert "USES" in types
    assert "DEPENDS_ON" in types

    # 5. Validate User B accessing User A's memory -> 403 Forbidden
    await client.post(
        "/api/v1/auth/register",
        json={"email": "relapiB@example.com", "password": "password123"}
    )
    client.cookies.clear()
    await client.post(
        "/api/v1/auth/login",
        json={"email": "relapiB@example.com", "password": "password123"}
    )

    rel_extract_resp_b = await client.post(f"/api/v1/memories/{mem_id}/relationships/extract")
    assert rel_extract_resp_b.status_code == 403
