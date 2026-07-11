import uuid
import math
import pytest
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.domain.entities import MemoryType, MemoryStatus, MemoryState, MemorySourceType
from app.application.ranking_service import RankingService
from app.infrastructure.db.models import MemoryTable, MemoryStateTable, MemoryAccessLogTable


pytestmark = pytest.mark.asyncio


def test_ranking_calculations():
    """Verify that the RankingService formulas execute correctly and yield bounded scores."""
    service = RankingService(
        w_semantic=0.40,
        w_importance=0.15,
        w_recency=0.15,
        w_frequency=0.10,
        w_decay=0.10,
        w_confidence=0.10,
        recency_half_life_hours=24.0,  # 1 day half-life for tests
        frequency_threshold=10
    )

    # 1. Recency decay calculation
    # exactly 24 hours ago should be 0.5
    assert pytest.approx(service.calculate_recency_score(datetime.now(timezone.utc) - timedelta(hours=24)), 1e-6) == 0.5
    # brand new should be 1.0
    assert pytest.approx(service.calculate_recency_score(datetime.now(timezone.utc)), 1e-6) == 1.0

    # 2. Logarithmic frequency calculation
    # 0 access count -> 0.0
    assert service.calculate_frequency_score(0) == 0.0
    # count == threshold -> 1.0
    assert pytest.approx(service.calculate_frequency_score(10), 1e-6) == 1.0
    # count exceeding threshold should be capped at 1.0
    assert service.calculate_frequency_score(20) == 1.0
    # standard log ratio check: ln(2)/ln(11) for count 1
    assert pytest.approx(service.calculate_frequency_score(1), 1e-6) == math.log(2) / math.log(11)


async def test_automatic_state_initialization(client: AsyncClient, db_session: AsyncSession):
    """Verify that memory states are automatically initialized transactionally when a memory is created."""
    # 1. Register & login
    await client.post(
        "/api/v1/auth/register",
        json={"email": "stateinit@example.com", "password": "password123"}
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "stateinit@example.com", "password": "password123"}
    )

    # 2. Create memory
    resp = await client.post(
        "/api/v1/memories",
        json={
            "content": "User owns a blue kayak.",
            "memory_type": "Preference",
            "importance": 0.8,
            "confidence": 0.9,
        }
    )
    assert resp.status_code == 201
    memory_id = resp.json()["id"]

    # 3. Verify MemoryStateTable row exists and matches fields
    stmt = select(MemoryStateTable).where(MemoryStateTable.memory_id == uuid.UUID(memory_id))
    res = await db_session.execute(stmt)
    state = res.scalars().first()
    assert state is not None
    assert state.access_count == 0
    assert state.retrieval_count == 0
    assert state.decay_score == 0.0
    assert state.confidence_score == 0.9
    assert state.importance_score == 0.8
    assert state.source_type == "user"


