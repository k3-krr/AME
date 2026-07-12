"""Unit and integration tests for hybrid retrieval Phase 4."""

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.domain.entities import Memory, MemoryType, MemoryStatus
from app.domain.memory_system import MemorySystem
from app.infrastructure.repositories.sql_repos import (
    SQLRepositoryFactory,
    SQLSemanticMemoryRepository,
    SQLEpisodicMemoryRepository,
)
from app.application.hybrid_retrieval_service import HybridRetrievalService
from app.application.memory_service import MemoryService
from app.infrastructure.db.models import UserTable, ConversationTable, MemoryTable

pytestmark = pytest.mark.asyncio


# =====================================================================
# 1. HybridRetrievalService Unit & Fail-safe Tests
# =====================================================================

async def test_hybrid_search_deduplication():
    # Setup mock factory and repositories
    factory = AsyncMock(spec=SQLRepositoryFactory)
    repo_semantic = AsyncMock(spec=SQLSemanticMemoryRepository)
    repo_episodic = AsyncMock(spec=SQLEpisodicMemoryRepository)

    factory.get.side_effect = lambda sys: {
        MemorySystem.SEMANTIC: repo_semantic,
        MemorySystem.EPISODIC: repo_episodic,
    }[sys]

    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # Return duplicate memory from both semantic and episodic
    dup_id = uuid.uuid4()
    dup_memory = Memory(
        id=dup_id,
        user_id=user_id,
        content="Shared context memory",
        memory_type=MemoryType.FACT,
        importance=0.5,
        confidence=0.8,
        status=MemoryStatus.ACTIVE,
        created_at=now,
        updated_at=now,
        last_accessed_at=now,
    )

    repo_semantic.retrieve_semantic.return_value = [dup_memory]
    repo_episodic.retrieve_episodic.return_value = [dup_memory]

    service = HybridRetrievalService(factory)
    
    # Query semantic and episodic systems
    results = await service.search_hybrid(
        user_id=user_id,
        systems=[MemorySystem.SEMANTIC, MemorySystem.EPISODIC]
    )

    # Should merge and return exactly one memory record
    assert len(results) == 1
    assert results[0].id == dup_id


async def test_hybrid_search_repository_failures_resilience():
    # Setup mock factory where semantic repo succeeds and episodic repo raises an error
    factory = AsyncMock(spec=SQLRepositoryFactory)
    repo_semantic = AsyncMock(spec=SQLSemanticMemoryRepository)
    repo_episodic = AsyncMock(spec=SQLEpisodicMemoryRepository)

    factory.get.side_effect = lambda sys: {
        MemorySystem.SEMANTIC: repo_semantic,
        MemorySystem.EPISODIC: repo_episodic,
    }[sys]

    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mem_semantic = Memory(
        id=uuid.uuid4(),
        user_id=user_id,
        content="Semantic information",
        memory_type=MemoryType.FACT,
        importance=0.5,
        confidence=0.8,
        status=MemoryStatus.ACTIVE,
        created_at=now,
        updated_at=now,
        last_accessed_at=now,
    )

    repo_semantic.retrieve_semantic.return_value = [mem_semantic]
    # Simulate database connection failure or query syntax error in Episodic repo
    repo_episodic.retrieve_episodic.side_effect = RuntimeError("Database timeout connection error")

    service = HybridRetrievalService(factory)

    # Execute search
    results = await service.search_hybrid(
        user_id=user_id,
        systems=[MemorySystem.SEMANTIC, MemorySystem.EPISODIC]
    )

    # Must survive and return semantic memory successfully
    assert len(results) == 1
    assert results[0].content == "Semantic information"


# =====================================================================
# 2. REST API Endpoint Integration Tests
# =====================================================================

async def test_api_hybrid_search_filters_and_auth(client: AsyncClient, db_session: AsyncSession):
    # Setup User and Conversation
    await client.post(
        "/api/v1/auth/register",
        json={"email": "hybrid_search_api@example.com", "password": "password123"},
    )
    user_id = (
        await db_session.execute(
            select(UserTable.id).where(UserTable.email == "hybrid_search_api@example.com")
        )
    ).scalar()

    conv_resp = await client.post("/api/v1/conversations", json={"title": "Hybrid Search API"})
    conv_id = uuid.UUID(conv_resp.json()["id"])

    # Create semantic memory
    m_semantic = MemoryTable(
        id=uuid.uuid4(),
        user_id=user_id,
        content="Apple makes iPhone devices",
        memory_type=MemoryType.FACT.value,
        memory_system=MemorySystem.SEMANTIC.value,
        importance=0.9,
        confidence=0.95,
        status="ACTIVE",
        version=1,
    )
    # Create episodic memory
    m_episodic = MemoryTable(
        id=uuid.uuid4(),
        user_id=user_id,
        conversation_id=conv_id,
        content="User visited Apple Store in 2026",
        memory_type=MemoryType.EVENT.value,
        memory_system=MemorySystem.EPISODIC.value,
        importance=0.8,
        confidence=0.9,
        status="ACTIVE",
        version=1,
        occurred_at=datetime.now(timezone.utc),
    )
    db_session.add(m_semantic)
    db_session.add(m_episodic)
    await db_session.commit()

    # 1. Search all systems
    resp_all = await client.get("/api/v1/memories/hybrid/search?systems=all")
    assert resp_all.status_code == 200
    data_all = resp_all.json()
    assert len(data_all) == 2
    contents = {m["content"] for m in data_all}
    assert "Apple makes iPhone devices" in contents
    assert "User visited Apple Store in 2026" in contents

    # 2. Search only semantic system
    resp_sem = await client.get("/api/v1/memories/hybrid/search?systems=semantic")
    assert resp_sem.status_code == 200
    data_sem = resp_sem.json()
    assert len(data_sem) == 1
    assert data_sem[0]["content"] == "Apple makes iPhone devices"

    # 3. Search only episodic system
    resp_ep = await client.get("/api/v1/memories/hybrid/search?systems=episodic")
    assert resp_ep.status_code == 200
    data_ep = resp_ep.json()
    assert len(data_ep) == 1
    assert data_ep[0]["content"] == "User visited Apple Store in 2026"

    # 4. Keyword filter check (returns only episodic matching "Store")
    resp_kw = await client.get("/api/v1/memories/hybrid/search?query=Store")
    assert resp_kw.status_code == 200
    data_kw = resp_kw.json()
    assert len(data_kw) == 1
    assert data_kw[0]["content"] == "User visited Apple Store in 2026"
