import pytest
import uuid
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_unauthorized_access(client: AsyncClient):
    """Test that chat endpoints return 401 when not authenticated."""
    response = await client.get("/api/v1/conversations")
    assert response.status_code == 401
    assert response.json()["error_code"] == "UNAUTHORIZED"


async def test_conversation_crud(client: AsyncClient):
    """Test creating, listing, and deleting conversations."""
    # 1. Log in / Authenticate
    await client.post(
        "/api/v1/auth/register",
        json={"email": "chatcrud@example.com", "password": "password123"}
    )
    
    # 2. Create conversation
    create_response = await client.post(
        "/api/v1/conversations",
        json={"title": "Test Chat", "system_prompt": "Test System Prompt"}
    )
    assert create_response.status_code == 201
    conv_data = create_response.json()
    assert conv_data["title"] == "Test Chat"
    assert conv_data["system_prompt"] == "Test System Prompt"
    conv_id = conv_data["id"]

    # 3. List conversations
    list_response = await client.get("/api/v1/conversations")
    assert list_response.status_code == 200
    conv_list = list_response.json()
    assert len(conv_list) >= 1
    assert any(c["id"] == conv_id for c in conv_list)

    # 4. Delete conversation
    delete_response = await client.delete(f"/api/v1/conversations/{conv_id}")
    assert delete_response.status_code == 204

    # 5. List conversations again (should be empty/removed)
    list_response_2 = await client.get("/api/v1/conversations")
    conv_list_2 = list_response_2.json()
    assert not any(c["id"] == conv_id for c in conv_list_2)


async def test_post_message_and_stream(client: AsyncClient):
    """Test posting a user message and parsing the SSE assistant response stream."""
    # 1. Register & Authenticate
    await client.post(
        "/api/v1/auth/register",
        json={"email": "streamtest@example.com", "password": "password123"}
    )
    
    # 2. Create conversation
    create_response = await client.post(
        "/api/v1/conversations",
        json={"title": "Streaming Chat"}
    )
    conv_id = create_response.json()["id"]

    # 3. List messages (should be empty initially)
    initial_messages = await client.get(f"/api/v1/conversations/{conv_id}/messages")
    assert initial_messages.status_code == 200
    assert len(initial_messages.json()) == 0

    # 4. Post message & stream response
    # We use client.stream POST to read chunks
    accumulated_content = ""
    assistant_msg_id = None
    
    # Note: HTTPX async client allows stream requests
    async with client.stream(
        "POST",
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "What is memory?"}
    ) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        
        # Read the stream lines
        async for line in response.aiter_lines():
            line = line.rstrip("\r\n")
            if not line:
                continue
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                data_val = line[6:] if line.startswith("data: ") else line[5:]
                if event_type == "message_id":
                    assistant_msg_id = data_val
                elif event_type == "delta":
                    accumulated_content += data_val
                elif event_type == "done":
                    assert data_val == "[DONE]"

    # Verify we got assistant message ID and content
    assert assistant_msg_id is not None
    assert len(accumulated_content) > 0

    # 5. Get message history from database
    history_response = await client.get(f"/api/v1/conversations/{conv_id}/messages")
    assert history_response.status_code == 200
    history = history_response.json()
    
    # We expect 2 messages: user query and assistant reply
    assert len(history) == 2
    history.sort(key=lambda m: (m["created_at"], m["sender_role"] == "assistant"))
    assert history[0]["sender_role"] == "user"
    assert history[0]["content"] == "What is memory?"
    assert history[1]["sender_role"] == "assistant"
    assert history[1]["id"] == assistant_msg_id
    assert history[1]["content"] == accumulated_content



async def test_cursor_pagination(client: AsyncClient):
    """Test cursor-based pagination works correctly using before_id."""
    # 1. Register & Authenticate
    await client.post(
        "/api/v1/auth/register",
        json={"email": "pagetest@example.com", "password": "password123"}
    )
    
    # 2. Create conversation
    create_response = await client.post("/api/v1/conversations", json={"title": "Page Chat"})
    conv_id = create_response.json()["id"]

    # 3. Post multiple messages (yielding user & assistant pairs in DB)
    # Post first message
    async with client.stream(
        "POST", f"/api/v1/conversations/{conv_id}/messages", json={"content": "Msg 1"}
    ) as r:
        await r.aread()

    # Post second message
    async with client.stream(
        "POST", f"/api/v1/conversations/{conv_id}/messages", json={"content": "Msg 2"}
    ) as r:
        await r.aread()

    # 4. Get message history (should be 4 messages total: 2 user + 2 assistant)
    full_history_resp = await client.get(f"/api/v1/conversations/{conv_id}/messages")
    full_history = full_history_resp.json()
    assert len(full_history) == 4
    full_history.sort(key=lambda m: (m["created_at"], m["sender_role"] == "assistant"))
    
    # Messages are chronological: full_history[0] is User Msg 1, full_history[2] is User Msg 2
    msg_1_user_id = full_history[0]["id"]
    msg_2_user_id = full_history[2]["id"]

    # 5. Fetch with limit and cursor: fetch messages before User Msg 2 (should return Msg 1 User and Assistant)
    paginated_resp = await client.get(
        f"/api/v1/conversations/{conv_id}/messages?limit=2&before_id={msg_2_user_id}"
    )
    paginated = paginated_resp.json()
    
    assert len(paginated) == 2
    paginated.sort(key=lambda m: (m["created_at"], m["sender_role"] == "assistant"))
    assert paginated[0]["id"] == msg_1_user_id
    assert paginated[0]["content"] == "Msg 1"
    assert paginated[1]["sender_role"] == "assistant"

