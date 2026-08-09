import pytest
import uuid
from httpx import AsyncClient
from app.retrieval.domain.entities import RetrievalRequest, GroundedContextPackage
from app.retrieval.domain.strategy import IRetrievalStrategy, IRetrievalStep, RetrievalContextState
from app.retrieval.domain.exceptions import StrategyNotFoundError
from app.retrieval.application.orchestrator import RetrievalPipelineOrchestrator
from app.retrieval.dependencies import get_retrieval_orchestrator


class MockRetrievalStep(IRetrievalStep):
    @property
    def name(self) -> str:
        return "mock_step"

    async def execute(self, state: RetrievalContextState) -> RetrievalContextState:
        state.grounded_package = GroundedContextPackage(
            request_id=state.request.id,
            retrieved_memories=[],
            fused_elements=[],
            metadata={"executed": True}
        )
        return state


class MockStrategy(IRetrievalStrategy):
    @property
    def name(self) -> str:
        return "mock_strategy"

    def resolve_steps(self, request: RetrievalRequest):
        return [MockRetrievalStep()]


@pytest.mark.asyncio
async def test_orchestrator_resolves_strategy_and_runs():
    """Verify that the orchestrator routes to the requested strategy and runs its steps."""
    orchestrator = RetrievalPipelineOrchestrator(
        strategies=[MockStrategy()],
        default_strategy_name="mock_strategy"
    )
    request = RetrievalRequest(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        query="Test query",
        options={"strategy": "mock_strategy"}
    )
    package = await orchestrator.execute_retrieval(request)
    assert package.request_id == request.id
    assert package.metadata.get("executed") is True


@pytest.mark.asyncio
async def test_orchestrator_raises_strategy_not_found():
    """Verify that the orchestrator throws StrategyNotFoundError if strategy is missing."""
    orchestrator = RetrievalPipelineOrchestrator(
        strategies=[],
        default_strategy_name="nonexistent"
    )
    request = RetrievalRequest(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        query="Test query",
        options={"strategy": "nonexistent"}
    )
    with pytest.raises(StrategyNotFoundError):
        await orchestrator.execute_retrieval(request)


@pytest.mark.asyncio
async def test_retrieval_request_validation():
    """Verify in-memory RetrievalRequest validation triggers errors on invalid inputs."""
    with pytest.raises(ValueError, match="Query string cannot be empty"):
        req = RetrievalRequest(id=uuid.uuid4(), user_id=uuid.uuid4(), query="")
        req.validate()

    with pytest.raises(ValueError, match="User ID is required"):
        # pass None to user_id
        req = RetrievalRequest(id=uuid.uuid4(), user_id=None, query="Hello")
        req.validate()


@pytest.mark.asyncio
async def test_api_retrieve_context_unauthorized(client: AsyncClient):
    """Verify endpoint blocks unauthenticated users."""
    response = await client.post(
        "/api/v1/retrieval/retrieve",
        json={"query": "hello"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_api_retrieve_context_404_no_strategy(client: AsyncClient):
    """Verify endpoint returns 404 when querying a strategy that is not registered."""
    # Register and log in
    reg_response = await client.post(
        "/api/v1/auth/register",
        json={"email": "retrieval_user_404@example.com", "password": "securepassword123"}
    )
    assert reg_response.status_code == 201

    # Mock the orchestrator to raise StrategyNotFoundError
    from app.main import app
    from app.retrieval.dependencies import get_retrieval_orchestrator
    
    class MockFailureOrchestrator:
        async def retrieve(self, user_id, query, conversation_id=None, options=None, access_context=None):
            raise StrategyNotFoundError("no valid retrieval strategy")

    app.dependency_overrides[get_retrieval_orchestrator] = lambda: MockFailureOrchestrator()

    try:
        response = await client.post(
            "/api/v1/retrieval/retrieve",
            json={"query": "test query", "options": {"strategy": "standard_rag"}}
        )
        assert response.status_code == 404
        assert "no valid retrieval strategy" in response.json()["message"].lower()
    finally:
        if get_retrieval_orchestrator in app.dependency_overrides:
            del app.dependency_overrides[get_retrieval_orchestrator]


@pytest.mark.asyncio
async def test_api_retrieve_context_success_with_override(client: AsyncClient):
    """Verify endpoint returns 200 OK when a mock strategy is injected via DI overrides."""
    # Register and log in
    reg_response = await client.post(
        "/api/v1/auth/register",
        json={"email": "retrieval_user_ok@example.com", "password": "securepassword123"}
    )
    assert reg_response.status_code == 201

    # Mock the orchestrator to return a mock package
    from app.main import app
    from app.retrieval.dependencies import get_retrieval_orchestrator
    
    class MockSuccessOrchestrator:
        async def retrieve(self, user_id, query, conversation_id=None, options=None, access_context=None):
            return GroundedContextPackage(
                request_id=uuid.uuid4(),
                retrieved_memories=[],
                fused_elements=[],
                metadata={"executed": True}
            )

    app.dependency_overrides[get_retrieval_orchestrator] = lambda: MockSuccessOrchestrator()

    try:
        response = await client.post(
            "/api/v1/retrieval/retrieve",
            json={"query": "test query", "options": {"strategy": "mock_strategy"}}
        )
        assert response.status_code == 200
        data = response.json()
        assert "request_id" in data
        assert "fused_elements" in data
        assert data["metadata"]["executed"] is True
    finally:
        # Clean up overrides so other tests are not affected
        if get_retrieval_orchestrator in app.dependency_overrides:
            del app.dependency_overrides[get_retrieval_orchestrator]


