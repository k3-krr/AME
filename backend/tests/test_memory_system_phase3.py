"""Unit and integration tests for hybrid memory Phase 3."""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.domain.entities import Memory, MemoryType, MemoryStatus
from app.domain.memory_system import MemorySystem
from app.domain.repositories import (
    ISemanticMemoryRepository,
    IEpisodicMemoryRepository,
    IProceduralMemoryRepository,
    IWorkingMemoryRepository,
)
from app.infrastructure.repositories.sql_repos import (
    SQLMemoryRepository,
    SQLSemanticMemoryRepository,
    SQLEpisodicMemoryRepository,
    SQLProceduralMemoryRepository,
    SQLWorkingMemoryRepository,
    SQLRepositoryFactory,
)
from app.infrastructure.db.models import MemoryTable, MemoryStateTable, UserTable, ConversationTable

pytestmark = pytest.mark.asyncio


# =====================================================================
# 1. Repository Inheritance & Contract Tests
# =====================================================================

async def test_repository_inheritance():
    # Assert concrete classes subclass both their domain contract interface and SQLMemoryRepository
    assert issubclass(SQLSemanticMemoryRepository, SQLMemoryRepository)
    assert issubclass(SQLSemanticMemoryRepository, ISemanticMemoryRepository)

    assert issubclass(SQLEpisodicMemoryRepository, SQLMemoryRepository)
    assert issubclass(SQLEpisodicMemoryRepository, IEpisodicMemoryRepository)

    assert issubclass(SQLProceduralMemoryRepository, SQLMemoryRepository)
    assert issubclass(SQLProceduralMemoryRepository, IProceduralMemoryRepository)

    assert issubclass(SQLWorkingMemoryRepository, SQLMemoryRepository)
    assert issubclass(SQLWorkingMemoryRepository, IWorkingMemoryRepository)


# =====================================================================
# 2. Semantic Repository Tests
# =====================================================================

async def test_semantic_repository_filtering(db_session: AsyncSession):
    # Setup test user
    user = UserTable(email="semantic_repo_test@example.com", password_hash="hash")
    db_session.add(user)
    await db_session.commit()

    repo = SQLSemanticMemoryRepository(db_session)
    now = datetime.now(timezone.utc)

    # Create semantic and episodic memories
    m1 = await repo.create(
        user_id=user.id,
        conversation_id=None,
        content="User likes dark theme",
        memory_type=MemoryType.PREFERENCE,
        importance=0.8,
        confidence=0.9,
        status=MemoryStatus.ACTIVE,
        last_accessed_at=now,
        version=1,
        metadata={},
        memory_system=MemorySystem.SEMANTIC,
    )
    m2 = await repo.create(
        user_id=user.id,
        conversation_id=None,
        content="Earth rotates around Sun",
        memory_type=MemoryType.FACT,
        importance=0.9,
        confidence=1.0,
        status=MemoryStatus.ACTIVE,
        last_accessed_at=now,
        version=1,
        metadata={},
        memory_system=MemorySystem.SEMANTIC,
    )
    m3 = await repo.create(
        user_id=user.id,
        conversation_id=None,
        content="Earth rotates around Sun (goal)",
        memory_type=MemoryType.GOAL,
        importance=0.9,
        confidence=1.0,
        status=MemoryStatus.ACTIVE,
        last_accessed_at=now,
        version=1,
        metadata={},
        memory_system=MemorySystem.SEMANTIC,
    )
    # Episodic memory to verify filtering
    await repo.create(
        user_id=user.id,
        conversation_id=uuid.uuid4(),  # placeholder
        content="User checked in at the airport",
        memory_type=MemoryType.EVENT,
        importance=0.7,
        confidence=0.8,
        status=MemoryStatus.ACTIVE,
        last_accessed_at=now,
        version=1,
        metadata={},
        memory_system=MemorySystem.EPISODIC,
        occurred_at=now,
    )

    # 1. Test listing semantic memories only
    semantic_list = await repo.list_semantic_memories(user_id=user.id)
    assert len(semantic_list) == 3
    assert all(m.memory_system == MemorySystem.SEMANTIC for m in semantic_list)

    # 2. Test filtering by specific MemoryType list
    by_types = await repo.get_semantic_memories_by_type(
        user_id=user.id, memory_types=[MemoryType.PREFERENCE, MemoryType.GOAL]
    )
    assert len(by_types) == 2
    types_found = {m.memory_type for m in by_types}
    assert MemoryType.PREFERENCE in types_found
    assert MemoryType.GOAL in types_found


