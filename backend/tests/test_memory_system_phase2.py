"""Unit and integration tests for hybrid memory Phase 2."""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.domain.entities import Memory, MemoryType, MemoryStatus
from app.domain.memory_system import MemorySystem
from app.domain.memory_router import MemoryRouter, ClassificationResult
from app.infrastructure.repositories.sql_repos import (
    SQLRepositoryFactory,
    SQLSemanticMemoryRepository,
    SQLEpisodicMemoryRepository,
    SQLProceduralMemoryRepository,
    SQLWorkingMemoryRepository,
    SQLMemoryRepository,
)
from app.application.memory_service import MemoryService
from app.infrastructure.db.models import MemoryTable, UserTable

pytestmark = pytest.mark.asyncio


# =====================================================================
# 1. MemoryRouter Tests
# =====================================================================

def test_router_priority_1_explicit():
    router = MemoryRouter()
    now = datetime.now(timezone.utc)
    # Even though content contains working keywords and is an Event type,
    # the explicit_system parameter must override everything.
    memory = Memory(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        content="temporary current session data",
        memory_type=MemoryType.EVENT,
        memory_system=MemorySystem.SEMANTIC,  # default placeholder
        importance=0.5,
        confidence=0.8,
        status=MemoryStatus.ACTIVE,
        created_at=now,
        updated_at=now,
        last_accessed_at=now,
        conversation_id=uuid.uuid4(),
    )
    result = router.classify(memory, explicit_system=MemorySystem.PROCEDURAL)
    assert result.memory_system == MemorySystem.PROCEDURAL
    assert result.confidence_score == 1.0
    assert "explicitly provided" in result.reason


def test_router_priority_2_metadata():
    router = MemoryRouter()
    now = datetime.now(timezone.utc)
    # Metadata hint must take priority over MemoryType mapping or keywords.
    memory = Memory(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        content="I visited Seattle yesterday.",
        memory_type=MemoryType.EVENT,
        memory_system=MemorySystem.SEMANTIC,
        importance=0.5,
        confidence=0.8,
        status=MemoryStatus.ACTIVE,
        created_at=now,
        updated_at=now,
        last_accessed_at=now,
        conversation_id=uuid.uuid4(),
        metadata={"system_hint": "Working"},
    )
    result = router.classify(memory)
    assert result.memory_system == MemorySystem.WORKING
    assert result.confidence_score == 1.0
    assert "metadata hint key" in result.reason


def test_router_priority_3_specialized_mapping():
    router = MemoryRouter()
    now = datetime.now(timezone.utc)
    
    # Event mapping to Episodic (with conversation_id)
    memory_episodic = Memory(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        content="Generic event description.",
        memory_type=MemoryType.EVENT,
        memory_system=MemorySystem.SEMANTIC,
        importance=0.5,
        confidence=0.8,
        status=MemoryStatus.ACTIVE,
        created_at=now,
        updated_at=now,
        last_accessed_at=now,
        conversation_id=uuid.uuid4(),
    )
    result_episodic = router.classify(memory_episodic)
    assert result_episodic.memory_system == MemorySystem.EPISODIC
    assert result_episodic.confidence_score == 0.95

    # Instruction mapping to Procedural
    memory_proc = Memory(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        content="Always follow guidelines.",
        memory_type=MemoryType.INSTRUCTION,
        memory_system=MemorySystem.SEMANTIC,
        importance=0.5,
        confidence=0.8,
        status=MemoryStatus.ACTIVE,
        created_at=now,
        updated_at=now,
        last_accessed_at=now,
    )
    result_proc = router.classify(memory_proc)
    assert result_proc.memory_system == MemorySystem.PROCEDURAL
    assert result_proc.confidence_score == 1.0


def test_router_priority_4_keyword_heuristics():
    router = MemoryRouter()
    now = datetime.now(timezone.utc)

    # Generic type Fact containing working keyword
    memory_work = Memory(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        content="This is for a temp session.",
        memory_type=MemoryType.FACT,
        memory_system=MemorySystem.SEMANTIC,
        importance=0.5,
        confidence=0.8,
        status=MemoryStatus.ACTIVE,
        created_at=now,
        updated_at=now,
        last_accessed_at=now,
        conversation_id=uuid.uuid4(),
    )
    result_work = router.classify(memory_work)
    assert result_work.memory_system == MemorySystem.WORKING
    assert result_work.confidence_score == 0.9

    # Generic type Fact containing episodic keyword
    memory_ep = Memory(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        content="I went to the store.",
        memory_type=MemoryType.FACT,
        memory_system=MemorySystem.SEMANTIC,
        importance=0.5,
        confidence=0.8,
        status=MemoryStatus.ACTIVE,
        created_at=now,
        updated_at=now,
        last_accessed_at=now,
        conversation_id=uuid.uuid4(),
    )
    result_ep = router.classify(memory_ep)
    assert result_ep.memory_system == MemorySystem.EPISODIC
    assert result_ep.confidence_score == 0.8


