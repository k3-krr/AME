import pytest
import uuid
from httpx import AsyncClient
from app.domain.entities import AgentStatus, MemoryAccessLevel

pytestmark = pytest.mark.asyncio


async def test_memory_access_control_workflow(client: AsyncClient):
    """
    Step-by-step test verifying memory access control:
    1. Register and login User A (Tenant A) and User B (Tenant B).
    2. Create Agent A1 and Agent A2 under Tenant A, and Agent B1 under Tenant B.
    3. Issue API keys for all agents.
    4. Authenticate Agent A1 to create an agent-owned memory.
    5. Verify Agent A1 can read/write/manage its own memory.
    6. Verify Agent A2 cannot access Agent A1's memory by default.
    7. Grant READ permission to Agent A2.
    8. Verify Agent A2 can read, but not write/manage the memory.
    9. Upgrade/upsert grant to WRITE permission for Agent A2.
    10. Verify Agent A2 can now update (write) the memory.
    11. Revoke access from Agent A2 and verify they are blocked again.
    12. Verify cross-tenant isolation: Tenant B / Agent B1 cannot grant access or see/access Tenant A's memories.
    13. Verify human user A retains full access to Agent A1's memory.
    14. Verify suspended agent cannot perform memory operations.
    """
    # ==========================================
    # 1. SETUP TENANTS AND AGENTS
    # ==========================================

    # Register and login User A
    await client.post(
        "/api/v1/auth/register",
        json={"email": "tenantA@example.com", "password": "password123"}
    )
    login_a_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "tenantA@example.com", "password": "password123"}
    )
    assert login_a_res.status_code == 200

    # Create Agent A1 & Agent A2
    agent_a1_res = await client.post(
        "/api/v1/agents",
        json={"name": "Agent A1", "description": "Owner agent", "configuration": {}}
    )
    assert agent_a1_res.status_code == 201
    agent_a1_id = agent_a1_res.json()["id"]

    agent_a2_res = await client.post(
        "/api/v1/agents",
        json={"name": "Agent A2", "description": "Collaborator agent", "configuration": {}}
    )
    assert agent_a2_res.status_code == 201
    agent_a2_id = agent_a2_res.json()["id"]

    # Issue credentials for A1 & A2
    cred_a1_res = await client.post(
        f"/api/v1/agents/{agent_a1_id}/credentials",
        json={"description": "A1 Key", "expires_in_days": 10}
    )
    assert cred_a1_res.status_code == 201
    key_a1 = cred_a1_res.json()["raw_key"]

    cred_a2_res = await client.post(
        f"/api/v1/agents/{agent_a2_id}/credentials",
        json={"description": "A2 Key", "expires_in_days": 10}
    )
    assert cred_a2_res.status_code == 201
    key_a2 = cred_a2_res.json()["raw_key"]

    # Clear cookies to login User B
    client.cookies.clear()

    # Register and login User B
    await client.post(
        "/api/v1/auth/register",
        json={"email": "tenantB@example.com", "password": "password123"}
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "tenantB@example.com", "password": "password123"}
    )

    # Create Agent B1
    agent_b1_res = await client.post(
        "/api/v1/agents",
        json={"name": "Agent B1", "description": "External agent", "configuration": {}}
    )
    assert agent_b1_res.status_code == 201
    agent_b1_id = agent_b1_res.json()["id"]

    # Issue credentials for B1
    cred_b1_res = await client.post(
        f"/api/v1/agents/{agent_b1_id}/credentials",
        json={"description": "B1 Key", "expires_in_days": 10}
    )
    assert cred_b1_res.status_code == 201
    key_b1 = cred_b1_res.json()["raw_key"]

    # Clear cookies to ensure clean header authentication context
    client.cookies.clear()

    # ==========================================
    # 2. AGENT-OWNED MEMORY CREATION (Agent A1)
    # ==========================================

    # Agent A1 creates a memory
    headers_a1 = {"X-Agent-Credential": key_a1}
    memory_payload = {
        "content": "Secret tactical plans of Agent A1.",
        "memory_type": "Fact",
        "importance": 0.9,
        "confidence": 0.95,
        "memory_system": "Semantic"
    }

    create_mem_res = await client.post(
        "/api/v1/memories",
        json=memory_payload,
        headers=headers_a1
    )
    assert create_mem_res.status_code == 201
    memory_id = create_mem_res.json()["id"]

    # ==========================================
    # 3. OWNER ACCESS VERIFICATION (Agent A1)
    # ==========================================

    # A1 retrieves the memory (READ)
    get_mem_res = await client.get(f"/api/v1/memories/{memory_id}", headers=headers_a1)
    assert get_mem_res.status_code == 200
    assert get_mem_res.json()["content"] == "Secret tactical plans of Agent A1."

    # A1 updates the memory (WRITE)
    update_payload = {"content": "Tactical plans of Agent A1 updated."}
    update_mem_res = await client.put(
        f"/api/v1/memories/{memory_id}",
        json=update_payload,
        headers=headers_a1
    )
    assert update_mem_res.status_code == 200
    assert update_mem_res.json()["content"] == "Tactical plans of Agent A1 updated."

    # ==========================================
    # 4. DEFAULT PROTECTION (Agent A2)
    # ==========================================

    # A2 tries to read the memory -> Should get 403 (PermissionError) for within-tenant unauthorized access
    headers_a2 = {"X-Agent-Credential": key_a2}
    get_mem_a2_res = await client.get(f"/api/v1/memories/{memory_id}", headers=headers_a2)
    assert get_mem_a2_res.status_code == 403

    # ==========================================
    # 5. GRANT READ ACCESS
    # ==========================================

    # A1 grants READ access to A2
    grant_res = await client.post(
        f"/api/v1/memories/{memory_id}/grants",
        json={
            "agent_id": agent_a2_id,
            "access_level": "READ",
            "expires_in_days": 5
        },
        headers=headers_a1
    )
    assert grant_res.status_code == 201
    assert grant_res.json()["access_level"] == "READ"
    assert grant_res.json()["granted_by_principal_type"] == "AGENT"
    assert grant_res.json()["granted_by_agent_id"] == agent_a1_id
    assert grant_res.json()["granted_by_user_id"] is None

    # A2 reads the memory successfully (READ allowed)
    get_mem_a2_granted = await client.get(f"/api/v1/memories/{memory_id}", headers=headers_a2)
    assert get_mem_a2_granted.status_code == 200
    assert get_mem_a2_granted.json()["content"] == "Tactical plans of Agent A1 updated."

    # A2 tries to update (WRITE denied -> should get 403 Forbidden)
    update_a2_res = await client.put(
        f"/api/v1/memories/{memory_id}",
        json={"content": "Malicious edit from Agent A2."},
        headers=headers_a2
    )
    assert update_a2_res.status_code == 403

    # ==========================================
    # 6. GRANT UPGRADE & UPSERT
    # ==========================================

    # A1 upgrades the grant to WRITE (tests upsert/re-grant)
    upgrade_res = await client.post(
        f"/api/v1/memories/{memory_id}/grants",
        json={
            "agent_id": agent_a2_id,
            "access_level": "WRITE"
        },
        headers=headers_a1
    )
    assert upgrade_res.status_code == 201
    assert upgrade_res.json()["access_level"] == "WRITE"

    # Verify only ONE grant is active by listing
    list_grants_res = await client.get(f"/api/v1/memories/{memory_id}/grants", headers=headers_a1)
    assert list_grants_res.status_code == 200
    assert len(list_grants_res.json()) == 1

    # A2 can now update (WRITE allowed)
    update_a2_success = await client.put(
        f"/api/v1/memories/{memory_id}",
        json={"content": "Collaborator edit from Agent A2."},
        headers=headers_a2
    )
    assert update_a2_success.status_code == 200
    assert update_a2_success.json()["content"] == "Collaborator edit from Agent A2."

    # A2 tries to delete (MANAGE denied -> should get 403 Forbidden)
    delete_a2_denied = await client.delete(f"/api/v1/memories/{memory_id}", headers=headers_a2)
    assert delete_a2_denied.status_code == 403

    # ==========================================
    # 7. REVOCATION
    # ==========================================

    # A1 revokes A2's access
    revoke_res = await client.post(
        f"/api/v1/memories/{memory_id}/grants/{agent_a2_id}/revoke",
        headers=headers_a1
    )
    assert revoke_res.status_code == 200
    assert "revoked_at" in revoke_res.json()

    # List grants should now return empty list (active grants only)
    list_grants_empty = await client.get(f"/api/v1/memories/{memory_id}/grants", headers=headers_a1)
    assert len(list_grants_empty.json()) == 0

    # A2 is blocked again (should return 403 for within-tenant unauthorized access)
    get_a2_blocked = await client.get(f"/api/v1/memories/{memory_id}", headers=headers_a2)
    assert get_a2_blocked.status_code == 403

    # ==========================================
    # 8. CROSS-TENANT ISOLATION
    # ==========================================

    # Agent B1 (Tenant B) tries to read memory -> should get 404 (does not exist in Tenant B)
    headers_b1 = {"X-Agent-Credential": key_b1}
    get_mem_b1_res = await client.get(f"/api/v1/memories/{memory_id}", headers=headers_b1)
    assert get_mem_b1_res.status_code == 404

    # Agent B1 tries to grant access to Agent A2 for this memory -> 404 Not Found
    grant_b1_res = await client.post(
        f"/api/v1/memories/{memory_id}/grants",
        json={
            "agent_id": agent_a2_id,
            "access_level": "READ"
        },
        headers=headers_b1
    )
    assert grant_b1_res.status_code == 404

    # Agent A1 tries to grant access to Agent B1 (cross-tenant target) -> 404 (Target Agent not found in Tenant A)
    grant_cross_res = await client.post(
        f"/api/v1/memories/{memory_id}/grants",
        json={
            "agent_id": agent_b1_id,
            "access_level": "READ"
        },
        headers=headers_a1
    )
    assert grant_cross_res.status_code == 404

    # ==========================================
    # 9. HUMAN USER ACCESS & GRANTS
    # ==========================================

    # Login User A back (via session cookie)
    client.cookies.clear()
    await client.post(
        "/api/v1/auth/login",
        json={"email": "tenantA@example.com", "password": "password123"}
    )

    # Human User A retrieves the memory successfully
    human_get_res = await client.get(f"/api/v1/memories/{memory_id}")
    assert human_get_res.status_code == 200
    assert human_get_res.json()["content"] == "Collaborator edit from Agent A2."

    # Human User A grants access to Agent A2 (re-grant upsert)
    human_grant_res = await client.post(
        f"/api/v1/memories/{memory_id}/grants",
        json={
            "agent_id": agent_a2_id,
            "access_level": "MANAGE"
        }
    )
    assert human_grant_res.status_code == 201
    assert human_grant_res.json()["granted_by_principal_type"] == "USER"
    assert human_grant_res.json()["granted_by_agent_id"] is None
    assert "granted_by_user_id" in human_grant_res.json()

    # Clear cookies again for agent verification
    client.cookies.clear()

    # Agent A2 can now soft-delete the memory (MANAGE allowed)
    delete_a2_res = await client.delete(f"/api/v1/memories/{memory_id}", headers=headers_a2)
    assert delete_a2_res.status_code == 204

    # Verify it is deleted (404/not active)
    get_mem_deleted = await client.get(f"/api/v1/memories/{memory_id}", headers=headers_a1)
    # The get_memory will raise KeyError because its status is DELETED
    assert get_mem_deleted.status_code == 404

    # ==========================================
    # 10. SUSPENDED AGENT RESTRICTIONS
    # ==========================================

    # Login User A back to suspend Agent A1
    await client.post(
        "/api/v1/auth/login",
        json={"email": "tenantA@example.com", "password": "password123"}
    )

    # Suspend Agent A1
    suspend_res = await client.post(
        f"/api/v1/agents/{agent_a1_id}/suspend"
    )
    assert suspend_res.status_code == 200

    # Clear cookies
    client.cookies.clear()

    # Agent A1 attempts to create a new memory -> 401 Unauthorized
    failed_create_res = await client.post(
        "/api/v1/memories",
        json={
            "content": "Tactical post-suspension plan.",
            "memory_type": "Fact",
            "importance": 0.8,
            "confidence": 0.8,
            "memory_system": "Semantic"
        },
        headers=headers_a1
    )
    assert failed_create_res.status_code == 401