# =====================================================================
# 3. Episodic Repository Tests
# =====================================================================

async def test_episodic_repository_timeline(db_session: AsyncSession):
    # Setup test user and conversation
    user = UserTable(email="episodic_repo_test@example.com", password_hash="hash")
    db_session.add(user)
    await db_session.commit()

    conv = ConversationTable(user_id=user.id, title="Trip Conv", system_prompt="Prompt")
    db_session.add(conv)
    await db_session.commit()

    repo = SQLEpisodicMemoryRepository(db_session)
    now = datetime.now(timezone.utc)

    # Create episodic memories with progressive occurred_at timestamps
    time1 = now - timedelta(days=5)
    time2 = now - timedelta(days=2)
    time3 = now - timedelta(hours=1)

    # Inserting in unsorted order to verify chronological sorting (ascending occurred_at)
    m_latest = await repo.create(
        user_id=user.id,
        conversation_id=conv.id,
        content="Event 3 happened",
        memory_type=MemoryType.EVENT,
        importance=0.6,
        confidence=0.8,
        status=MemoryStatus.ACTIVE,
        last_accessed_at=now,
        version=1,
        metadata={},
        memory_system=MemorySystem.EPISODIC,
        occurred_at=time3,
    )
    m_earliest = await repo.create(
        user_id=user.id,
        conversation_id=conv.id,
        content="Event 1 happened",
        memory_type=MemoryType.EVENT,
        importance=0.6,
        confidence=0.8,
        status=MemoryStatus.ACTIVE,
        last_accessed_at=now,
        version=1,
        metadata={},
        memory_system=MemorySystem.EPISODIC,
        occurred_at=time1,
    )
    m_middle = await repo.create(
        user_id=user.id,
        conversation_id=conv.id,
        content="Event 2 happened",
        memory_type=MemoryType.EVENT,
        importance=0.6,
        confidence=0.8,
        status=MemoryStatus.ACTIVE,
        last_accessed_at=now,
        version=1,
        metadata={},
        memory_system=MemorySystem.EPISODIC,
        occurred_at=time2,
    )

    # 1. Timeline check - chronological (earliest first)
    timeline = await repo.get_timeline(user_id=user.id)
    assert len(timeline) == 3
    assert timeline[0].id == m_earliest.id
    assert timeline[1].id == m_middle.id
    assert timeline[2].id == m_latest.id

    # 2. Date filtering check
    filtered_timeline = await repo.get_timeline(
        user_id=user.id,
        start_time=now - timedelta(days=4),
        end_time=now - timedelta(days=1),
    )
    assert len(filtered_timeline) == 1
    assert filtered_timeline[0].id == m_middle.id

    # 3. Conversation chronological listing
    conv_list = await repo.list_by_conversation_episodic(conversation_id=conv.id)
    assert len(conv_list) == 3
    assert conv_list[0].id == m_earliest.id


# =====================================================================
# 4. Procedural Repository Tests
# =====================================================================

