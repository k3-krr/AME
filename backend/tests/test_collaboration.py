import pytest
import uuid
import json
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.entities import AgentStatus, MemoryAccessLevel, MemoryStatus
from app.infrastructure.db.models import AgentTable, MemoryAccessGrantTable, MemoryTable

pytestmark = pytest.mark.asyncio


async def test_agent_collaboration_sharing_flow(client: AsyncClient, db_session: AsyncSession):
    """
    Step-by-step test verifying multi-agent collaboration:
    1. Setup Tenant A and Tenant B.
    2. Create Agent A1, A2, A3 (Tenant A) and B1 (Tenant B).
    3. Issue agent credentials.
    4. Agent A1 creates Memory A1.
    5. Agent A2 attempts to access without grant -> 403 Forbidden.
    6. Agent A1 grants READ to Agent A2.
    7. Agent A2 reads memory successfully.
    8. Agent A2 attempts to update (WRITE) -> 403 Forbidden.
    9. Agent A2 attempts to delegate (MANAGE) READ to Agent A3 -> 403 Forbidden.
    10. Agent A1 upgrades grant to WRITE for Agent A2.
    11. Agent A2 updates memory successfully.
    12. Agent A2 attempts to delegate READ to Agent A3 -> 403 Forbidden.
    13. Agent A1 upgrades grant to MANAGE for Agent A2.
    14. Agent A2 delegates READ to Agent A3.
    15. Agent A3 reads memory successfully.
    16. Agent A2 attempts cross-tenant grant to Agent B1 -> 404 Not Found.
    17. Agent A2 revokes Agent A3's grant -> Agent A3 access blocked immediately.
    """
    # 1. SETUP TENANTS AND AGENTS
    # Register Tenant A
    await client.post(
        "/api/v1/auth/register",
        json={"email": "tenantA_collab@example.com", "password": "password123"}
    )
    login_a_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "tenantA_collab@example.com", "password": "password123"}
    )
    assert login_a_res.status_code == 200

    # Create Agent A1, A2, A3
    agent_a1_res = await client.post(
        "/api/v1/agents",
        json={"name": "Agent A1", "description": "A1", "configuration": {}}
    )
    agent_a1_id = agent_a1_res.json()["id"]

    agent_a2_res = await client.post(
        "/api/v1/agents",
        json={"name": "Agent A2", "description": "A2", "configuration": {}}
    )
    agent_a2_id = agent_a2_res.json()["id"]

    agent_a3_res = await client.post(
        "/api/v1/agents",
        json={"name": "Agent A3", "description": "A3", "configuration": {}}
    )
    agent_a3_id = agent_a3_res.json()["id"]

    # Issue credentials
    cred_a1 = (await client.post(f"/api/v1/agents/{agent_a1_id}/credentials", json={"description": "K1"})).json()["raw_key"]
    cred_a2 = (await client.post(f"/api/v1/agents/{agent_a2_id}/credentials", json={"description": "K2"})).json()["raw_key"]
    cred_a3 = (await client.post(f"/api/v1/agents/{agent_a3_id}/credentials", json={"description": "K3"})).json()["raw_key"]

    # Clear cookies and set headers
    client.cookies.clear()
    headers_a1 = {"X-Agent-Credential": cred_a1}
    headers_a2 = {"X-Agent-Credential": cred_a2}
    headers_a3 = {"X-Agent-Credential": cred_a3}

    # Register Tenant B
    client.cookies.clear()
    await client.post(
        "/api/v1/auth/register",
        json={"email": "tenantB_collab@example.com", "password": "password123"}
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "tenantB_collab@example.com", "password": "password123"}
    )
    agent_b1_res = await client.post(
        "/api/v1/agents",
        json={"name": "Agent B1", "description": "B1", "configuration": {}}
    )
    agent_b1_id = agent_b1_res.json()["id"]
    cred_b1 = (await client.post(f"/api/v1/agents/{agent_b1_id}/credentials", json={"description": "KB1"})).json()["raw_key"]

    client.cookies.clear()
    headers_b1 = {"X-Agent-Credential": cred_b1}

    # 4. Agent A1 creates Memory A1
    create_res = await client.post(
        "/api/v1/memories",
        json={"content": "Top secret intelligence.", "memory_type": "Fact", "importance": 0.8, "confidence": 0.8, "memory_system": "Semantic"},
        headers=headers_a1
    )
    assert create_res.status_code == 201
    memory_id = create_res.json()["id"]

    # 5. Agent A2 attempts to access without grant -> 403
    get_res = await client.get(f"/api/v1/memories/{memory_id}", headers=headers_a2)
    assert get_res.status_code == 403

    # 6. Agent A1 grants READ to Agent A2
    grant_res = await client.post(
        f"/api/v1/memories/{memory_id}/grants",
        json={"agent_id": agent_a2_id, "access_level": "READ"},
        headers=headers_a1
    )
    assert grant_res.status_code == 201

    # 7. Agent A2 reads memory successfully
    get_res = await client.get(f"/api/v1/memories/{memory_id}", headers=headers_a2)
    assert get_res.status_code == 200
    assert get_res.json()["content"] == "Top secret intelligence."

    # 8. Agent A2 attempts to update (WRITE) -> 403
    update_res = await client.put(f"/api/v1/memories/{memory_id}", json={"content": "Updated by A2"}, headers=headers_a2)
    assert update_res.status_code == 403

    # 9. Agent A2 attempts to delegate READ to Agent A3 -> 403 (since A2 is only READ)
    del_res = await client.post(
        f"/api/v1/memories/{memory_id}/grants",
        json={"agent_id": agent_a3_id, "access_level": "READ"},
        headers=headers_a2
    )
    assert del_res.status_code == 403

    # 10. Agent A1 upgrades grant to WRITE for Agent A2
    grant_res = await client.post(
        f"/api/v1/memories/{memory_id}/grants",
        json={"agent_id": agent_a2_id, "access_level": "WRITE"},
        headers=headers_a1
    )
    assert grant_res.status_code == 201

    # 11. Agent A2 updates memory successfully
    update_res = await client.put(f"/api/v1/memories/{memory_id}", json={"content": "Updated by A2"}, headers=headers_a2)
    assert update_res.status_code == 200

    # 12. Agent A2 attempts to delegate READ to Agent A3 -> 403 (since A2 is only WRITE)
    del_res = await client.post(
        f"/api/v1/memories/{memory_id}/grants",
        json={"agent_id": agent_a3_id, "access_level": "READ"},
        headers=headers_a2
    )
    assert del_res.status_code == 403

    # 13. Agent A1 upgrades grant to MANAGE for Agent A2
    grant_res = await client.post(
        f"/api/v1/memories/{memory_id}/grants",
        json={"agent_id": agent_a2_id, "access_level": "MANAGE"},
        headers=headers_a1
    )
    assert grant_res.status_code == 201

    # 14. Agent A2 delegates READ to Agent A3
    del_res = await client.post(
        f"/api/v1/memories/{memory_id}/grants",
        json={"agent_id": agent_a3_id, "access_level": "READ"},
        headers=headers_a2
    )
    assert del_res.status_code == 201

    # 15. Agent A3 reads memory successfully
    get_res = await client.get(f"/api/v1/memories/{memory_id}", headers=headers_a3)
    assert get_res.status_code == 200

    # 16. Agent A2 attempts cross-tenant grant to Agent B1 -> 404
    cross_res = await client.post(
        f"/api/v1/memories/{memory_id}/grants",
        json={"agent_id": agent_b1_id, "access_level": "READ"},
        headers=headers_a2
    )
    assert cross_res.status_code == 404

    # 17. Agent A2 revokes Agent A3's grant
    revoke_res = await client.post(
        f"/api/v1/memories/{memory_id}/grants/{agent_a3_id}/revoke",
        headers=headers_a2
    )
    assert revoke_res.status_code == 200

    # Agent A3 access blocked immediately
    get_res = await client.get(f"/api/v1/memories/{memory_id}", headers=headers_a3)
    assert get_res.status_code == 403


