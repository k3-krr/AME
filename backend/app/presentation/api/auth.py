import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, status, Response, Request
from fastapi.responses import JSONResponse

from app.presentation.api.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    StandardErrorResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


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
async def register(payload: UserRegisterRequest, response: Response):
    """
    Registers a new user and sets a secure HttpOnly session cookie.
    
    This is currently a skeleton router. In Milestone 2, it will connect to
    the SQLUserRepository, hash the password, write to the database,
    generate a session token, write it to SQLSessionRepository, and set the HttpOnly cookie.
    """
    mock_user_id = uuid.uuid4()
    # Stub response matching UserResponse schema structure
    return UserResponse(
        id=mock_user_id,
        email=payload.email,
        created_at=datetime.now(timezone.utc)
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
async def login(payload: UserLoginRequest, response: Response):
    """
    Authenticates an existing user and sets a secure HttpOnly session cookie.
    
    This is currently a skeleton router. In Milestone 2, it will verify credentials,
    create an auth session in SQLSessionRepository, and set the cookie.
    """
    mock_user_id = uuid.uuid4()
    return UserResponse(
        id=mock_user_id,
        email=payload.email,
        created_at=datetime.now(timezone.utc)
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
async def logout(request: Request, response: Response):
    """
    Invalidates the active session token in the database and clears the user's browser cookie.
    
    This is currently a skeleton router. In Milestone 2, it will read the session cookie,
    delete it from SQLSessionRepository, and clear the cookie on the response.
    """
    return Response(status_code=status.HTTP_204_NO_CONTENT)
