import pytest
import uuid
import httpx
from pydantic import ValidationError
from app.config import settings, AppSettings
from app.infrastructure.db.models import AgentCredentialTable
from sqlalchemy import select
from app.domain.entities import AccessContext, PrincipalType

pytestmark = pytest.mark.asyncio


async def test_jwt_production_safety():
    """Verifies that the configuration rejects the default JWT secret in production mode."""
    # 1. Production with default key should fail validation
    with pytest.raises(ValidationError) as excinfo:
        AppSettings(ENV="production", JWT_SECRET_KEY="secret-tokens-change-on-production-environments-310aefb")
    assert "Production environment detected but default/insecure JWT_SECRET_KEY" in str(excinfo.value)

    # 2. Production with a custom key should pass validation
    config = AppSettings(ENV="production", JWT_SECRET_KEY="custom-secure-prod-key-12345")
    assert config.JWT_SECRET_KEY == "custom-secure-prod-key-12345"

    # 3. Development with default key should pass validation
    config_dev = AppSettings(ENV="development", JWT_SECRET_KEY="secret-tokens-change-on-production-environments-310aefb")
    assert config_dev.JWT_SECRET_KEY == "secret-tokens-change-on-production-environments-310aefb"


async def test_unhandled_exception_concealment(client):
    """Verifies that unhandled internal errors do not leak stack traces or trace details when DEBUG = False."""
    from app.main import app
    from app.presentation.api.auth import get_access_context
    from app.presentation.api.memories import get_memory_service

    orig_debug = settings.DEBUG
    orig_env = settings.ENV
    settings.DEBUG = False
    settings.ENV = "production"

    def override_get_access_context():
        return AccessContext(
            tenant_id=uuid.uuid4(),
            principal_type=PrincipalType.USER,
            user_id=uuid.uuid4()
        )

    def override_get_memory_service():
        raise RuntimeError("Sensitive DB path trace leak information")

    app.dependency_overrides[get_access_context] = override_get_access_context
    app.dependency_overrides[get_memory_service] = override_get_memory_service

    # Create a custom client with raise_app_exceptions=False so FastAPI global handler runs
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as test_client:
            response = await test_client.get("/api/v1/memories/00000000-0000-0000-0000-000000000000")
            assert response.status_code == 500
            data = response.json()
            assert data["error_code"] == "INTERNAL_SERVER_ERROR"
            assert "Sensitive DB path" not in str(data)
            assert data["details"] == {}
    finally:
        settings.DEBUG = orig_debug
        settings.ENV = orig_env
        app.dependency_overrides.clear()


async def test_cors_environment_loading():
    """Verifies that CORS middleware is registered and receives allowed origins dynamically from settings."""
    from app.main import app
    from fastapi.middleware.cors import CORSMiddleware

    cors_middleware = None
    for mw in app.user_middleware:
        if mw.cls == CORSMiddleware:
            cors_middleware = mw
            break

    assert cors_middleware is not None
    assert cors_middleware.kwargs["allow_origins"] == settings.CORS_ALLOWED_ORIGINS


async def test_api_key_hashing_secrecy(db_session):
    """Verifies that raw API keys are never stored, only their hashes exist in the database."""
    stmt = select(AgentCredentialTable)
    result = await db_session.execute(stmt)
    credentials = result.scalars().all()

    for cred in credentials:
        # Ensure raw key format is not stored
        assert not cred.credential_hash.startswith("ame_agent_")
        # Ensure it is stored as SHA-256 hash (64 hex characters)
        assert len(cred.credential_hash) == 64
