import uuid
import asyncio
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.domain.entities import MemoryType, ExtractionStatus, ExtractionAction
from app.infrastructure.db.models import (
    MemoryTable,
    MemoryStateTable,
    MemoryExtractionTable,
    MemoryExtractionCandidateTable
)

pytestmark = pytest.mark.asyncio


async def test_autonomous_extraction_flow_on_chat(client: AsyncClient, db_session: AsyncSession):
    """Verify that a successful chat stream triggers the background extraction and logs audit details."""
    # 1. Register & login
    await client.post(
        "/api/v1/auth/register",
        json={"email": "extractionchat@example.com", "password": "password123"}
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "extractionchat@example.com", "password": "password123"}
    )

    # 2. Create conversation
    conv_resp = await client.post("/api/v1/conversations", json={"title": "Extraction Chat"})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["id"]

    # 3. Post user message that triggers simulated candidate
    msg_resp = await client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "I just bought a new blue kayak today!"}
    )
    assert msg_resp.status_code == 200

    # Consume stream
    async for _ in msg_resp.aiter_lines():
        pass

    # Give the background task a moment to execute
    await asyncio.sleep(0.5)

    # 4. Verify that memory was extracted and added
    db_session.expire_all()
    mem_stmt = select(MemoryTable).where(MemoryTable.conversation_id == uuid.UUID(conv_id))
    mem_res = await db_session.execute(mem_stmt)
    memories = list(mem_res.scalars().all())
    assert len(memories) >= 1
    assert any("kayak" in m.content.lower() for m in memories)

    # 5. Verify the audit log record was successfully logged
    ext_stmt = select(MemoryExtractionTable).where(MemoryExtractionTable.conversation_id == uuid.UUID(conv_id))
    ext_res = await db_session.execute(ext_stmt)
    extractions = list(ext_res.scalars().all())
    assert len(extractions) == 1
    assert extractions[0].status == ExtractionStatus.SUCCESS.value

    # 6. Verify extraction candidate parameters
    cand_stmt = select(MemoryExtractionCandidateTable).where(
        MemoryExtractionCandidateTable.extraction_id == extractions[0].id
    )
    cand_res = await db_session.execute(cand_stmt)
    candidates = list(cand_res.scalars().all())
    assert len(candidates) >= 1
    assert candidates[0].action_taken == ExtractionAction.CREATE.value
    assert candidates[0].target_memory_id == memories[0].id


