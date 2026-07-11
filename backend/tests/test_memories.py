import pytest
import uuid
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_memory_unauthorized_access(client: AsyncClient):
    """Test that memories endpoints return 401 when not authenticated."""
    # List memories
    response = await client.get("/api/v1/memories")
    assert response.status_code == 401
    assert response.json()["error_code"] == "UNAUTHORIZED"

    # Create memory
    response = await client.post(
        "/api/v1/memories",
        json={
            "content": "A fact",
            "memory_type": "Fact",
            "importance": 0.5,
            "confidence": 0.9,
        }
    )
    assert response.status_code == 401


async def test_memory_crud_cycle(client: AsyncClient):
    """Test creating, reading, updating, listing, and soft-deleting user memories."""
    # 1. Register & Authenticate User A
    await client.post(
        "/api/v1/auth/register",
        json={"email": "memorytestA@example.com", "password": "password123"}
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "memorytestA@example.com", "password": "password123"}
    )
    assert login_resp.status_code == 200

    # 2. Create a conversation linked memory
    conv_resp = await client.post(
        "/api/v1/conversations",
        json={"title": "Memory Conv"}
    )
    conv_id = conv_resp.json()["id"]

    create_resp = await client.post(
        "/api/v1/memories",
        json={
            "conversation_id": conv_id,
            "content": "User prefers Dark Mode settings. ",  # with trailing whitespace
            "memory_type": "Preference",
            "importance": 0.8,
            "confidence": 0.95,
            "metadata": {"source": "manual_input"}
        }
    )
    assert create_resp.status_code == 201
    data = create_resp.json()
    assert data["id"] is not None
    assert data["conversation_id"] == conv_id
    assert data["content"] == "User prefers Dark Mode settings. "
    assert data["memory_type"] == "Preference"
    assert data["importance"] == 0.8
    assert data["confidence"] == 0.95
    assert data["status"] == "ACTIVE"
    assert data["version"] == 1
    assert data["metadata"] == {"source": "manual_input"}
    memory_id = data["id"]

    # 3. Read specific memory detail
    get_resp = await client.get(f"/api/v1/memories/{memory_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["content"] == "User prefers Dark Mode settings. "

    # 4. Update memory details
    update_resp = await client.put(
        f"/api/v1/memories/{memory_id}",
        json={
            "importance": 0.9,
            "metadata": {"source": "system_auto", "updated": True}
        }
    )
    assert update_resp.status_code == 200
    updated_data = update_resp.json()
    assert updated_data["importance"] == 0.9
    assert updated_data["version"] == 2
    assert updated_data["metadata"] == {"source": "system_auto", "updated": True}

    # 5. List memories
    list_resp = await client.get("/api/v1/memories")
    assert list_resp.status_code == 200
    memories = list_resp.json()
    assert len(memories) >= 1
    assert any(m["id"] == memory_id for m in memories)

    # 6. Soft Delete
    delete_resp = await client.delete(f"/api/v1/memories/{memory_id}")
    assert delete_resp.status_code == 204

    # 7. Verify soft delete (status is DELETED but record is retrievable)
    get_deleted_resp = await client.get(f"/api/v1/memories/{memory_id}")
    assert get_deleted_resp.status_code == 200
    assert get_deleted_resp.json()["status"] == "DELETED"


async def test_memory_validations(client: AsyncClient):
    """Test validation boundaries for memory fields."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "memoryval@example.com", "password": "password123"}
    )

    # Importance too high
    r1 = await client.post(
        "/api/v1/memories",
        json={"content": "fact", "memory_type": "Fact", "importance": 1.1, "confidence": 0.5}
    )
    assert r1.status_code == 422

    # Confidence negative
    r2 = await client.post(
        "/api/v1/memories",
        json={"content": "fact", "memory_type": "Fact", "importance": 0.5, "confidence": -0.2}
    )
    assert r2.status_code == 422

    # Empty content
    r3 = await client.post(
        "/api/v1/memories",
        json={"content": "   ", "memory_type": "Fact", "importance": 0.5, "confidence": 0.5}
    )
    assert r3.status_code == 422


async def test_duplicate_active_memory_blocking(client: AsyncClient):
    """Test that duplicate active memories inside a single conversation are rejected."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "duplicate@example.com", "password": "password123"}
    )

    # Create conversation
    conv_resp = await client.post("/api/v1/conversations", json={"title": "Dup Conv"})
    conv_id = conv_resp.json()["id"]

    # Post initial memory
    r1 = await client.post(
        "/api/v1/memories",
        json={
            "conversation_id": conv_id,
            "content": "User loves Python coding.",
            "memory_type": "Preference",
            "importance": 0.5,
            "confidence": 0.5
        }
    )
    assert r1.status_code == 201

    # Post duplicate memory with identical normalized content (different spacing and casing)
    r2 = await client.post(
        "/api/v1/memories",
        json={
            "conversation_id": conv_id,
            "content": "  USER  LOVES  python  CODING.  ",
            "memory_type": "Preference",
            "importance": 0.5,
            "confidence": 0.5
        }
    )
    # Returns 409 Conflict
    assert r2.status_code == 409
    assert "already exists" in r2.json()["message"]

    # Verify we can update content to duplicate active content
    r3 = await client.post(
        "/api/v1/memories",
        json={
            "conversation_id": conv_id,
            "content": "User hates Java.",
            "memory_type": "Preference",
            "importance": 0.5,
            "confidence": 0.5
        }
    )
    assert r3.status_code == 201
    m3_id = r3.json()["id"]

    r4 = await client.put(
        f"/api/v1/memories/{m3_id}",
        json={"content": "User loves Python coding."}
    )
    assert r4.status_code == 409


