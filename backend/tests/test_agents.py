import pytest
import uuid
from httpx import AsyncClient
from app.domain.entities import AgentStatus

pytestmark = pytest.mark.asyncio


async def test_agent_unauthorized_access(client: AsyncClient):
    """Test that agent endpoints return 401 when not authenticated."""
    response = await client.get("/api/v1/agents")
    assert response.status_code == 401
    assert response.json()["error_code"] == "UNAUTHORIZED"

    response = await client.post(
        "/api/v1/agents",
        json={"name": "Test Agent"}
    )
    assert response.status_code == 401


async def test_agent_create_success(client: AsyncClient):
    """Test creating an agent successfully with valid inputs."""
    # Register & Login User A
    await client.post(
        "/api/v1/auth/register",
        json={"email": "agenttestA@example.com", "password": "password123"}
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "agenttestA@example.com", "password": "password123"}
    )

    # Create Agent
    response = await client.post(
        "/api/v1/agents",
        json={
            "name": "Memory Agent",
            "description": "An agent that manages semantic memory.",
            "configuration": {"temperature": 0.3, "provider": "custom"}
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "tenant_id" in data  # matches User A's ID
    assert data["name"] == "Memory Agent"
    assert data["description"] == "An agent that manages semantic memory."
    assert data["status"] == "ACTIVE"
    assert data["configuration"] == {"temperature": 0.3, "provider": "custom"}
    assert "created_at" in data
    assert "updated_at" in data


async def test_agent_create_invalid_input(client: AsyncClient):
    """Test that creating an agent with empty name or missing fields fails."""
    # Register & Login User A
    await client.post(
        "/api/v1/auth/register",
        json={"email": "agenttestB@example.com", "password": "password123"}
    )

    # Empty name (triggers Pydantic schema validation error)
    response = await client.post(
        "/api/v1/agents",
        json={"name": ""}
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"
    assert "details" in response.json()

    # Whitespace-only name (passes Pydantic but fails service logic validation)
    response = await client.post(
        "/api/v1/agents",
        json={"name": "   "}
    )
    assert response.status_code == 400


async def test_agent_retrieve_and_tenant_isolation(client: AsyncClient):
    """Test retrieving an agent and verifying cross-tenant access is blocked."""
    # 1. Register & login User A
    await client.post(
        "/api/v1/auth/register",
        json={"email": "usera@example.com", "password": "password123"}
    )
    create_resp_a = await client.post(
        "/api/v1/agents",
        json={"name": "User A Agent"}
    )
    assert create_resp_a.status_code == 201
    agent_a_id = create_resp_a.json()["id"]

    # Retrieve own agent (User A)
    get_resp_a = await client.get(f"/api/v1/agents/{agent_a_id}")
    assert get_resp_a.status_code == 200
    assert get_resp_a.json()["name"] == "User A Agent"

    # 2. Register & login User B
    client.cookies.clear()
    await client.post(
        "/api/v1/auth/register",
        json={"email": "userb@example.com", "password": "password123"}
    )
    
    # Try retrieving User A's agent (should return 403 Forbidden)
    get_resp_b = await client.get(f"/api/v1/agents/{agent_a_id}")
    assert get_resp_b.status_code == 403
    assert get_resp_b.json()["error_code"] == "FORBIDDEN"

    # Try retrieving a non-existent agent (should return 404 Not Found)
    non_existent_id = uuid.uuid4()
    get_nonexistent = await client.get(f"/api/v1/agents/{non_existent_id}")
    assert get_nonexistent.status_code == 404
    assert get_nonexistent.json()["error_code"] == "RESOURCE_NOT_FOUND"


async def test_agent_update_success(client: AsyncClient):
    """Test updating agent fields (name, description, configuration) successfully."""
    # Register & Login User
    await client.post(
        "/api/v1/auth/register",
        json={"email": "updateuser@example.com", "password": "password123"}
    )

    # Create Agent
    create_resp = await client.post(
        "/api/v1/agents",
        json={"name": "Original Name", "description": "Original Desc", "configuration": {"k": "v"}}
    )
    agent_id = create_resp.json()["id"]

    # Update Agent
    update_resp = await client.patch(
        f"/api/v1/agents/{agent_id}",
        json={"name": "New Name", "description": "New Desc", "configuration": {"k2": "v2"}}
    )
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["name"] == "New Name"
    assert data["description"] == "New Desc"
    assert data["configuration"] == {"k2": "v2"}

    # Update only one field
    update_one = await client.patch(
        f"/api/v1/agents/{agent_id}",
        json={"name": "Single Name Update"}
    )
    assert update_one.status_code == 200
    assert update_one.json()["name"] == "Single Name Update"
    assert update_one.json()["description"] == "New Desc"  # stays the same


async def test_agent_update_tenant_isolation(client: AsyncClient):
    """Test that User B cannot update User A's agent."""
    # 1. Register & login User A
    await client.post(
        "/api/v1/auth/register",
        json={"email": "user_update_a@example.com", "password": "password123"}
    )
    create_resp = await client.post(
        "/api/v1/agents",
        json={"name": "User A Agent"}
    )
    agent_id = create_resp.json()["id"]

    # 2. Register & login User B
    client.cookies.clear()
    await client.post(
        "/api/v1/auth/register",
        json={"email": "user_update_b@example.com", "password": "password123"}
    )

    # Try updating User A's agent (should return 403 Forbidden)
    update_resp = await client.patch(
        f"/api/v1/agents/{agent_id}",
        json={"name": "Hacked Name"}
    )
    assert update_resp.status_code == 403


async def test_agent_list_isolation(client: AsyncClient):
    """Test that listing agents is strictly isolated per tenant."""
    # 1. Register & login User A
    await client.post(
        "/api/v1/auth/register",
        json={"email": "user_list_a@example.com", "password": "password123"}
    )
    await client.post("/api/v1/agents", json={"name": "Agent A1"})
    await client.post("/api/v1/agents", json={"name": "Agent A2"})

    # List User A's agents
    list_a = await client.get("/api/v1/agents")
    assert list_a.status_code == 200
    agents_a = list_a.json()
    assert len(agents_a) == 2
    assert any(a["name"] == "Agent A1" for a in agents_a)
    assert any(a["name"] == "Agent A2" for a in agents_a)

    # 2. Register & login User B
    client.cookies.clear()
    await client.post(
        "/api/v1/auth/register",
        json={"email": "user_list_b@example.com", "password": "password123"}
    )
    await client.post("/api/v1/agents", json={"name": "Agent B1"})

    # List User B's agents (should not leak User A's agents)
    list_b = await client.get("/api/v1/agents")
    assert list_b.status_code == 200
    agents_b = list_b.json()
    assert len(agents_b) == 1
    assert agents_b[0]["name"] == "Agent B1"


async def test_agent_lifecycle_transitions(client: AsyncClient):
    """Test valid and invalid status transitions."""
    # Register & Login User
    await client.post(
        "/api/v1/auth/register",
        json={"email": "lifecycle@example.com", "password": "password123"}
    )

    # Create Agent (initial status ACTIVE)
    create_resp = await client.post(
        "/api/v1/agents",
        json={"name": "Lifecycle Agent"}
    )
    agent_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "ACTIVE"

    # ACTIVE -> SUSPENDED
    suspend_resp = await client.post(f"/api/v1/agents/{agent_id}/suspend")
    assert suspend_resp.status_code == 200
    assert suspend_resp.json()["status"] == "SUSPENDED"

    # SUSPENDED -> SUSPENDED (no-op)
    suspend_dup = await client.post(f"/api/v1/agents/{agent_id}/suspend")
    assert suspend_dup.status_code == 200
    assert suspend_dup.json()["status"] == "SUSPENDED"

    # SUSPENDED -> ACTIVE
    reactivate_resp = await client.post(f"/api/v1/agents/{agent_id}/reactivate")
    assert reactivate_resp.status_code == 200
    assert reactivate_resp.json()["status"] == "ACTIVE"

    # ACTIVE -> ACTIVE (no-op)
    reactivate_dup = await client.post(f"/api/v1/agents/{agent_id}/reactivate")
    assert reactivate_dup.status_code == 200
    assert reactivate_dup.json()["status"] == "ACTIVE"

    # ACTIVE -> REVOKED
    revoke_resp = await client.post(f"/api/v1/agents/{agent_id}/revoke")
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["status"] == "REVOKED"

    # REVOKED -> REVOKED (no-op)
    revoke_dup = await client.post(f"/api/v1/agents/{agent_id}/revoke")
    assert revoke_dup.status_code == 200
    assert revoke_dup.json()["status"] == "REVOKED"

    # REVOKED -> ACTIVE (invalid transition, should return 400)
    reactivate_revoked = await client.post(f"/api/v1/agents/{agent_id}/reactivate")
    assert reactivate_revoked.status_code == 400
    assert "terminal" in reactivate_revoked.json()["message"]

    # REVOKED -> SUSPENDED (invalid transition, should return 400)
    suspend_revoked = await client.post(f"/api/v1/agents/{agent_id}/suspend")
    assert suspend_revoked.status_code == 400
    assert "terminal" in suspend_revoked.json()["message"]

    # Update a revoked agent (should return 400)
    update_revoked = await client.patch(
        f"/api/v1/agents/{agent_id}",
        json={"name": "New Name"}
    )
    assert update_revoked.status_code == 400
    assert "revoked" in update_revoked.json()["message"].lower()


async def test_agent_lifecycle_transitions_from_suspended_to_revoked(client: AsyncClient):
    """Test that a SUSPENDED agent can be REVOKED."""
    # Register & Login User
    await client.post(
        "/api/v1/auth/register",
        json={"email": "lifecycle2@example.com", "password": "password123"}
    )

    # Create Agent
    create_resp = await client.post(
        "/api/v1/agents",
        json={"name": "Lifecycle Agent 2"}
    )
    agent_id = create_resp.json()["id"]

    # SUSPEND
    await client.post(f"/api/v1/agents/{agent_id}/suspend")

    # SUSPENDED -> REVOKED
    revoke_resp = await client.post(f"/api/v1/agents/{agent_id}/revoke")
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["status"] == "REVOKED"


async def test_agent_lifecycle_cross_tenant_denied(client: AsyncClient):
    """Test that User B cannot change the status of User A's agent."""
    # 1. Register & login User A
    await client.post(
        "/api/v1/auth/register",
        json={"email": "lifecycle_owner@example.com", "password": "password123"}
    )
    create_resp = await client.post(
        "/api/v1/agents",
        json={"name": "User A Agent"}
    )
    agent_id = create_resp.json()["id"]

    # 2. Register & login User B
    client.cookies.clear()
    await client.post(
        "/api/v1/auth/register",
        json={"email": "lifecycle_attacker@example.com", "password": "password123"}
    )

    # Try suspending User A's agent
    suspend_resp = await client.post(f"/api/v1/agents/{agent_id}/suspend")
    assert suspend_resp.status_code == 403

    # Try reactivating User A's agent
    reactivate_resp = await client.post(f"/api/v1/agents/{agent_id}/reactivate")
    assert reactivate_resp.status_code == 403

    # Try revoking User A's agent
    revoke_resp = await client.post(f"/api/v1/agents/{agent_id}/revoke")
    assert revoke_resp.status_code == 403
