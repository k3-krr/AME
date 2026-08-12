import pytest
import uuid
import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Memory, MemoryType, MemoryStatus
from app.retrieval.domain.value_objects import PipelineStatus
from app.retrieval.application.telemetry import RetrievalTelemetryTracker
from app.config import settings


@pytest.mark.asyncio
async def test_api_query_length_limit_enforcement(client: AsyncClient):
    """Verify that queries exceeding the max length limit are rejected with 422."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "limit_test@example.com", "password": "securepassword123"}
    )
    
    long_query = "x" * (settings.RETRIEVAL_MAX_QUERY_LENGTH + 1)
    
    resp = await client.post(
        "/api/v1/retrieval/retrieve",
        json={"query": long_query}
    )
    assert resp.status_code == 422
    assert "exceeds the maximum allowed limit" in resp.json()["message"]


@pytest.mark.asyncio
async def test_api_overall_timeout_cancellation(client: AsyncClient):
    """Verify that retrieval requests timing out return a 408 Request Timeout."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "timeout_test@example.com", "password": "securepassword123"}
    )
    
    # Send a request with a miniscule timeout (e.g. 0.0001 seconds) to trigger cancellation
    resp = await client.post(
        "/api/v1/retrieval/ground",
        json={
            "query": "Who is the owner?",
            "options": {"timeout": 0.0001}
        }
    )
    assert resp.status_code == 408
    assert "timed out" in resp.json()["message"].lower()


@pytest.mark.asyncio
async def test_embedding_failure_returns_degraded_status(client: AsyncClient):
    """Verify that when embeddings fail, the pipeline returns status DEGRADED instead of 500."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "degraded_test@example.com", "password": "securepassword123"}
    )
    
    # Seed a memory
    await client.post(
        "/api/v1/memories",
        json={
            "content": "User owns a red bicycle.",
            "memory_type": "Fact",
            "importance": 0.8,
            "confidence": 0.9,
        }
    )
    
    # Mock embedding provider to raise an exception
    from app.infrastructure.clients.embedding_client import OpenAIEmbeddingProvider
    
    async def mock_get_embedding(text):
        raise RuntimeError("Embedding service unavailable")
        
    with patch.object(OpenAIEmbeddingProvider, "get_embedding", side_effect=mock_get_embedding):
        resp = await client.post(
            "/api/v1/retrieval/retrieve",
            json={"query": "bicycle details"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "DEGRADED"


@pytest.mark.asyncio
async def test_ranking_failure_falls_back_gracefully(client: AsyncClient):
    """Verify that when ranking fails, it preserves raw result order and maps status to DEGRADED."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "ranking_fail@example.com", "password": "securepassword123"}
    )
    
    # Seed a memory
    await client.post(
        "/api/v1/memories",
        json={
            "content": "Tennis player",
            "memory_type": "Fact",
            "importance": 0.5,
            "confidence": 0.5,
        }
    )
    
    from app.application.hybrid_ranking_service import HybridRankingService
    
    def mock_rank_hybrid_memories(self, memories, states, semantic_scores):
        raise ValueError("Ranking calculation error")
        
    with patch.object(HybridRankingService, "rank_hybrid_memories", side_effect=mock_rank_hybrid_memories):
        resp = await client.post(
            "/api/v1/retrieval/retrieve",
            json={"query": "Tennis"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "DEGRADED"
        assert len(data["fused_elements"]) >= 1


def test_telemetry_tracker_logs_structured_json():
    """Verify that RetrievalTelemetryTracker records and outputs metrics in valid JSON format."""
    tracker = RetrievalTelemetryTracker()
    tracker.record_latency("query_analysis", 0.0523)
    tracker.record_latency("ranking", 0.0122)
    tracker.result_count = 5
    tracker.capability_usage = ["SEMANTIC_SEARCH"]
    tracker.retained_element_ratio = 0.8
    tracker.success = True
    
    log_messages = []
    
    class CaptureHandler(logging.Handler):
        def emit(self, record):
            log_messages.append(record.getMessage())
            
    telemetry_logger = logging.getLogger("ame_backend.retrieval.telemetry")
    orig_disabled = telemetry_logger.disabled
    telemetry_logger.disabled = False
    orig_level = telemetry_logger.level
    telemetry_logger.setLevel(logging.INFO)
    handler = CaptureHandler()
    telemetry_logger.addHandler(handler)
    
    try:
        tracker.log_metrics()
        if len(log_messages) == 0:
            import app.retrieval.application.telemetry as tm
            raise RuntimeError(f"Log messages empty! disabled: {telemetry_logger.disabled}, id_equal: {id(telemetry_logger) == id(tm.logger)}, tm.logger.handlers: {tm.logger.handlers}, tm.logger.level: {tm.logger.level}, telemetry_logger.handlers: {telemetry_logger.handlers}, telemetry_logger.level: {telemetry_logger.level}, manager.disable: {logging.root.manager.disable}")
        assert len(log_messages) >= 1
        
        parsed = json.loads(log_messages[-1])
        assert parsed["request_id"] == str(tracker.request_id)
        assert parsed["success"] is True
        assert parsed["stage_latencies"]["query_analysis"] == 0.0523
        assert parsed["stage_latencies"]["ranking"] == 0.0122
        assert parsed["result_count"] == 5
        assert parsed["capability_usage"] == ["SEMANTIC_SEARCH"]
        assert parsed["retained_element_ratio"] == 0.8
    finally:
        telemetry_logger.setLevel(orig_level)
        telemetry_logger.disabled = orig_disabled
        telemetry_logger.removeHandler(handler)


@pytest.mark.asyncio
async def test_tenant_boundary_isolation_checks(client: AsyncClient, db_session: AsyncSession):
    """Verify that retrieval results do not leak between different users."""
    # 1. Register User A
    await client.post(
        "/api/v1/auth/register",
        json={"email": "user_a@example.com", "password": "securepassword123"}
    )
    # Login as User A and create a secret memory
    await client.post(
        "/api/v1/auth/login",
        json={"email": "user_a@example.com", "password": "securepassword123"}
    )
    await client.post(
        "/api/v1/memories",
        json={
            "content": "Secret code for User A is 12345.",
            "memory_type": "Fact",
            "importance": 0.9,
            "confidence": 0.9,
        }
    )
    await client.post("/api/v1/auth/logout")

    # 2. Register User B
    await client.post(
        "/api/v1/auth/register",
        json={"email": "user_b@example.com", "password": "securepassword123"}
    )
    # Login as User B and verify they cannot fetch User A's memory
    await client.post(
        "/api/v1/auth/login",
        json={"email": "user_b@example.com", "password": "securepassword123"}
    )
    resp = await client.post(
        "/api/v1/retrieval/retrieve",
        json={"query": "Secret code"}
    )
    
    assert resp.status_code == 200
    data = resp.json()
    # User B should not see User A's secret memory
    for el in data["fused_elements"]:
        assert "12345" not in el["content"]
