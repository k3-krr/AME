"""Unit and integration tests for hybrid ranking Phase 5."""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.domain.entities import Memory, MemoryType, MemoryStatus
from app.domain.memory_system import MemorySystem
from app.application.ranking_service import RankingService
from app.application.hybrid_ranking_service import HybridRankingService
from app.application.memory_service import MemoryService
from app.infrastructure.repositories.sql_repos import (
    SQLMemoryRepository,
    SQLSemanticMemoryRepository,
    SQLEpisodicMemoryRepository,
    SQLRepositoryFactory,
)
from app.infrastructure.db.models import UserTable, ConversationTable, MemoryTable, MemoryStateTable

pytestmark = pytest.mark.asyncio


# =====================================================================
# 1. HybridRankingService Unit Tests
# =====================================================================

async def test_hybrid_ranking_config_overrides():
    base_ranker = RankingService()
    
    # Instantiate with specific weight overrides
    ranker = HybridRankingService(
        adaptive_ranking_service=base_ranker,
        semantic_system_weight=5.5,
        working_active_weight=0.9,
    )
    
    assert ranker.semantic_system_weight == 5.5
    assert ranker.working_active_weight == 0.9
    # Unspecified parameters fallback to settings
    assert ranker.episodic_system_weight == 1.0


async def test_hybrid_ranking_subscore_computations(db_session: AsyncSession):
    base_ranker = RankingService()
    ranker = HybridRankingService(
        adaptive_ranking_service=base_ranker,
        w_hybrid_adaptive=0.0,  # Focus solely on system score
        w_hybrid_system=1.0,
        semantic_similarity_weight=1.0,
        semantic_importance_weight=0.0,
        semantic_frequency_weight=0.0,
    )

    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # 1. Semantic Memory
    m_sem = Memory(
        id=uuid.uuid4(),
        user_id=user_id,
        content="Semantic code snippet",
        memory_type=MemoryType.FACT,
        importance=0.8,
        confidence=0.9,
        status=MemoryStatus.ACTIVE,
        created_at=now,
        updated_at=now,
        last_accessed_at=now,
        memory_system=MemorySystem.SEMANTIC,
    )

    # 2. Working Memory
    m_work = Memory(
        id=uuid.uuid4(),
        user_id=user_id,
        content="Working session detail",
        memory_type=MemoryType.FACT,
        importance=0.4,
        confidence=0.7,
        status=MemoryStatus.ACTIVE,
        created_at=now,
        updated_at=now,
        last_accessed_at=now,
        memory_system=MemorySystem.WORKING,
        metadata={"conversation_priority": 0.8},
    )

    # Semantic similarity scores map
    scores_map = {
        m_sem.id: 0.95,
        m_work.id: 0.10,
    }

    # Execute ranking
    ranked = ranker.rank_hybrid_memories(
        memories=[m_sem, m_work],
        states=[],
        semantic_scores=scores_map,
    )

    assert len(ranked) == 2
    # m_sem should have highest system score (similarity weight = 1.0, similarity = 0.95)
    assert ranked[0][0].id == m_sem.id
    assert ranked[0][1] == pytest.approx(0.95)


async def test_hybrid_ranking_tie_breaking_stability():
    base_ranker = RankingService()
    # Force identical scoring for tie-break testing
    ranker = HybridRankingService(
        adaptive_ranking_service=base_ranker,
        w_hybrid_adaptive=0.0,
        w_hybrid_system=0.0,
    )

    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    id1 = uuid.UUID("11111111-1111-1111-1111-111111111111")
    id2 = uuid.UUID("22222222-2222-2222-2222-222222222222")

    m1 = Memory(
        id=id1,
        user_id=user_id,
        content="First memory",
        memory_type=MemoryType.FACT,
        importance=0.5,
        confidence=0.5,
        status=MemoryStatus.ACTIVE,
        created_at=now,
        updated_at=now,
        last_accessed_at=now,
    )
    m2 = Memory(
        id=id2,
        user_id=user_id,
        content="Second memory",
        memory_type=MemoryType.FACT,
        importance=0.5,
        confidence=0.5,
        status=MemoryStatus.ACTIVE,
        created_at=now,
        updated_at=now,
        last_accessed_at=now,
    )

    # Run ranking (m1 and m2 have score = 0.0)
    # tie breaker sorts by string of ID: "1111..." should come before "2222..."
    ranked = ranker.rank_hybrid_memories(
        memories=[m2, m1],
        states=[],
        semantic_scores={},
    )
    assert ranked[0][0].id == id1
    assert ranked[1][0].id == id2


# =====================================================================
# 2. Integration Tests inside MemoryService
# =====================================================================

async def test_memory_service_hybrid_search_ranking(db_session: AsyncSession):
    # Setup user
    user = UserTable(email="hybrid_rank_service@example.com", password_hash="hash")
    db_session.add(user)
    await db_session.commit()

    conv = ConversationTable(user_id=user.id, title="Ranking API", system_prompt="Prompt")
    db_session.add(conv)
    await db_session.commit()

    # Repositories
    memory_repo = SQLMemoryRepository(db_session)
    conversation_repo = None  # mock not needed for simple retrieval
    from app.presentation.api.memories import OpenAIEmbeddingProvider
    from app.domain.repositories import IMemoryEmbeddingRepository, IMemoryStateRepository
    embedding_repo = db_session.get  # dummy
    embedding_provider = OpenAIEmbeddingProvider()
    
    # We can create a basic integration using full service injection helper
    from app.presentation.api.memories import get_memory_service, get_ranking_service
    from unittest.mock import patch

    with patch("app.config.settings.WORKING_MEMORY_WEIGHT", 0.1), patch("app.config.settings.SEMANTIC_MEMORY_WEIGHT", 2.0):
        ranking_service = get_ranking_service()
        service = get_memory_service(db_session, ranking_service)

    # Create semantic and working memories in database
    m1_id = uuid.uuid4()
    m2_id = uuid.uuid4()

    m1_db = MemoryTable(
        id=m1_id,
        user_id=user.id,
        conversation_id=conv.id,
        content="Apple makes MacBook laptops",
        memory_type=MemoryType.FACT.value,
        memory_system=MemorySystem.SEMANTIC.value,
        importance=0.9,
        confidence=0.9,
        status="ACTIVE",
        version=1,
    )
    m2_db = MemoryTable(
        id=m2_id,
        user_id=user.id,
        conversation_id=conv.id,
        content="Current active buffer session",
        memory_type=MemoryType.FACT.value,
        memory_system=MemorySystem.WORKING.value,
        importance=0.5,
        confidence=0.5,
        status="ACTIVE",
        version=1,
    )
    db_session.add(m1_db)
    db_session.add(m2_db)
    await db_session.commit()

    # Initialize state records
    state1 = MemoryStateTable(
        memory_id=m1_id,
        access_count=100,  # highly accessed
        retrieval_count=10,
        reinforcement_count=5,
        decay_score=0.0,
        confidence_score=0.9,
        importance_score=0.9,
    )
    state2 = MemoryStateTable(
        memory_id=m2_id,
        access_count=1,
        retrieval_count=1,
        reinforcement_count=0,
        decay_score=0.0,
        confidence_score=0.5,
        importance_score=0.5,
    )
    db_session.add(state1)
    db_session.add(state2)
    await db_session.commit()

    # Query hybrid search via MemoryService
    # Apple MacBook should be ranked first due to high importance, access_count, and system tier
    results = await service.search_hybrid_memories(
        user_id=user.id,
        conversation_id=conv.id,
    )

    assert len(results) == 2
    assert results[0].id == m1_id