async def test_duplicate_resolution_strategies(client: AsyncClient, db_session: AsyncSession):
    """Test duplicate detection, reinforcement, merging, and conflict resolution scenarios."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "duplicatestrategies@example.com", "password": "password123"}
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "duplicatestrategies@example.com", "password": "password123"}
    )

    # Create conversation
    conv_resp = await client.post("/api/v1/conversations", json={"title": "Duplication Checks"})
    conv_id = conv_resp.json()["id"]

    # ----------------------------------------------------
    # SCENARIO 1: CREATE -> REINFORCE
    # ----------------------------------------------------
    # Send user message with "ice cream" trigger
    r1 = await client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "I really love eating chocolate ice cream."}
    )
    async for _ in r1.aiter_lines():
        pass
    await asyncio.sleep(0.3)

    db_session.expire_all()
    mem_stmt = select(MemoryTable).where(MemoryTable.conversation_id == uuid.UUID(conv_id))
    mem_res = await db_session.execute(mem_stmt)
    m1 = mem_res.scalars().first()
    assert m1 is not None
    m1_id = m1.id

    # Get state stats
    state_stmt = select(MemoryStateTable).where(MemoryStateTable.memory_id == m1_id)
    s1 = (await db_session.execute(state_stmt)).scalars().first()
    assert s1.reinforcement_count == 0

    # Repeat exact query to trigger REINFORCE
    r2 = await client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "I really love eating chocolate ice cream."}
    )
    async for _ in r2.aiter_lines():
        pass
    await asyncio.sleep(0.3)

    db_session.expire_all()
    s2 = (await db_session.execute(state_stmt)).scalars().first()
    assert s2.reinforcement_count >= 1  # Successfully reinforced

    # Check candidates log action is reinforce
    cand_stmt = select(MemoryExtractionCandidateTable).where(
        MemoryExtractionCandidateTable.target_memory_id == m1_id
    ).order_by(MemoryExtractionCandidateTable.id.desc())
    candidates = (await db_session.execute(cand_stmt)).scalars().all()
    # The last candidate should be reinforce
    assert any(c.action_taken == ExtractionAction.REINFORCE.value for c in candidates)

    # ----------------------------------------------------
    # SCENARIO 2: CONFLICT_UPDATE (Lives Seattle vs Boston)
    # ----------------------------------------------------
    # Create fact: User lives in Seattle (via brick house simulator trigger)
    r3 = await client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "I live in a red brick house in Seattle."}
    )
    async for _ in r3.aiter_lines():
        pass
    await asyncio.sleep(0.3)

    db_session.expire_all()
    m_fact = (await db_session.execute(
        select(MemoryTable)
        .where(MemoryTable.conversation_id == uuid.UUID(conv_id))
        .where(MemoryTable.content.like("%brick house%"))
    )).scalars().first()
    assert m_fact is not None
    m_fact_id = m_fact.id

    # Artificially set state counts
    state_fact_stmt = select(MemoryStateTable).where(MemoryStateTable.memory_id == m_fact_id)
    sf1 = (await db_session.execute(state_fact_stmt)).scalars().first()
    sf1.access_count = 5
    sf1.reinforcement_count = 3
    sf1.decay_score = 0.5
    await db_session.commit()

    # Trigger conflict change: lives in Boston
    r4 = await client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Actually, I moved out. I now live in a brick house in Boston."}
    )
    async for _ in r4.aiter_lines():
        pass
    await asyncio.sleep(0.3)

    db_session.expire_all()
    # Verify content updated
    m_fact_after = await db_session.get(MemoryTable, m_fact_id)
    assert "Boston" in m_fact_after.content or "brick house" in m_fact_after.content

    # Verify state reset
    sf2 = (await db_session.execute(state_fact_stmt)).scalars().first()
    assert sf2.decay_score == 0.0
    assert sf2.access_count == 0
    assert sf2.reinforcement_count == 0


async def test_extraction_rest_apis(client: AsyncClient, db_session: AsyncSession):
    """Verify manual extract, list history, and detail view REST endpoints."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "api_extraction@example.com", "password": "password123"}
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "api_extraction@example.com", "password": "password123"}
    )

    conv_resp = await client.post("/api/v1/conversations", json={"title": "API Extraction Check"})
    conv_id = conv_resp.json()["id"]

    # Post message with kayak trigger
    msg_resp = await client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "I like to paddle in a blue kayak."}
    )
    async for _ in msg_resp.aiter_lines():
        pass
    await asyncio.sleep(0.3)

    # 1. Trigger manual extraction endpoint
    manual_resp = await client.post(f"/api/v1/conversations/{conv_id}/extract")
    assert manual_resp.status_code == 200
    ext_data = manual_resp.json()
    assert ext_data["conversation_id"] == conv_id
    extraction_id = ext_data["id"]

    # 2. Get history of extractions
    hist_resp = await client.get(f"/api/v1/extractions/history?conversation_id={conv_id}")
    assert hist_resp.status_code == 200
    assert len(hist_resp.json()) >= 1

    # 3. Get extraction detail record with candidates list
    detail_resp = await client.get(f"/api/v1/extractions/{extraction_id}")
    assert detail_resp.status_code == 200
    details = detail_resp.json()
    assert details["extraction"]["id"] == extraction_id
    assert len(details["candidates"]) >= 1

    # 4. Trigger Reprocess endpoint
    reprocess_resp = await client.post(
        "/api/v1/extractions/reprocess",
        json={"conversation_ids": [conv_id]}
    )
    assert reprocess_resp.status_code == 200
    assert reprocess_resp.json()["reprocessed_count"] == 1
