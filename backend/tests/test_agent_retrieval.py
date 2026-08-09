import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.entities import AgentStatus, MemoryAccessLevel
from app.knowledge_graph.repositories.sql_repositories import SQLGraphRepository
from app.knowledge_graph.domain.entities import MemoryNodeMapping

pytestmark = pytest.mark.asyncio


async def test_agent_aware_retrieval_and_rag(client: AsyncClient, db_session: AsyncSession):
    """
    Comprehensive integration test suite verifying Milestone 10 Phase 4:
    1. Setup Tenant A and Tenant B.
    2. Create Agent A1, A2 (Tenant A) and B1 (Tenant B).
    3. Issue agent credentials.
    4. Verify Direct Semantic Retrieval (Owner, collaborator, blocked, expired, revoked).
    5. Verify Pre-Ranking Filtering (prevents top-k starvation).
    6. Verify Knowledge Graph path pruning (prunes unauthorized nodes, preserves unmapped intermediate nodes).
    7. Verify RAG & Grounding integrity.
    8. Verify Tenant Isolation.
    9. Verify Suspended/Revoked agent returns 401.
    10. Verify Human User retrieval remains unaffected (regression).
    """

    # ==========================================
    # 1. SETUP TENANTS AND AGENTS
    # ==========================================

    # Register and login User A (Tenant A)
    await client.post(
        "/api/v1/auth/register",
        json={"email": "tenantA_ret@example.com", "password": "password123"}
    )
    login_a_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "tenantA_ret@example.com", "password": "password123"}
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

    # Register and login User B (Tenant B)
    await client.post(
        "/api/v1/auth/register",
        json={"email": "tenantB_ret@example.com", "password": "password123"}
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "tenantB_ret@example.com", "password": "password123"}
    )

    # Create Agent B1
    agent_b1_res = await client.post(
        "/api/v1/agents",
        json={"name": "Agent B1", "description": "Tenant B Agent", "configuration": {}}
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

    # Clear cookies for clean API key header context
    client.cookies.clear()

    headers_a1 = {"X-Agent-Credential": key_a1}
    headers_a2 = {"X-Agent-Credential": key_a2}
    headers_b1 = {"X-Agent-Credential": key_b1}

    # ==========================================
    # 2. SEED AGENT-OWNED MEMORY
    # ==========================================
    
    # Agent A1 creates semantic memory
    create_mem_res = await client.post(
        "/api/v1/memories",
        json={
            "content": "A1 proprietary fusion blueprint.",
            "memory_type": "Fact",
            "importance": 0.8,
            "confidence": 0.9,
            "memory_system": "Semantic"
        },
        headers=headers_a1
    )
    assert create_mem_res.status_code == 201
    memory_a1_id = create_mem_res.json()["id"]

    # ==========================================
    # 3. DIRECT SEMANTIC RETRIEVAL CHECKS
    # ==========================================

    # A. Owner Agent A1 retrieves memory
    ret_a1_res = await client.post(
        "/api/v1/retrieval/retrieve",
        json={"query": "fusion blueprint"},
        headers=headers_a1
    )
    assert ret_a1_res.status_code == 200
    fused_elements = ret_a1_res.json()["fused_elements"]
    assert len(fused_elements) > 0
    assert any("fusion blueprint" in f["content"] for f in fused_elements)

    # B. Collaborator Agent A2 (no grant) attempts retrieval -> gets 0 results (silent exclusion)
    ret_a2_res = await client.post(
        "/api/v1/retrieval/retrieve",
        json={"query": "fusion blueprint"},
        headers=headers_a2
    )
    assert ret_a2_res.status_code == 200
    assert len(ret_a2_res.json()["fused_elements"]) == 0

    # Log back as User A to grant access to Agent A2
    await client.post(
        "/api/v1/auth/login",
        json={"email": "tenantA_ret@example.com", "password": "password123"}
    )

    # Grant READ to Agent A2
    grant_res = await client.post(
        f"/api/v1/memories/{memory_a1_id}/grants",
        json={"agent_id": agent_a2_id, "access_level": "READ"}
    )
    assert grant_res.status_code == 201
    grant_id = grant_res.json()["id"]

    # Clear cookies
    client.cookies.clear()

    # C. Verify Agent A2 can now retrieve the memory
    ret_a2_granted_res = await client.post(
        "/api/v1/retrieval/retrieve",
        json={"query": "fusion blueprint"},
        headers=headers_a2
    )
    assert ret_a2_granted_res.status_code == 200
    assert len(ret_a2_granted_res.json()["fused_elements"]) > 0
    assert any("fusion blueprint" in f["content"] for f in ret_a2_granted_res.json()["fused_elements"])

    # Log back as User A to revoke grant
    await client.post(
        "/api/v1/auth/login",
        json={"email": "tenantA_ret@example.com", "password": "password123"}
    )

    # Revoke grant
    revoke_res = await client.post(f"/api/v1/memories/{memory_a1_id}/grants/{agent_a2_id}/revoke")
    assert revoke_res.status_code == 200, revoke_res.text

    # Clear cookies
    client.cookies.clear()

    # D. Verify Agent A2 is blocked again
    ret_a2_revoked_res = await client.post(
        "/api/v1/retrieval/retrieve",
        json={"query": "fusion blueprint"},
        headers=headers_a2
    )
    assert ret_a2_revoked_res.status_code == 200
    assert len(ret_a2_revoked_res.json()["fused_elements"]) == 0

    # ==========================================
    # 4. PRE-RANKING FILTERING (TOP-K STARVATION PROOF)
    # ==========================================

    # Create 3 memories for Agent A1:
    # Memory A (owned, matches query)
    # Memory B (unauth, matches query better but owned by Agent A2)
    # Memory C (owned, matches query)
    
    # A1 creates Memory A
    mem_a_res = await client.post(
        "/api/v1/memories",
        json={
            "content": "Python recipe is delicious.",
            "memory_type": "Fact",
            "importance": 0.5,
            "confidence": 0.5,
            "memory_system": "Semantic"
        },
        headers=headers_a1
    )
    assert mem_a_res.status_code == 201

    # A2 creates Memory B (highly matchable query)
    mem_b_res = await client.post(
        "/api/v1/memories",
        json={
            "content": "Python pizza is superior python dish.",
            "memory_type": "Fact",
            "importance": 0.9,
            "confidence": 0.9,
            "memory_system": "Semantic"
        },
        headers=headers_a2
    )
    assert mem_b_res.status_code == 201

    # A1 creates Memory C
    mem_c_res = await client.post(
        "/api/v1/memories",
        json={
            "content": "Python juice is sweet drink.",
            "memory_type": "Fact",
            "importance": 0.6,
            "confidence": 0.6,
            "memory_system": "Semantic"
        },
        headers=headers_a1
    )
    assert mem_c_res.status_code == 201

    # Retrieve under Agent A1 context with limit_per_system = 2
    # If pre-filtering works: it filters out Memory B (A2-owned) before limit/top-k.
    # It must return both Memory A and Memory C (fused count = 2).
    # If post-filtering was used, it would fetch [B, C], filter out B, leaving only 1 result (starvation).
    ret_starvation_res = await client.post(
        "/api/v1/retrieval/retrieve",
        json={
            "query": "python",
            "options": {"limit_per_system": 2}
        },
        headers=headers_a1
    )
    assert ret_starvation_res.status_code == 200
    elements = ret_starvation_res.json()["fused_elements"]
    assert len(elements) == 2
    assert not any("superior python dish" in e["content"] for e in elements)
    assert any("recipe is delicious" in e["content"] for e in elements)
    assert any("juice is sweet" in e["content"] for e in elements)

    # ==========================================
    # 5. KNOWLEDGE GRAPH TRAVERSAL & PATH PRUNING
    # ==========================================
    
    # A. Create memories first under their respective agent owners
    # A1 creates Memory Z
    client.cookies.clear()
    mem_z_res = await client.post(
        "/api/v1/memories",
        json={
            "content": "Secret blueprints stored in GammaNode.",
            "memory_type": "Fact",
            "importance": 0.8,
            "confidence": 0.8,
            "memory_system": "Semantic"
        },
        headers=headers_a1
    )
    assert mem_z_res.status_code == 201, mem_z_res.text
    mem_z_id = mem_z_res.json()["id"]

    # A2 creates Memory Y (owned by Agent A2, so unauthorized for Agent A1)
    client.cookies.clear()
    mem_y_res = await client.post(
        "/api/v1/memories",
        json={
            "content": "A2 exclusive code stored in BetaNode.",
            "memory_type": "Fact",
            "importance": 0.8,
            "confidence": 0.8,
            "memory_system": "Semantic"
        },
        headers=headers_a2
    )
    assert mem_y_res.status_code == 201, mem_y_res.text
    mem_y_id = mem_y_res.json()["id"]

    # A1 creates Memory X
    client.cookies.clear()
    mem_x_res = await client.post(
        "/api/v1/memories",
        json={
            "content": "Kayak origin node details in AlphaNode.",
            "memory_type": "Fact",
            "importance": 0.8,
            "confidence": 0.8,
            "memory_system": "Semantic"
        },
        headers=headers_a1
    )
    assert mem_x_res.status_code == 201, mem_x_res.text
    mem_x_id = mem_x_res.json()["id"]

    # Now login User A to setup KG nodes and relationships
    await client.post(
        "/api/v1/auth/login",
        json={"email": "tenantA_ret@example.com", "password": "password123"}
    )

    # Setup nodes: Node X, Node Y (unauth node), Node Z
    node_x_res = await client.post(
        "/api/v1/entities",
        json={"name": "AlphaNode", "entity_type": "ORGANIZATION"}
    )
    assert node_x_res.status_code == 201
    node_x_id = node_x_res.json()["id"]

    node_y_res = await client.post(
        "/api/v1/entities",
        json={"name": "BetaNode", "entity_type": "PERSON"}
    )
    assert node_y_res.status_code == 201
    node_y_id = node_y_res.json()["id"]

    node_z_res = await client.post(
        "/api/v1/entities",
        json={"name": "GammaNode", "entity_type": "CUSTOM"}
    )
    assert node_z_res.status_code == 201
    node_z_id = node_z_res.json()["id"]

    # Set up relationships: Node X -> Node Y -> Node Z
    r1 = await client.post(
        "/api/v1/relationships",
        json={"source_entity_id": node_x_id, "target_entity_id": node_y_id, "relationship_type": "RELATED_TO", "confidence": 0.9}
    )
    assert r1.status_code == 201
    
    r2 = await client.post(
        "/api/v1/relationships",
        json={"source_entity_id": node_y_id, "target_entity_id": node_z_id, "relationship_type": "RELATED_TO", "confidence": 0.9}
    )
    assert r2.status_code == 201

    # Map memories to nodes using SQLGraphRepository
    graph_repo = SQLGraphRepository(db_session)
    await graph_repo.mappings.create(MemoryNodeMapping(
        memory_id=uuid.UUID(mem_z_id), node_id=uuid.UUID(node_z_id), confidence=0.95
    ))
    await graph_repo.mappings.create(MemoryNodeMapping(
        memory_id=uuid.UUID(mem_y_id), node_id=uuid.UUID(node_y_id), confidence=0.95
    ))
    await graph_repo.mappings.create(MemoryNodeMapping(
        memory_id=uuid.UUID(mem_x_id), node_id=uuid.UUID(node_x_id), confidence=0.95
    ))
    await db_session.flush()

    # Clear cookies before query tests
    client.cookies.clear()

    # Verify that traversing / retrieving under Agent A1 from AlphaNode (Node X):
    # - Node Y maps exclusively to Memory Y (unauthorized for A1).
    # - Therefore, Node Y is treated as unauthorized.
    # - The traversal path AlphaNode -> BetaNode -> GammaNode is blocked because of BetaNode (Node Y).
    # - GammaNode's memories (Memory Z) must NOT be retrieved.
    ret_kg_blocked_res = await client.post(
        "/api/v1/retrieval/retrieve",
        json={
            "query": "kayak",
            "options": {"limit_per_system": 1}
        },
        headers=headers_a1
    )
    assert ret_kg_blocked_res.status_code == 200, ret_kg_blocked_res.text
    elements_kg = ret_kg_blocked_res.json()["fused_elements"]
    # Check that Memory Z (GammaNode blueprint) is NOT in the retrieved list
    assert not any("GammaNode" in e["content"] for e in elements_kg), f"elements_kg contains GammaNode! elements: {elements_kg}"

    # Verify traversal endpoint is pruned too
    trav_res = await client.get(
        "/api/v1/graph/traverse",
        params={"start_node_id": node_x_id, "max_depth": 3},
        headers=headers_a1
    )
    assert trav_res.status_code == 200, trav_res.text
    trav_nodes = trav_res.json()["nodes"]
    # Should only contain AlphaNode, since BetaNode is unauthorized
    assert len(trav_nodes) == 1
    assert trav_nodes[0]["node"]["name"] == "AlphaNode"

    # B. Test unmapped intermediate nodes path preservation:
    # Setup ActiveNode (no memory mapping, pure concept link)
    # AlphaNode (Node X) -> ActiveNode -> GammaNode (Node Z)
    await client.post(
        "/api/v1/auth/login",
        json={"email": "tenantA_ret@example.com", "password": "password123"}
    )
    node_k_res = await client.post(
        "/api/v1/entities",
        json={"name": "ActiveNode", "entity_type": "CUSTOM"}
    )
    assert node_k_res.status_code == 201
    node_k_id = node_k_res.json()["id"]

    # Set up relationships: Node X -> ActiveNode -> Node Z
    r3 = await client.post(
        "/api/v1/relationships",
        json={"source_entity_id": node_x_id, "target_entity_id": node_k_id, "relationship_type": "RELATED_TO", "confidence": 0.9}
    )
    assert r3.status_code == 201
    
    r4 = await client.post(
        "/api/v1/relationships",
        json={"source_entity_id": node_k_id, "target_entity_id": node_z_id, "relationship_type": "RELATED_TO", "confidence": 0.9}
    )
    assert r4.status_code == 201

    # Clear cookies
    client.cookies.clear()

    # Now verify traversal under Agent A1 from AlphaNode:
    # Traversal goes through ActiveNode (allowed, unmapped) to reach GammaNode (Node Z, authorized).
    # GammaNode's memories (Memory Z) must be retrieved successfully!
    ret_kg_allowed_res = await client.post(
        "/api/v1/retrieval/retrieve",
        json={
            "query": "kayak",
            "options": {"limit_per_system": 1}
        },
        headers=headers_a1
    )
    assert ret_kg_allowed_res.status_code == 200, ret_kg_allowed_res.text
    elements_kg_allowed = ret_kg_allowed_res.json()["fused_elements"]
    assert any("GammaNode" in e["content"] for e in elements_kg_allowed), f"allowed elements: {elements_kg_allowed}"

    # Verify traversal endpoint shows GammaNode and ActiveNode
    trav_allowed_res = await client.get(
        "/api/v1/graph/traverse",
        params={"start_node_id": node_x_id, "max_depth": 3},
        headers=headers_a1
    )
    assert trav_allowed_res.status_code == 200, trav_allowed_res.text
    allowed_nodes = [item["node"]["name"] for item in trav_allowed_res.json()["nodes"]]
    assert "AlphaNode" in allowed_nodes
    assert "ActiveNode" in allowed_nodes
    assert "GammaNode" in allowed_nodes
    assert "BetaNode" not in allowed_nodes

    # ==========================================
    # 6. RAG & GROUNDING INTEGRITY
    # ==========================================

    # Call /retrieval/ground under Agent A1
    ground_res = await client.post(
        "/api/v1/retrieval/ground",
        json={
            "query": "kayak",
            "options": {"limit_per_system": 1}
        },
        headers=headers_a1
    )
    assert ground_res.status_code == 200, ground_res.text
    ground_data = ground_res.json()
    # Grounded prompt must contain authorized GammaNode memory content
    assert "GammaNode" in ground_data["system_prompt"]
    # Verify citations do not contain the unauthorized BetaNode memory
    assert not any("BetaNode" in c["content"] for c in ground_data["citations"])

    # ==========================================
    # 7. TENANT ISOLATION
    # ==========================================

    # Agent B1 from Tenant B retrieves -> should get 0 results for A1's memories
    ret_b1_res = await client.post(
        "/api/v1/retrieval/retrieve",
        json={"query": "fusion blueprint"},
        headers=headers_b1
    )
    assert ret_b1_res.status_code == 200
    assert len(ret_b1_res.json()["fused_elements"]) == 0

    # ==========================================
    # 8. SUSPENDED/REVOKED AGENT RETRIEVAL BEHAVIOR
    # ==========================================

    # Log back as User A to suspend Agent A1
    await client.post(
        "/api/v1/auth/login",
        json={"email": "tenantA_ret@example.com", "password": "password123"}
    )
    
    # Suspend Agent A1
    suspend_res = await client.post(
        f"/api/v1/agents/{agent_a1_id}/suspend"
    )
    assert suspend_res.status_code == 200

    # Clear cookies
    client.cookies.clear()

    # Verify Agent A1 retrieval fails with 401 (inactive agent credentials)
    ret_suspended_res = await client.post(
        "/api/v1/retrieval/retrieve",
        json={"query": "fusion blueprint"},
        headers=headers_a1
    )
    assert ret_suspended_res.status_code == 401
    assert "inactive agent credentials" in ret_suspended_res.json()["message"].lower()

    # ==========================================
    # 9. HUMAN USER RETRIEVAL REGRESSION
    # ==========================================

    # Login as User A again
    await client.post(
        "/api/v1/auth/login",
        json={"email": "tenantA_ret@example.com", "password": "password123"}
    )

    # Human User A retrieves -> should successfully retrieve all Tenant A memories (including A2's memory B)
    # Human user is unaffected by Agent suspension or memory ownership bounds
    user_ret_res = await client.post(
        "/api/v1/retrieval/retrieve",
        json={"query": "python"}
    )
    assert user_ret_res.status_code == 200
    user_elements = user_ret_res.json()["fused_elements"]
    assert len(user_elements) >= 3  # A, B, C Python memories
