import pytest
import uuid
from httpx import AsyncClient
from app.domain.entities import AgentStatus

pytestmark = pytest.mark.asyncio


async def test_agent_credential_lifecycle(client: AsyncClient):
    """Test that agent credentials can be created, listed, verified, and revoked."""
    # 1. Register and login User A
    await client.post(
        "/api/v1/auth/register",
        json={"email": "agentcredA@example.com", "password": "password123"}
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "agentcredA@example.com", "password": "password123"}
    )

    # 2. Create an Agent
    agent_res = await client.post(
        "/api/v1/agents",
        json={
            "name": "Test Cred Agent",
            "description": "Agent to test credential lifecycle.",
            "configuration": {}
        }
    )
    assert agent_res.status_code == 201
    agent_id = agent_res.json()["id"]

    # 3. Issue Credential
    cred_res = await client.post(
        f"/api/v1/agents/{agent_id}/credentials",
        json={"description": "Prod Key", "expires_in_days": 30}
    )
    assert cred_res.status_code == 201
    cred_data = cred_res.json()
    assert "id" in cred_data
    assert cred_data["agent_id"] == agent_id
    assert cred_data["description"] == "Prod Key"
    assert "raw_key" in cred_data
    raw_key = cred_data["raw_key"]
    assert raw_key.startswith("ame_agent_")

    # 4. List Credentials and verify raw_key and hash are NOT returned
    list_res = await client.get(f"/api/v1/agents/{agent_id}/credentials")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert len(list_data) == 1
    assert list_data[0]["id"] == cred_data["id"]
    assert list_data[0]["description"] == "Prod Key"
    assert "raw_key" not in list_data[0] or list_data[0]["raw_key"] is None
    assert "credential_hash" not in list_data[0]

    # --- Test Single Principal Auth (clear cookies first to avoid Ambiguous rejection) ---
    client.cookies.clear()

    # 5. Authenticate using the new raw_key (calling /agents/me/context)
    # Using Authorization Header
    auth_res = await client.get(
        "/api/v1/agents/me/context",
        headers={"Authorization": f"Bearer {raw_key}"}
    )
    assert auth_res.status_code == 200
    ctx = auth_res.json()
    assert ctx["principal_type"] == "AGENT"
    assert ctx["agent_id"] == agent_id
    assert ctx["user_id"] is None

    # Using X-Agent-Credential Header
    auth_res_x = await client.get(
        "/api/v1/agents/me/context",
        headers={"X-Agent-Credential": raw_key}
    )
    assert auth_res_x.status_code == 200
    assert auth_res_x.json()["agent_id"] == agent_id

    # --- Re-login to revoke key ---
    await client.post(
        "/api/v1/auth/login",
        json={"email": "agentcredA@example.com", "password": "password123"}
    )

    # 6. Revoke the Credential
    revoke_res = await client.post(
        f"/api/v1/agents/{agent_id}/credentials/{cred_data['id']}/revoke"
    )
    assert revoke_res.status_code == 200
    assert revoke_res.json()["id"] == cred_data["id"]

    # --- Clear cookies to test revoked key auth ---
    client.cookies.clear()

    # 7. Authenticate again (should fail with 401)
    auth_res_after = await client.get(
        "/api/v1/agents/me/context",
        headers={"Authorization": f"Bearer {raw_key}"}
    )
    assert auth_res_after.status_code == 401


async def test_agent_credential_rotation(client: AsyncClient):
    """Test that multiple credentials can coexist to support seamless key rotation."""
    # Register and login User
    await client.post(
        "/api/v1/auth/register",
        json={"email": "agentcred_rot@example.com", "password": "password123"}
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "agentcred_rot@example.com", "password": "password123"}
    )

    # Create Agent
    agent_res = await client.post(
        "/api/v1/agents",
        json={"name": "Rotation Agent"}
    )
    agent_id = agent_res.json()["id"]

    # Create Credential 1
    cred1_res = await client.post(
        f"/api/v1/agents/{agent_id}/credentials",
        json={"description": "Key 1"}
    )
    key1 = cred1_res.json()["raw_key"]

    # Create Credential 2
    cred2_res = await client.post(
        f"/api/v1/agents/{agent_id}/credentials",
        json={"description": "Key 2"}
    )
    key2 = cred2_res.json()["raw_key"]

    # --- Clear cookies to test agent authentication ---
    client.cookies.clear()

    # Verify both work
    r1 = await client.get("/api/v1/agents/me/context", headers={"Authorization": f"Bearer {key1}"})
    assert r1.status_code == 200
    r2 = await client.get("/api/v1/agents/me/context", headers={"Authorization": f"Bearer {key2}"})
    assert r2.status_code == 200

    # --- Re-login to revoke key 1 ---
    await client.post(
        "/api/v1/auth/login",
        json={"email": "agentcred_rot@example.com", "password": "password123"}
    )
    await client.post(f"/api/v1/agents/{agent_id}/credentials/{cred1_res.json()['id']}/revoke")

    # --- Clear cookies to test auth after revocation ---
    client.cookies.clear()

    # Key 1 fails, Key 2 still works
    r1_after = await client.get("/api/v1/agents/me/context", headers={"Authorization": f"Bearer {key1}"})
    assert r1_after.status_code == 401
    r2_after = await client.get("/api/v1/agents/me/context", headers={"Authorization": f"Bearer {key2}"})
    assert r2_after.status_code == 200


