"""API and persistence tests for hybrid memory Phase 1."""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.domain.entities import MemoryType
from app.domain.memory_system import MemorySystem
from app.infrastructure.db.models import MemoryTable, UserTable

pytestmark = pytest.mark.asyncio


async def test_create_memory_defaults_to_semantic_system(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "hybrid_default@example.com", "password": "password123"},
    )

    resp = await client.post(
        "/api/v1/memories",
        json={
            "content": "User prefers dark mode.",
            "memory_type": "Preference",
            "importance": 0.7,
            "confidence": 0.9,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["memory_system"] == "Semantic"
    assert data["occurred_at"] is None
    assert data["expires_at"] is None


async def test_create_episodic_memory_with_conversation(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "hybrid_episodic@example.com", "password": "password123"},
    )

    conv = await client.post("/api/v1/conversations", json={"title": "Episodic Conv"})
    conv_id = conv.json()["id"]
    occurred = datetime.now(timezone.utc).isoformat()

    resp = await client.post(
        "/api/v1/memories",
        json={
            "conversation_id": conv_id,
            "content": "User visited the museum on Saturday.",
            "memory_type": "Event",
            "memory_system": "Episodic",
            "occurred_at": occurred,
            "importance": 0.6,
            "confidence": 0.85,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["memory_system"] == "Episodic"
    assert data["conversation_id"] == conv_id
    assert data["occurred_at"] is not None


async def test_create_episodic_without_conversation_rejected(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "hybrid_episodic_fail@example.com", "password": "password123"},
    )

    resp = await client.post(
        "/api/v1/memories",
        json={
            "content": "An orphan episodic memory.",
            "memory_type": "Event",
            "memory_system": "Episodic",
            "importance": 0.5,
            "confidence": 0.5,
        },
    )
    assert resp.status_code == 422
    assert "conversation_id" in resp.json()["message"]


async def test_create_working_memory_auto_expiry(client: AsyncClient, db_session: AsyncSession):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "hybrid_working@example.com", "password": "password123"},
    )

    conv = await client.post("/api/v1/conversations", json={"title": "Working Conv"})
    conv_id = conv.json()["id"]

    resp = await client.post(
        "/api/v1/memories",
        json={
            "conversation_id": conv_id,
            "content": "Currently discussing project Alpha.",
            "memory_type": "Fact",
            "memory_system": "Working",
            "importance": 0.4,
            "confidence": 0.7,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["memory_system"] == "Working"
    assert data["expires_at"] is not None

    memory_id = uuid.UUID(data["id"])
    row = await db_session.get(MemoryTable, memory_id)
    assert row.memory_system == "Working"
    assert row.expires_at is not None


async def test_procedural_memory_persisted(client: AsyncClient, db_session: AsyncSession):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "hybrid_map@example.com", "password": "password123"},
    )

    user_id = (
        await db_session.execute(
            select(UserTable.id).where(UserTable.email == "hybrid_map@example.com")
        )
    ).scalar()

    proc = MemoryTable(
        id=uuid.uuid4(),
        user_id=user_id,
        content="User follows a morning standup routine.",
        memory_type=MemoryType.HABIT.value,
        memory_system=MemorySystem.PROCEDURAL.value,
        importance=0.5,
        confidence=0.8,
        status="ACTIVE",
        version=1,
    )
    db_session.add(proc)
    await db_session.commit()

    get_resp = await client.get(f"/api/v1/memories/{proc.id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["memory_system"] == "Procedural"


async def test_existing_memory_crud_regression_includes_memory_system(client: AsyncClient):
    """Existing CRUD flow continues to work with additive memory_system field."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "hybrid_regress@example.com", "password": "password123"},
    )

    create = await client.post(
        "/api/v1/memories",
        json={
            "content": "Regression fact.",
            "memory_type": "Fact",
            "importance": 0.5,
            "confidence": 0.8,
        },
    )
    assert create.status_code == 201
    memory_id = create.json()["id"]

    get_resp = await client.get(f"/api/v1/memories/{memory_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["memory_system"] == "Semantic"

    update = await client.put(
        f"/api/v1/memories/{memory_id}",
        json={"importance": 0.9},
    )
    assert update.status_code == 200
    assert update.json()["memory_system"] == "Semantic"