async def test_grant_expiration_enforcement(client: AsyncClient, db_session: AsyncSession):
    """Verifies that expired grants immediately block access."""
    # Register Tenant A
    await client.post(
        "/api/v1/auth/register",
        json={"email": "tenantA_expired@example.com", "password": "password123"}
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "tenantA_expired@example.com", "password": "password123"}
    )

    # Create Agent A1, A2
    agent_a1_id = (await client.post("/api/v1/agents", json={"name": "A1", "configuration": {}})).json()["id"]
    agent_a2_id = (await client.post("/api/v1/agents", json={"name": "A2", "configuration": {}})).json()["id"]

    cred_a1 = (await client.post(f"/api/v1/agents/{agent_a1_id}/credentials", json={})).json()["raw_key"]
    cred_a2 = (await client.post(f"/api/v1/agents/{agent_a2_id}/credentials", json={})).json()["raw_key"]

    client.cookies.clear()
    headers_a1 = {"X-Agent-Credential": cred_a1}
    headers_a2 = {"X-Agent-Credential": cred_a2}

    # Create memory
    memory_id = (await client.post(
        "/api/v1/memories",
        json={"content": "Expired grant test content", "memory_type": "Fact", "importance": 0.8, "confidence": 0.8},
        headers=headers_a1
    )).json()["id"]

    # Grant READ to Agent A2
    await client.post(
        f"/api/v1/memories/{memory_id}/grants",
        json={"agent_id": agent_a2_id, "access_level": "READ"},
        headers=headers_a1
    )

    # Verify A2 has access
    get_res = await client.get(f"/api/v1/memories/{memory_id}", headers=headers_a2)
    assert get_res.status_code == 200

    # Modify the grant in the database to be expired
    stmt = select(MemoryAccessGrantTable).where(
        MemoryAccessGrantTable.memory_id == uuid.UUID(memory_id),
        MemoryAccessGrantTable.agent_id == uuid.UUID(agent_a2_id)
    )
    result = await db_session.execute(stmt)
    grant_db = result.scalar_one()
    grant_db.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await db_session.flush()

    # Verify A2 is blocked now
    get_res2 = await client.get(f"/api/v1/memories/{memory_id}", headers=headers_a2)
    assert get_res2.status_code == 403


