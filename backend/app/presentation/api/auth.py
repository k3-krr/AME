import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, status, Response, Request, Depends, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.sql_repos import SQLUserRepository, SQLSessionRepository
from app.application.auth_service import AuthService
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
        response.set_cookie(
            key="session",
            value=token,
            httponly=True,
            max_age=settings.ACCESSO_TOKEN_EXPIRE_MINUTES * 60,
            expires=settings.ACCESSO_TOKEN_EXPIRE_MINUTES * 60,
            samesite="lax",
            secure=settings.ENV == "production",
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

        response.set_cookie(
            key="session",
            value=token,
            httponly=True,
            max_age=settings.ACCESSO_TOKEN_EXPIRE_MINUTES * 60,
            expires=settings.ACCESSO_TOKEN_EXPIRE_MINUTES * 60,
            samesite="lax",
            secure=settings.ENV == "production",
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
    
    response.delete_cookie(
        key="session",
        path="/",
        samesite="lax",
        secure=settings.ENV == "production",
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