async def test_agent_credential_isolation(client: AsyncClient):
    """Test that tenant isolation prevents unauthorized management of agent keys."""
    # User A registers & logs in
    await client.post(
        "/api/v1/auth/register",
        json={"email": "agentcred_usera@example.com", "password": "password123"}
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "agentcred_usera@example.com", "password": "password123"}
    )
    agent_res = await client.post(
        "/api/v1/agents",
        json={"name": "Agent A"}
    )
    agent_id = agent_res.json()["id"]

    # User B registers & logs in
    await client.post(
        "/api/v1/auth/register",
        json={"email": "agentcred_userb@example.com", "password": "password123"}
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "agentcred_userb@example.com", "password": "password123"}
    )

    # User B tries to issue credential for User A's Agent (should fail with 403)
    res = await client.post(
        f"/api/v1/agents/{agent_id}/credentials",
        json={"description": "Unauthorized Key"}
    )
    assert res.status_code == 403

    # User B tries to list User A's Agent credentials (should fail with 403)
    res_list = await client.get(f"/api/v1/agents/{agent_id}/credentials")
    assert res_list.status_code == 403


async def test_suspended_and_revoked_agent_auth(client: AsyncClient):
    """Test that suspended or revoked agents cannot authenticate with credentials."""
    # Register & Login User A
    await client.post(
        "/api/v1/auth/register",
        json={"email": "agentcred_status@example.com", "password": "password123"}
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "agentcred_status@example.com", "password": "password123"}
    )

    # Create Agent
    agent_res = await client.post(
        "/api/v1/agents",
        json={"name": "Status Agent"}
    )
    agent_id = agent_res.json()["id"]

    # Issue Credential
    cred_res = await client.post(
        f"/api/v1/agents/{agent_id}/credentials",
        json={"description": "Active Key"}
    )
    raw_key = cred_res.json()["raw_key"]

    # --- Clear cookies to test agent authentication ---
    client.cookies.clear()

    # Verify authenticates successfully
    res = await client.get("/api/v1/agents/me/context", headers={"Authorization": f"Bearer {raw_key}"})
    assert res.status_code == 200

    # --- Re-login User A to suspend the agent ---
    await client.post(
        "/api/v1/auth/login",
        json={"email": "agentcred_status@example.com", "password": "password123"}
    )

    # Suspend the Agent
    sus_res = await client.post(f"/api/v1/agents/{agent_id}/suspend")
    assert sus_res.status_code == 200

    # --- Clear cookies to test agent authentication ---
    client.cookies.clear()

    # Try to authenticate (should fail with 401)
    res_sus = await client.get("/api/v1/agents/me/context", headers={"Authorization": f"Bearer {raw_key}"})
    assert res_sus.status_code == 401

    # --- Re-login User A to reactivate the agent ---
    await client.post(
        "/api/v1/auth/login",
        json={"email": "agentcred_status@example.com", "password": "password123"}
    )

    # Reactivate the Agent
    react_res = await client.post(f"/api/v1/agents/{agent_id}/reactivate")
    assert react_res.status_code == 200

    # --- Clear cookies to test agent authentication ---
    client.cookies.clear()

    # Verify works again
    res_react = await client.get("/api/v1/agents/me/context", headers={"Authorization": f"Bearer {raw_key}"})
    assert res_react.status_code == 200

    # --- Re-login User A to revoke the agent ---
    await client.post(
        "/api/v1/auth/login",
        json={"email": "agentcred_status@example.com", "password": "password123"}
    )

    # Revoke the Agent
    rev_res = await client.post(f"/api/v1/agents/{agent_id}/revoke")
    assert rev_res.status_code == 200

    # --- Clear cookies to test agent authentication ---
    client.cookies.clear()

    # Try to authenticate (should fail with 401)
    res_rev = await client.get("/api/v1/agents/me/context", headers={"Authorization": f"Bearer {raw_key}"})
    assert res_rev.status_code == 401

    # --- Re-login User A to try creating credential ---
    await client.post(
        "/api/v1/auth/login",
        json={"email": "agentcred_status@example.com", "password": "password123"}
    )

    # Try to create credential for revoked agent (should fail with 400 Bad Request)
    res_create_rev = await client.post(
        f"/api/v1/agents/{agent_id}/credentials",
        json={"description": "Revoked Key"}
    )
    assert res_create_rev.status_code == 400


async def test_ambiguous_authentication_rejection(client: AsyncClient):
    """Test that requests containing both a valid session cookie and an agent key are rejected."""
    # 1. Register & login User A
    await client.post(
        "/api/v1/auth/register",
        json={"email": "agentcred_ambig@example.com", "password": "password123"}
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "agentcred_ambig@example.com", "password": "password123"}
    )

    # 2. Create Agent
    agent_res = await client.post(
        "/api/v1/agents",
        json={"name": "Ambiguous Agent"}
    )
    agent_id = agent_res.json()["id"]

    # 3. Issue Credential
    cred_res = await client.post(
        f"/api/v1/agents/{agent_id}/credentials",
        json={"description": "Active Key"}
    )
    raw_key = cred_res.json()["raw_key"]

    # At this point, the client contains the "session" cookie from login.
    # If we request with the agent header, both are present, so it should reject with 400.
    res = await client.get(
        "/api/v1/agents/me/context",
        headers={"Authorization": f"Bearer {raw_key}"}
    )
    assert res.status_code == 400
    assert "Ambiguous authentication context" in res.json()["message"]
    assert res.json()["error_code"] == "BAD_REQUEST"
