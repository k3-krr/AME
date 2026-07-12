import pytest
import uuid
import asyncio
from datetime import datetime
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_graph.domain.entities import Node, NodeType, EntityType, Relationship, RelationshipType, MemoryNodeMapping
from app.knowledge_graph.models.models import NodeTable, RelationshipTable, MemoryNodeMappingTable
from app.knowledge_graph.services.extraction_provider import RuleBasedProvider
from app.knowledge_graph.services.entity_extractor import EntityExtractor
from app.knowledge_graph.services.entity_extraction_service import EntityExtractionService
from app.knowledge_graph.dependencies.graph_deps import get_entity_service, get_graph_service
from app.infrastructure.repositories.sql_repos import SQLMemoryRepository, SQLUserRepository
from app.domain.entities import Memory, MemoryType, MemoryStatus
from app.domain.memory_system import MemorySystem

pytestmark = pytest.mark.asyncio


# ==============================================================================
# 1. UNIT & PROVIDER TESTS
# ==============================================================================

async def test_rule_based_provider_extraction():
    provider = RuleBasedProvider()
    
    # Check technology and framework matching
    text1 = "I am writing python code using FastAPI and postgres."
    res1 = await provider.extract_entities(text1)
    
    extracted_names = [r["name"].lower() for r in res1]
    assert "python" in extracted_names
    assert "fastapi" in extracted_names
    assert "postgres" in extracted_names

    # Check overlapping match resolution: "OpenAI API" (API) should be matched over "OpenAI" (Organization)
    text2 = "We interface with the OpenAI API."
    res2 = await provider.extract_entities(text2)
    assert len(res2) == 1
    assert res2[0]["name"].lower() == "openai api"
    assert res2[0]["entity_type"] == EntityType.API

    # Empty text check
    assert await provider.extract_entities("") == []
    assert await provider.extract_entities("   ") == []


async def test_extractor_canonicalization_and_aliases():
    provider = RuleBasedProvider()
    extractor = EntityExtractor(provider)
    
    # Check casing standardizations and aliases
    text = "We use postgres database, js scripts, and ts code inside fast api."
    extracted = await extractor.extract(text)
    
    # Verify canonical name translations
    names = [e["name"] for e in extracted]
    assert "PostgreSQL" in names  # postgres -> PostgreSQL
    assert "JavaScript" in names  # js -> JavaScript
    assert "TypeScript" in names  # ts -> TypeScript
    assert "FastAPI" in names     # fast api -> FastAPI


# ==============================================================================
# 2. REPOSITORY & RESOLUTION TESTS (Node Reuse / Mapping Uniqueness)
# ==============================================================================

async def test_node_resolution_reuse(db_session: AsyncSession):
    user_repo = SQLUserRepository(db_session)
    user = await user_repo.create(email="kg_reuse@example.com", password_hash="hash")
    await db_session.flush()

    entity_service = get_entity_service(db_session)

    # 1. Resolve first time (creates node)
    node1 = await entity_service.resolve_entity(
        user_id=user.id,
        name="postgres",
        entity_type=EntityType.DATABASE
    )
    assert node1.canonical_name == "postgresql"

    # 2. Resolve second time with alias/diff casing (should return the SAME node)
    node2 = await entity_service.resolve_entity(
        user_id=user.id,
        name="PostgreSQL",
        entity_type=EntityType.DATABASE
    )
    assert node1.id == node2.id


async def test_mapping_persistence_and_duplicate_prevention(db_session: AsyncSession):
    user_repo = SQLUserRepository(db_session)
    user = await user_repo.create(email="kg_map@example.com", password_hash="hash")
    await db_session.flush()

    memory_repo = SQLMemoryRepository(db_session)
    memory = await memory_repo.create(
        user_id=user.id,
        conversation_id=None,
        content="Testing python framework",
        memory_type=MemoryType.FACT,
        importance=0.5,
        confidence=0.8,
        status=MemoryStatus.ACTIVE,
        last_accessed_at=datetime.utcnow(),
        version=1,
        metadata={},
        memory_system=MemorySystem.SEMANTIC,
    )

    entity_service = get_entity_service(db_session)
    node = await entity_service.resolve_entity(
        user_id=user.id,
        name="FastAPI",
        entity_type=EntityType.FRAMEWORK
    )

    graph_service = get_graph_service(db_session)

    # 1. Create memory mapping
    map1 = await graph_service.create_memory_node_mapping(
        user_id=user.id,
        memory_id=memory.id,
        node_id=node.id,
        confidence=1.0
    )
    assert map1 is not None

    # 2. Create duplicate mapping (should return same mapping without throwing error)
    map2 = await graph_service.create_memory_node_mapping(
        user_id=user.id,
        memory_id=memory.id,
        node_id=node.id,
        confidence=1.0
    )
    assert map1.memory_id == map2.memory_id
    assert map1.node_id == map2.node_id


