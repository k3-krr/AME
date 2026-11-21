import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, status, Response, Request, Depends, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.sql_repos import (
    SQLUserRepository,
    SQLSessionRepository,
    SQLAgentRepository,
    SQLAgentCredentialRepository,
)
from app.application.auth_service import AuthService
from app.application.agent_service import AgentService
from app.domain.entities import AccessContext, PrincipalType, Agent
from app.infrastructure.db.models import UserTable
from app.presentation.api.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    StandardErrorResponse,
)

logger = logging.getLogger("ame_backend.api.auth")

router = APIRouter(prefix="/auth", tags=["auth"])


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> UserTable:
    """
    FastAPI dependency that extracts the session cookie, verifies it against 
    the active sessions in the database, and returns the authenticated user.
    """
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    user_repo = SQLUserRepository(db)
    session_repo = SQLSessionRepository(db)
    auth_service = AuthService(user_repo, session_repo)

    user = await auth_service.get_user_from_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )

    return user


async def get_access_context(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> AccessContext:
    """
    Unified dependency resolving the request principal.
    Checks headers for agent credentials first, falling back to the user session cookie.
    """
    raw_key = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        raw_key = auth_header[7:].strip()
    else:
        x_agent_key = request.headers.get("X-Agent-Credential")
        if x_agent_key:
            raw_key = x_agent_key.strip()

    # Reject ambiguous requests containing both user and agent credentials
    has_session = request.cookies.get("session") is not None
    if raw_key is not None and has_session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ambiguous authentication context: both agent credential and user session cookie are present"
        )

    # 1. Process Agent key if present
    if raw_key:
        if raw_key.startswith("ame_agent_"):
            agent_repo = SQLAgentRepository(db)
            credential_repo = SQLAgentCredentialRepository(db)
            agent_service = AgentService(agent_repo, credential_repo)
            try:
                agent = await agent_service.authenticate_agent_by_key(raw_key)
                return AccessContext(
                    tenant_id=agent.tenant_id,
                    principal_type=PrincipalType.AGENT,
                    agent_id=agent.id,
                    user_id=None
                )
            except ValueError as e:
                logger.warning(f"Agent authentication failed: {e}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or inactive agent credentials"
                )

    # 2. Fallback to session cookie for human users
    token = request.cookies.get("session")
    if token:
        user_repo = SQLUserRepository(db)
        session_repo = SQLSessionRepository(db)
        auth_service = AuthService(user_repo, session_repo)
        user = await auth_service.get_user_from_token(token)
        if user:
            return AccessContext(
                tenant_id=user.id,
                principal_type=PrincipalType.USER,
                agent_id=None,
                user_id=user.id
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated"
    )


async def get_current_agent(
    context: AccessContext = Depends(get_access_context),
    db: AsyncSession = Depends(get_db)
) -> Agent:
    """
    FastAPI dependency requiring agent-principal context.
    Returns HTTP 403 if accessed via human user context.
    """
    if context.principal_type != PrincipalType.AGENT or not context.agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent principal required"
        )

    agent_repo = SQLAgentRepository(db)
    agent = await agent_repo.get_by_id(context.agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    return agent



@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "User successfully registered"},
        400: {"model": StandardErrorResponse, "description": "Invalid registration credentials or email exists"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def register(
    payload: UserRegisterRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Registers a new user, automatically creates an active session,
    and sets a secure HttpOnly session cookie.
    """
    user_repo = SQLUserRepository(db)
    session_repo = SQLSessionRepository(db)
    auth_service = AuthService(user_repo, session_repo)

    try:
        # 1. Create the user
        user = await auth_service.register_user(email=payload.email, password=payload.password)
        
        # 2. Automatically log the user in to create a session
        _, token = await auth_service.login_user(
            email=payload.email,
            password=payload.password
        )

        # 3. Set the secure HttpOnly cookie
        is_test = request.headers.get("host") == "testserver"
        response.set_cookie(
            key="session",
            value=token,
            httponly=True,
            max_age=settings.ACCESSO_TOKEN_EXPIRE_MINUTES * 60,
            expires=settings.ACCESSO_TOKEN_EXPIRE_MINUTES * 60,
            samesite="lax" if is_test else "none",
            secure=False if is_test else True,
        )

        return UserResponse(
            id=user.id,
            email=user.email,
            created_at=user.created_at
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error during registration: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register user."
        )


@router.post(
    "/login",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "User successfully logged in"},
        401: {"model": StandardErrorResponse, "description": "Invalid email or password"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def login(
    payload: UserLoginRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticates an existing user, creates an auth session,
    and sets a secure HttpOnly session cookie.
    """
    user_repo = SQLUserRepository(db)
    session_repo = SQLSessionRepository(db)
    auth_service = AuthService(user_repo, session_repo)

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        user, token = await auth_service.login_user(
            email=payload.email,
            password=payload.password,
            ip_address=ip_address,
            user_agent=user_agent
        )

        is_test = request.headers.get("host") == "testserver"
        response.set_cookie(
            key="session",
            value=token,
            httponly=True,
            max_age=settings.ACCESSO_TOKEN_EXPIRE_MINUTES * 60,
            expires=settings.ACCESSO_TOKEN_EXPIRE_MINUTES * 60,
            samesite="lax" if is_test else "none",
            secure=False if is_test else True,
        )

        return UserResponse(
            id=user.id,
            email=user.email,
            created_at=user.created_at
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error during login: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to log in."
        )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "User successfully logged out and session deleted"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def logout(
    request: Request,
    response: Response,
    current_user: UserTable = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Invalidates the active session token in the database and clears the user's browser cookie.
    """
    token = request.cookies.get("session")

    user_repo = SQLUserRepository(db)
    session_repo = SQLSessionRepository(db)
    auth_service = AuthService(user_repo, session_repo)

    try:
        await auth_service.logout_user(token)
        await db.commit()
    except Exception as e:
        logger.error(f"Error during logout: {e}", exc_info=True)
        # We proceed to clear the cookie even if database deletion fails to clean up client state
    
    is_test = request.headers.get("host") == "testserver"
    response.delete_cookie(
        key="session",
        path="/",
        samesite="lax" if is_test else "none",
        secure=False if is_test else True,
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