async def test_procedural_repository_frequency(db_session: AsyncSession):
    # Setup user
    user = UserTable(email="procedural_repo_test@example.com", password_hash="hash")
    db_session.add(user)
    await db_session.commit()

    repo = SQLProceduralMemoryRepository(db_session)
    now = datetime.now(timezone.utc)

    # Create procedural memories
    p1 = await repo.create(
        user_id=user.id,
        conversation_id=None,
        content="Morning Standup workflow",
        memory_type=MemoryType.HABIT,
        importance=0.5,
        confidence=0.8,
        status=MemoryStatus.ACTIVE,
        last_accessed_at=now,
        version=1,
        metadata={},
        memory_system=MemorySystem.PROCEDURAL,
    )
    p2 = await repo.create(
        user_id=user.id,
        conversation_id=None,
        content="Git rebase workflow",
        memory_type=MemoryType.INSTRUCTION,
        importance=0.5,
        confidence=0.8,
        status=MemoryStatus.ACTIVE,
        last_accessed_at=now,
        version=1,
        metadata={},
        memory_system=MemorySystem.PROCEDURAL,
    )

    # Retrieve and manipulate existing MemoryState entries initialized during create()
    state1 = await db_session.get(MemoryStateTable, p1.id)
    state1.access_count = 10
    state1.retrieval_count = 5
    state1.reinforcement_count = 2
    state1.decay_score = 0.1
    state1.confidence_score = 0.9
    state1.importance_score = 0.8

    state2 = await db_session.get(MemoryStateTable, p2.id)
    state2.access_count = 2
    state2.retrieval_count = 1
    state2.reinforcement_count = 0
    state2.decay_score = 0.1
    state2.confidence_score = 0.9
    state2.importance_score = 0.8

    await db_session.commit()

    # 1. Standard listing
    list_all = await repo.get_procedural_memories(user_id=user.id)
    assert len(list_all) == 2

    # 2. Frequent procedures retrieval (highest access_count first)
    frequent = await repo.get_frequent_procedures(user_id=user.id, limit=5)
    assert len(frequent) == 2
    assert frequent[0].id == p1.id  # 10 accesses
    assert frequent[1].id == p2.id  # 2 accesses


# =====================================================================
# 5. Working Repository Tests
# =====================================================================

async def test_working_repository_expiration(db_session: AsyncSession):
    # Setup test user and conversation
    user = UserTable(email="working_repo_test@example.com", password_hash="hash")
    db_session.add(user)
    await db_session.commit()

    conv = ConversationTable(user_id=user.id, title="Working Context", system_prompt="Prompt")
    db_session.add(conv)
    await db_session.commit()

    repo = SQLWorkingMemoryRepository(db_session)
    now = datetime.now(timezone.utc)

    # 1. Active Working memory (non-expired, expires in 2 hours)
    m_active = await repo.create(
        user_id=user.id,
        conversation_id=conv.id,
        content="Current discussion topic A",
        memory_type=MemoryType.FACT,
        importance=0.4,
        confidence=0.7,
        status=MemoryStatus.ACTIVE,
        last_accessed_at=now,
        version=1,
        metadata={},
        memory_system=MemorySystem.WORKING,
        expires_at=now + timedelta(hours=2),
    )

    # 2. Expired Working memory (expired 1 hour ago)
    await repo.create(
        user_id=user.id,
        conversation_id=conv.id,
        content="Temporary context already closed",
        memory_type=MemoryType.FACT,
        importance=0.4,
        confidence=0.7,
        status=MemoryStatus.ACTIVE,
        last_accessed_at=now,
        version=1,
        metadata={},
        memory_system=MemorySystem.WORKING,
        expires_at=now - timedelta(hours=1),
    )

    # 3. Verify get_active_working_memories filters out the expired memory
    active_list = await repo.get_active_working_memories(user_id=user.id)
    assert len(active_list) == 1
    assert active_list[0].id == m_active.id

    # 4. Verify list_active_session_context filters out the expired memory for the conversation
    session_list = await repo.list_active_session_context(conversation_id=conv.id)
    assert len(session_list) == 1
    assert session_list[0].id == m_active.id