async def test_authorization_boundaries(client: AsyncClient):
    """Test user isolation: User B cannot access/modify User A's memories/conversations."""
    # 1. Register & Authenticate User A
    await client.post(
        "/api/v1/auth/register",
        json={"email": "usera@example.com", "password": "password123"}
    )
    login_a = await client.post(
        "/api/v1/auth/login",
        json={"email": "usera@example.com", "password": "password123"}
    )
    
    # 2. Create User A conversation and memory
    conv_a = await client.post("/api/v1/conversations", json={"title": "User A Chat"})
    conv_a_id = conv_a.json()["id"]
    mem_a = await client.post(
        "/api/v1/memories",
        json={
            "conversation_id": conv_a_id,
            "content": "User A secret info",
            "memory_type": "Fact",
            "importance": 0.5,
            "confidence": 0.5
        }
    )
    mem_a_id = mem_a.json()["id"]

    # 3. Register & Authenticate User B
    await client.post(
        "/api/v1/auth/register",
        json={"email": "userb@example.com", "password": "password123"}
    )
    # Log in as User B
    login_b = await client.post(
        "/api/v1/auth/login",
        json={"email": "userb@example.com", "password": "password123"}
    )
    assert login_b.status_code == 200

    # 4. User B tries to read User A's memory -> 403 Forbidden
    r_get = await client.get(f"/api/v1/memories/{mem_a_id}")
    assert r_get.status_code == 403

    # 5. User B tries to update User A's memory -> 403 Forbidden
    r_put = await client.put(f"/api/v1/memories/{mem_a_id}", json={"content": "hack"})
    assert r_put.status_code == 403

    # 6. User B tries to delete User A's memory -> 403 Forbidden
    r_del = await client.delete(f"/api/v1/memories/{mem_a_id}")
    assert r_del.status_code == 403

    # 7. User B tries to add a memory linked to User A's conversation -> 403 Forbidden
    r_add = await client.post(
        "/api/v1/memories",
        json={
            "conversation_id": conv_a_id,
            "content": "linked to A",
            "memory_type": "Fact",
            "importance": 0.5,
            "confidence": 0.5
        }
    )
    assert r_add.status_code == 403

    # 8. User B tries to view memories of User A's conversation -> 403 Forbidden
    r_list = await client.get(f"/api/v1/conversations/{conv_a_id}/memories")
    assert r_list.status_code == 403


async def test_sorting_and_pagination(client: AsyncClient):
    """Test that list endpoints support sorting and pagination queries correctly."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "sortpage@example.com", "password": "password123"}
    )

    # Create 3 memories with varying importance
    importances = [0.2, 0.9, 0.6]
    for idx, imp in enumerate(importances):
        await client.post(
            "/api/v1/memories",
            json={
                "content": f"Memory importance {idx}",
                "memory_type": "Fact",
                "importance": imp,
                "confidence": 0.8
            }
        )

    # 1. Fetch listing sorted by importance desc
    resp_desc = await client.get("/api/v1/memories?sort_by=importance&sort_order=desc")
    assert resp_desc.status_code == 200
    items_desc = resp_desc.json()
    assert len(items_desc) >= 3
    # Check that sorting order matches 0.9 -> 0.6 -> 0.2
    imps = [m["importance"] for m in items_desc[:3]]
    assert imps == [0.9, 0.6, 0.2]

    # 2. Fetch listing sorted by importance asc
    resp_asc = await client.get("/api/v1/memories?sort_by=importance&sort_order=asc")
    assert resp_asc.status_code == 200
    items_asc = resp_asc.json()
    imps_asc = [m["importance"] for m in items_asc[:3]]
    assert imps_asc == [0.2, 0.6, 0.9]

    # 3. Test pagination: page=1, limit=2
    paginated_resp = await client.get("/api/v1/memories?sort_by=importance&sort_order=desc&page=1&limit=2")
    assert paginated_resp.status_code == 200
    p_items = paginated_resp.json()
    assert len(p_items) == 2
    assert p_items[0]["importance"] == 0.9
    assert p_items[1]["importance"] == 0.6

    # page=2, limit=2
    paginated_resp_2 = await client.get("/api/v1/memories?sort_by=importance&sort_order=desc&page=2&limit=2")
    p_items_2 = paginated_resp_2.json()
    assert len(p_items_2) >= 1
    assert p_items_2[0]["importance"] == 0.2