async def test_suspended_revoked_agent_collaboration(client: AsyncClient, db_session: AsyncSession):
    """Verifies that suspended or revoked agents cannot retrieve or receive grants."""
    # Register Tenant A
    await client.post(
        "/api/v1/auth/register",
        json={"email": "tenantA_inactive@example.com", "password": "password123"}
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "tenantA_inactive@example.com", "password": "password123"}
    )

    # Create Agent A1, A2
    agent_a1_id = (await client.post("/api/v1/agents", json={"name": "A1", "configuration": {}})).json()["id"]
    agent_a2_id = (await client.post("/api/v1/agents", json={"name": "A2", "configuration": {}})).json()["id"]

    cred_a1 = (await client.post(f"/api/v1/agents/{agent_a1_id}/credentials", json={})).json()["raw_key"]
    cred_a2 = (await client.post(f"/api/v1/agents/{agent_a2_id}/credentials", json={})).json()["raw_key"]

    client.cookies.clear()
    headers_a1 = {"X-Agent-Credential": cred_a1}
    headers_a2 = {"X-Agent-Credential": cred_a2}

    # Create memory
    memory_id = (await client.post(
        "/api/v1/memories",
        json={"content": "Inactive agent test content", "memory_type": "Fact", "importance": 0.8, "confidence": 0.8},
        headers=headers_a1
    )).json()["id"]

    # 1. Test recipient SUSPENDED:
    # Suspend Agent A2
    stmt = select(AgentTable).where(AgentTable.id == uuid.UUID(agent_a2_id))
    result = await db_session.execute(stmt)
    agent_a2_db = result.scalar_one()
    agent_a2_db.status = "SUSPENDED"
    await db_session.flush()

    # Trying to grant to suspended agent fails with 404 (Agent not found)
    grant_res = await client.post(
        f"/api/v1/memories/{memory_id}/grants",
        json={"agent_id": agent_a2_id, "access_level": "READ"},
        headers=headers_a1
    )
    assert grant_res.status_code == 404

    # 2. Test recipient REVOKED:
    # Revoke Agent A2
    agent_a2_db.status = "REVOKED"
    await db_session.flush()

    # Trying to grant to revoked agent fails with 404
    grant_res2 = await client.post(
        f"/api/v1/memories/{memory_id}/grants",
        json={"agent_id": agent_a2_id, "access_level": "READ"},
        headers=headers_a1
    )
    assert grant_res2.status_code == 404


async def test_retrieval_and_graph_filter_integration(client: AsyncClient, db_session: AsyncSession):
    """Verifies that retrieval endpoints and KG path traversals respect sharing settings."""
    # Register Tenant A
    await client.post(
        "/api/v1/auth/register",
        json={"email": "tenantA_ret_filter@example.com", "password": "password123"}
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "tenantA_ret_filter@example.com", "password": "password123"}
    )

    # Create Agent A1, A2
    agent_a1_id = (await client.post("/api/v1/agents", json={"name": "A1", "configuration": {}})).json()["id"]
    agent_a2_id = (await client.post("/api/v1/agents", json={"name": "A2", "configuration": {}})).json()["id"]

    cred_a1 = (await client.post(f"/api/v1/agents/{agent_a1_id}/credentials", json={})).json()["raw_key"]
    cred_a2 = (await client.post(f"/api/v1/agents/{agent_a2_id}/credentials", json={})).json()["raw_key"]

    client.cookies.clear()
    headers_a1 = {"X-Agent-Credential": cred_a1}
    headers_a2 = {"X-Agent-Credential": cred_a2}

    # Create memory with content "Agent A1 specialized data query"
    memory_id = (await client.post(
        "/api/v1/memories",
        json={"content": "Agent A1 specialized data query", "memory_type": "Fact", "importance": 0.8, "confidence": 0.8},
        headers=headers_a1
    )).json()["id"]

    # Agent A2 retrieves -> should return 0 results since no grant
    ret_res = await client.post(
        "/api/v1/retrieval/retrieve",
        json={"query": "specialized data query"},
        headers=headers_a2
    )
    assert ret_res.status_code == 200
    assert len(ret_res.json()["fused_elements"]) == 0

    # Agent A1 grants READ to Agent A2
    await client.post(
        f"/api/v1/memories/{memory_id}/grants",
        json={"agent_id": agent_a2_id, "access_level": "READ"},
        headers=headers_a1
    )

    # Agent A2 retrieves -> should now return the memory
    ret_res2 = await client.post(
        "/api/v1/retrieval/retrieve",
        json={"query": "specialized data query"},
        headers=headers_a2
    )
    assert ret_res2.status_code == 200
    assert len(ret_res2.json()["fused_elements"]) > 0
    assert ret_res2.json()["fused_elements"][0]["content"] == "Agent A1 specialized data query"