async def test_retrieval_pipeline_and_access_logging(client: AsyncClient, db_session: AsyncSession):
    """Verify that semantic search triggers access logging and updates stats in the memory state."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "loggingtest@example.com", "password": "password123"}
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "loggingtest@example.com", "password": "password123"}
    )

    # Create memory
    resp = await client.post(
        "/api/v1/memories",
        json={
            "content": "User lives in a brick house.",
            "memory_type": "Fact",
            "importance": 0.5,
            "confidence": 0.8,
        }
    )
    memory_id = uuid.UUID(resp.json()["id"])

    # Trigger retrieval by searching memories
    # The search endpoint retrieves memories using RetrievalService
    search_resp = await client.get("/api/v1/memories/search?query=brick house&top_k=2")
    assert search_resp.status_code == 200

    # Wait for session teardown or force transaction flush to read log
    db_session.expire_all()
    
    # Verify access logs table got an entry
    log_stmt = select(MemoryAccessLogTable).where(MemoryAccessLogTable.memory_id == memory_id)
    log_res = await db_session.execute(log_stmt)
    logs = list(log_res.scalars().all())
    assert len(logs) >= 1
    assert logs[0].retrieval_success is True

    # Verify memory state stats incremented
    state_stmt = select(MemoryStateTable).where(MemoryStateTable.memory_id == memory_id)
    state_res = await db_session.execute(state_stmt)
    state = state_res.scalars().first()
    assert state.access_count >= 1
    assert state.retrieval_count >= 1

    # Call diagnostics api to inspect logs
    diag_resp = await client.get(f"/api/v1/memories/{memory_id}/analytics")
    assert diag_resp.status_code == 200
    diag_data = diag_resp.json()
    assert diag_data["memory_id"] == str(memory_id)
    assert diag_data["state"]["access_count"] >= 1
    assert len(diag_data["access_logs"]) >= 1


async def test_manual_and_stream_reinforcement(client: AsyncClient, db_session: AsyncSession):
    """Verify that successful assistant response delivery reinforces retrieval memories, while failure does not."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "reinforcetest@example.com", "password": "password123"}
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "reinforcetest@example.com", "password": "password123"}
    )

    # 1. Create a memory and get its ID
    resp = await client.post(
        "/api/v1/memories",
        json={
            "content": "User loves chocolate ice cream.",
            "memory_type": "Preference",
            "importance": 0.60,
            "confidence": 0.90,
        }
    )
    memory_id = uuid.UUID(resp.json()["id"])

    # 2. Trigger manual reinforcement endpoint
    m_resp = await client.post(f"/api/v1/memories/{memory_id}/reinforce")
    assert m_resp.status_code == 200

    # Verify reinforcement results: reinforcement_count incremented, importance increased
    db_session.expire_all()
    state_stmt = select(MemoryStateTable).where(MemoryStateTable.memory_id == memory_id)
    state_res = await db_session.execute(state_stmt)
    state = state_res.scalars().first()
    assert state.reinforcement_count == 1
    # 0.60 + 0.02 = 0.62
    assert pytest.approx(state.importance_score, 1e-6) == 0.62
    assert state.decay_score == 0.0

    # 3. Test chat context enrichment success reinforcement
    conv_resp = await client.post("/api/v1/conversations", json={"title": "Reinforce Chat"})
    conv_id = conv_resp.json()["id"]

    # Submit a message which retrieves our memory
    msg_resp = await client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "What ice cream do I like?"}
    )
    assert msg_resp.status_code == 200
    
    # Read the full SSE stream to finish delivery (so callback runs)
    async for _ in msg_resp.aiter_lines():
        pass

    # Verify that reinforcement was automatically applied on successful delivery
    db_session.expire_all()
    state_res2 = await db_session.execute(state_stmt)
    state2 = state_res2.scalars().first()
    assert state2.reinforcement_count == 2
    # 0.62 + 0.02 = 0.64
    assert pytest.approx(state2.importance_score, 1e-6) == 0.64


async def test_decay_mechanism(client: AsyncClient, db_session: AsyncSession):
    """Verify that idle memories decay over time and manual/automatic endpoints trigger decay scores updates."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "decaytest@example.com", "password": "password123"}
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "decaytest@example.com", "password": "password123"}
    )

    # 1. Create a memory
    resp = await client.post(
        "/api/v1/memories",
        json={
            "content": "User owns a red bicycle.",
            "memory_type": "Fact",
            "importance": 0.5,
            "confidence": 0.8,
        }
    )
    memory_id = uuid.UUID(resp.json()["id"])

    # 2. Modify last_accessed_at in the database to simulate 100 hours of idle time
    state_stmt = select(MemoryStateTable).where(MemoryStateTable.memory_id == memory_id)
    state_res = await db_session.execute(state_stmt)
    state = state_res.scalars().first()
    
    past_time = datetime.now(timezone.utc) - timedelta(hours=100)
    state.last_accessed_at = past_time
    state.last_reinforced_at = None
    await db_session.commit()

    # 3. Trigger manual decay cycle route
    decay_resp = await client.post("/api/v1/memories/decay")
    assert decay_resp.status_code == 200
    assert decay_resp.json()["updated_count"] == 1

    # Verify that decay score has been updated
    # Formula: 1.0 - exp(-0.004 * 100) = 1.0 - exp(-0.4) = ~0.329679
    db_session.expire_all()
    state_res_after = await db_session.execute(state_stmt)
    state_after = state_res_after.scalars().first()
    expected_decay = 1.0 - math.exp(-0.004 * 100)
    assert pytest.approx(state_after.decay_score, 1e-4) == expected_decay
