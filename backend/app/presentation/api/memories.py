import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, status, Query, Response, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_db
from app.presentation.api.auth import get_current_user
from app.infrastructure.db.models import UserTable
from app.infrastructure.repositories.sql_repos import (
    SQLMemoryRepository,
    SQLConversationRepository,
)
from app.application.memory_service import MemoryService
from app.domain.entities import MemoryType, MemoryStatus
from app.presentation.api.schemas import (
    MemoryCreateRequest,
    MemoryUpdateRequest,
    MemoryResponse,
    StandardErrorResponse,
)

logger = logging.getLogger("ame_backend.api.memories")

router = APIRouter(tags=["memories"])


def get_memory_service(db: AsyncSession = Depends(get_db)) -> MemoryService:
    """Dependency helper instantiating MemoryService with standard database repositories."""
    memory_repo = SQLMemoryRepository(db)
    conversation_repo = SQLConversationRepository(db)
    return MemoryService(
        memory_repo=memory_repo,
        conversation_repo=conversation_repo,
    )


@router.post(
    "/memories",
    response_model=MemoryResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Memory successfully created"},
        400: {"model": StandardErrorResponse, "description": "Bad Request"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        403: {"model": StandardErrorResponse, "description": "Forbidden conversation ownership validation"},
        404: {"model": StandardErrorResponse, "description": "Conversation not found"},
        409: {"model": StandardErrorResponse, "description": "Duplicate active memory conflict"},
        422: {"model": StandardErrorResponse, "description": "Validation error"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def create_memory(
    payload: MemoryCreateRequest,
    current_user: UserTable = Depends(get_current_user),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Creates a new long-term memory. If linked to a conversation, validates conversation ownership and checks for duplicate active content.
    """
    try:
        memory = await memory_service.create_memory(
            user_id=current_user.id,
            conversation_id=payload.conversation_id,
            content=payload.content,
            memory_type=payload.memory_type,
            importance=payload.importance,
            confidence=payload.confidence,
            metadata=payload.metadata,
        )
        return memory
    except ValueError as e:
        err_msg = str(e)
        if "already exists" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=err_msg
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=err_msg
        )
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating memory: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create memory."
        )


@router.get(
    "/memories",
    response_model=List[MemoryResponse],
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Retrieved list of memories for the authenticated user"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def list_memories(
    memory_type: Optional[MemoryType] = Query(None, description="Filter memories by type"),
    status_filter: Optional[MemoryStatus] = Query(None, alias="status", description="Filter memories by status"),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Number of items to return per page"),
    sort_by: str = Query("created_at", description="Field to sort by (created_at, updated_at, importance, confidence)"),
    sort_order: str = Query("desc", description="Sorting direction (asc, desc)"),
    current_user: UserTable = Depends(get_current_user),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Retrieves a paginated, sorted list of memories belonging to the authenticated user.
    """
    if sort_by not in ("created_at", "updated_at", "importance", "confidence"):
        sort_by = "created_at"
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"

    try:
        memories = await memory_service.list_user_memories(
            user_id=current_user.id,
            memory_type=memory_type,
            status=status_filter,
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return memories
    except Exception as e:
        logger.error(f"Error listing memories: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve memories."
        )


@router.get(
    "/memories/{memory_id}",
    response_model=MemoryResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Retrieved memory successfully"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        403: {"model": StandardErrorResponse, "description": "Forbidden memory ownership validation"},
        404: {"model": StandardErrorResponse, "description": "Memory not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def get_memory(
    memory_id: uuid.UUID,
    current_user: UserTable = Depends(get_current_user),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Retrieves details of a specific memory record.
    """
    try:
        memory = await memory_service.get_memory(user_id=current_user.id, memory_id=memory_id)
        return memory
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error fetching memory details: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve memory details."
        )


@router.put(
    "/memories/{memory_id}",
    response_model=MemoryResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Memory updated successfully"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        403: {"model": StandardErrorResponse, "description": "Forbidden memory ownership validation"},
        404: {"model": StandardErrorResponse, "description": "Memory not found"},
        409: {"model": StandardErrorResponse, "description": "Duplicate active memory conflict"},
        422: {"model": StandardErrorResponse, "description": "Validation error"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def update_memory(
    memory_id: uuid.UUID,
    payload: MemoryUpdateRequest,
    current_user: UserTable = Depends(get_current_user),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Updates fields of an existing memory. Bumps version and validates changes.
    """
    try:
        memory = await memory_service.update_memory(
            user_id=current_user.id,
            memory_id=memory_id,
            content=payload.content,
            memory_type=payload.memory_type,
            importance=payload.importance,
            confidence=payload.confidence,
            status=payload.status,
            metadata=payload.metadata,
        )
        return memory
    except ValueError as e:
        err_msg = str(e)
        if "already exists" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=err_msg
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=err_msg
        )
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating memory: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update memory."
        )


@router.delete(
    "/memories/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Memory soft-deleted successfully"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        403: {"model": StandardErrorResponse, "description": "Forbidden memory ownership validation"},
        404: {"model": StandardErrorResponse, "description": "Memory not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def delete_memory(
    memory_id: uuid.UUID,
    current_user: UserTable = Depends(get_current_user),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Soft-deletes an existing memory by setting its status state to DELETED.
    """
    try:
        await memory_service.delete_memory(user_id=current_user.id, memory_id=memory_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error deleting memory: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete memory."
        )


@router.get(
    "/conversations/{conversation_id}/memories",
    response_model=List[MemoryResponse],
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Retrieved list of memories for the conversation"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        403: {"model": StandardErrorResponse, "description": "Forbidden conversation ownership validation"},
        404: {"model": StandardErrorResponse, "description": "Conversation not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def list_conversation_memories(
    conversation_id: uuid.UUID,
    memory_type: Optional[MemoryType] = Query(None, description="Filter memories by type"),
    status_filter: Optional[MemoryStatus] = Query(None, alias="status", description="Filter memories by status"),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Number of items to return per page"),
    sort_by: str = Query("created_at", description="Field to sort by (created_at, updated_at, importance, confidence)"),
    sort_order: str = Query("desc", description="Sorting direction (asc, desc)"),
    current_user: UserTable = Depends(get_current_user),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Retrieves a paginated, sorted list of memories linked to a specific conversation.
    """
    if sort_by not in ("created_at", "updated_at", "importance", "confidence"):
        sort_by = "created_at"
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"

    try:
        memories = await memory_service.list_conversation_memories(
            user_id=current_user.id,
            conversation_id=conversation_id,
            memory_type=memory_type,
            status=status_filter,
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return memories
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error fetching conversation memory logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve conversation memories."
        )
