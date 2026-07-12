"""Verification tests for hybrid memory Phase 6 (Production Readiness)."""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Memory, MemoryType, MemoryStatus
from app.domain.memory_system import MemorySystem
from app.infrastructure.repositories.sql_repos import SQLRepositoryFactory
from app.application.hybrid_retrieval_service import HybridRetrievalService
from app.application.hybrid_ranking_service import HybridRankingService
from app.application.ranking_service import RankingService
from app.application.memory_service import MemoryService
from app.infrastructure.db.models import UserTable, ConversationTable, MemoryTable

pytestmark = pytest.mark.asyncio


# =====================================================================
# 1. Dependency injection and Architecture Boundary Tests
# =====================================================================

async def test_di_wiring_consistency(db_session: AsyncSession):
    from app.presentation.api.memories import get_memory_service, get_ranking_service
    ranking_service = get_ranking_service()
    service = get_memory_service(db_session, ranking_service)

    # Assert all components are successfully wired and correct instances
    assert isinstance(service, MemoryService)
    assert isinstance(service.hybrid_retrieval_service, HybridRetrievalService)
    assert isinstance(service.hybrid_ranking_service, HybridRankingService)
    assert isinstance(service.hybrid_ranking_service.adaptive_ranking_service, RankingService)


# =====================================================================
# 2. Cross-User Data Authorization & Security Isolation Tests
# =====================================================================

async def test_api_hybrid_search_authorization_isolation(client: AsyncClient, db_session: AsyncSession):
    # 1. Register User A (sets cookie for User A)
    client.cookies.clear()
    await client.post(
        "/api/v1/auth/register",
        json={"email": "usera@example.com", "password": "password123"},
    )
    user_a_id = (
        await db_session.execute(
            select(UserTable.id).where(UserTable.email == "usera@example.com")
        )
    ).scalar()

    # 2. Register User B
    client.cookies.clear()
    await client.post(
        "/api/v1/auth/register",
        json={"email": "userb@example.com", "password": "password123"},
    )
    user_b_id = (
        await db_session.execute(
            select(UserTable.id).where(UserTable.email == "userb@example.com")
        )
    ).scalar()

    # Create memory for User B
    m_b = MemoryTable(
        id=uuid.uuid4(),
        user_id=user_b_id,
        content="Secret credential of User B",
        memory_type=MemoryType.FACT.value,
        memory_system=MemorySystem.SEMANTIC.value,
        importance=0.9,
        confidence=0.9,
        status="ACTIVE",
        version=1,
    )
    db_session.add(m_b)
    await db_session.commit()

    # 3. Log in User A
    client.cookies.clear()
    await client.post(
        "/api/v1/auth/login",
        json={"email": "usera@example.com", "password": "password123"},
    )

    # User A requests hybrid search
    resp = await client.get("/api/v1/memories/hybrid/search?systems=all")
    assert resp.status_code == 200
    data = resp.json()
    
    # Must NOT contain User B's secret memory
    contents = {m["content"] for m in data}
    assert "Secret credential of User B" not in contents


# =====================================================================
# 3. Backward Compatibility CRUD Tests
# =====================================================================

async def test_crud_backward_compatibility(client: AsyncClient, db_session: AsyncSession):
    # Register and automatically log in User A
    client.cookies.clear()
    await client.post(
        "/api/v1/auth/register",
        json={"email": "usera@example.com", "password": "password123"},
    )

    # Create a standard memory using the existing CRUD POST API
    resp_create = await client.post(
        "/api/v1/memories",
        json={
            "content": "Standard preference memory",
            "memory_type": "Preference",
            "importance": 0.7,
            "confidence": 0.8,
        },
    )
    assert resp_create.status_code == 201
    memory_id = resp_create.json()["id"]

    # Retrieve memory using standard GET API
    resp_get = await client.get(f"/api/v1/memories/{memory_id}")
    assert resp_get.status_code == 200
    assert resp_get.json()["content"] == "Standard preference memory"
