import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_register_success(client: AsyncClient):
    """Test user registration successfully sets a cookie and registers User."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "newuser@example.com", "password": "securepassword123"}
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["email"] == "newuser@example.com"
    assert "created_at" in data
    
    # Assert session cookie is set
    assert "session" in client.cookies
    assert client.cookies["session"] is not None


async def test_register_duplicate(client: AsyncClient):
    """Test registering a duplicate email returns 400."""
    # First registration
    await client.post(
        "/api/v1/auth/register",
        json={"email": "dup@example.com", "password": "securepassword123"}
    )
    
    # Clear cookies to simulate fresh signup attempt
    client.cookies.clear()
    
    # Duplicate registration
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "dup@example.com", "password": "securepassword123"}
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "BAD_REQUEST"


async def test_login_success(client: AsyncClient):
    """Test login with correct credentials."""
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={"email": "login@example.com", "password": "mypassword123"}
    )
    
    # Clear cookies so client is not auto-logged in
    client.cookies.clear()
    
    # Login
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "mypassword123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "login@example.com"
    assert "session" in client.cookies


async def test_login_fail(client: AsyncClient):
    """Test login with wrong password returns 401."""
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={"email": "wrongpass@example.com", "password": "correctpassword123"}
    )
    client.cookies.clear()
    
    # Try logging in with wrong password
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpass@example.com", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert response.json()["error_code"] == "UNAUTHORIZED"
    assert "session" not in client.cookies


async def test_logout_and_revocation(client: AsyncClient):
    """Test logout invalidates the session and blocks further access."""
    # Register and log in
    await client.post(
        "/api/v1/auth/register",
        json={"email": "logout@example.com", "password": "password123"}
    )
    assert "session" in client.cookies
    cookie_value = client.cookies["session"]

    # Logout
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 204
    
    # Check that cookie is removed from the client
    assert "session" not in client.cookies or not client.cookies["session"]
    
    # Attempt to access a protected endpoint (like logout itself) using the old cookie
    client.cookies["session"] = cookie_value
    retry_response = await client.post("/api/v1/auth/logout")
    assert retry_response.status_code == 401