# ==============================================================================
# 3. SERVICE WORKFLOW TESTS
# ==============================================================================

async def test_entity_extraction_service_workflow(db_session: AsyncSession):
    user_repo = SQLUserRepository(db_session)
    user = await user_repo.create(email="kg_serv@example.com", password_hash="hash")
    await db_session.flush()

    memory_repo = SQLMemoryRepository(db_session)
    memory = await memory_repo.create(
        user_id=user.id,
        conversation_id=None,
        content="We built AME using python and fastapi.",
        memory_type=MemoryType.FACT,
        importance=0.5,
        confidence=0.8,
        status=MemoryStatus.ACTIVE,
        last_accessed_at=datetime.utcnow(),
        version=1,
        metadata={},
        memory_system=MemorySystem.SEMANTIC,
    )

    provider = RuleBasedProvider()
    extractor = EntityExtractor(provider)
    entity_service = get_entity_service(db_session)
    graph_service = get_graph_service(db_session)

    extraction_service = EntityExtractionService(extractor, entity_service, graph_service)

    # Trigger extraction and mapping
    node_ids = await extraction_service.extract_and_map_entities(
        user_id=user.id,
        memory_id=memory.id,
        content=memory.content
    )

    # Should match "AME", "python", "fastapi"
    assert len(node_ids) == 3

    # Verify nodes exist in database
    resolved_nodes = await entity_service.list_entities(user.id)
    assert len(resolved_nodes) == 3
    node_names = [n.name for n in resolved_nodes]
    assert "AME" in node_names
    assert "Python" in node_names
    assert "FastAPI" in node_names


# ==============================================================================
# 4. API LAYER INTEGRATION TESTS
# ==============================================================================

async def test_kg_extraction_unauthorized(client: AsyncClient):
    # Endpoint requires auth
    memory_id = uuid.uuid4()
    resp = await client.post(f"/api/v1/memories/{memory_id}/entities/extract")
    assert resp.status_code == 401


async def test_kg_manual_extraction_from_memory(client: AsyncClient, db_session: AsyncSession):
    # 1. Register and Login
    await client.post(
        "/api/v1/auth/register",
        json={"email": "manualextract@example.com", "password": "password123"}
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "manualextract@example.com", "password": "password123"}
    )

    # 2. Create memory manually
    mem_resp = await client.post(
        "/api/v1/memories",
        json={
            "content": "I am working with python, redis, and django.",
            "memory_type": "Fact",
            "importance": 0.5,
            "confidence": 0.9,
        }
    )
    assert mem_resp.status_code == 201
    mem_id = mem_resp.json()["id"]

    # 3. Trigger manual entity extraction on this memory
    extract_resp = await client.post(f"/api/v1/memories/{mem_id}/entities/extract")
    assert extract_resp.status_code == 200
    entities = extract_resp.json()
    
    # Should resolve "Python", "Redis", "Django"
    assert len(entities) == 3
    names = [e["name"] for e in entities]
    assert "Python" in names
    assert "Redis" in names
    assert "Django" in names

    # 4. Try User B accessing User A's memory -> 403 Forbidden
    await client.post(
        "/api/v1/auth/register",
        json={"email": "manualextractB@example.com", "password": "password123"}
    )
    client.cookies.clear()
    await client.post(
        "/api/v1/auth/login",
        json={"email": "manualextractB@example.com", "password": "password123"}
    )

    extract_resp_b = await client.post(f"/api/v1/memories/{mem_id}/entities/extract")
    assert extract_resp_b.status_code == 403