def test_router_priority_5_default_fallback():
    router = MemoryRouter()
    now = datetime.now(timezone.utc)

    # General Fact maps to Semantic
    memory = Memory(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        content="Seattle has a space needle.",
        memory_type=MemoryType.FACT,
        memory_system=MemorySystem.SEMANTIC,
        importance=0.5,
        confidence=0.8,
        status=MemoryStatus.ACTIVE,
        created_at=now,
        updated_at=now,
        last_accessed_at=now,
    )
    result = router.classify(memory)
    assert result.memory_system == MemorySystem.SEMANTIC
    assert "Default fallback mapping" in result.reason


# =====================================================================
# 2. RepositoryFactory Tests
# =====================================================================

async def test_repository_factory_resolution(db_session: AsyncSession):
    factory = SQLRepositoryFactory(db_session)
    
    assert isinstance(factory.get(MemorySystem.SEMANTIC), SQLSemanticMemoryRepository)
    assert isinstance(factory.get(MemorySystem.EPISODIC), SQLEpisodicMemoryRepository)
    assert isinstance(factory.get(MemorySystem.PROCEDURAL), SQLProceduralMemoryRepository)
    assert isinstance(factory.get(MemorySystem.WORKING), SQLWorkingMemoryRepository)


# =====================================================================
# 3. MemoryService Integration Tests
# =====================================================================

async def test_memory_service_automatic_routing(client: AsyncClient, db_session: AsyncSession):
    # Setup authenticated user and conversation
    await client.post(
        "/api/v1/auth/register",
        json={"email": "hybrid_routing@example.com", "password": "password123"},
    )
    conv_resp = await client.post("/api/v1/conversations", json={"title": "Routing Conversation"})
    conv_id = uuid.UUID(conv_resp.json()["id"])
    
    user_id = (
        await db_session.execute(
            select(UserTable.id).where(UserTable.email == "hybrid_routing@example.com")
        )
    ).scalar()

    # Instantiate factory & service
    from app.infrastructure.clients.embedding_client import OpenAIEmbeddingProvider
    from app.infrastructure.repositories.sql_repos import (
        SQLConversationRepository,
        SQLMemoryEmbeddingRepository,
        SQLMemoryStateRepository,
    )
    
    memory_router = MemoryRouter()
    repository_factory = SQLRepositoryFactory(db_session)
    
    service = MemoryService(
        memory_repo=SQLMemoryRepository(db_session),
        conversation_repo=SQLConversationRepository(db_session),
        embedding_repo=SQLMemoryEmbeddingRepository(db_session),
        embedding_provider=OpenAIEmbeddingProvider(),
        memory_state_repo=SQLMemoryStateRepository(db_session),
        memory_router=memory_router,
        repository_factory=repository_factory,
    )

    # 1. Test Working Memory Routing (via keywords)
    m_working = await service.create_memory(
        user_id=user_id,
        conversation_id=conv_id,
        content="temp context for session",
        memory_type=MemoryType.FACT,
        importance=0.6,
        confidence=0.9,
    )
    assert m_working.memory_system == MemorySystem.WORKING
    assert m_working.expires_at is not None

    # 2. Test Procedural Memory Routing (via type mapping)
    m_proc = await service.create_memory(
        user_id=user_id,
        conversation_id=conv_id,
        content="Follow procedure steps to deploy",
        memory_type=MemoryType.INSTRUCTION,
        importance=0.5,
        confidence=0.8,
    )
    assert m_proc.memory_system == MemorySystem.PROCEDURAL
    assert m_proc.expires_at is None

    # Verify database persistence
    db_session.expire_all()
    w_row = await db_session.get(MemoryTable, m_working.id)
    assert w_row.memory_system == "Working"
    assert w_row.expires_at is not None

    p_row = await db_session.get(MemoryTable, m_proc.id)
    assert p_row.memory_system == "Procedural"
