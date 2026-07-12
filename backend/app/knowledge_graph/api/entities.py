import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, status, Query, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession


from app.presentation.api.auth import get_current_user
from app.infrastructure.db.session import get_db
from app.infrastructure.db.models import UserTable

from app.knowledge_graph.domain.entities import EntityType
from app.knowledge_graph.schemas.schemas import (
    EntityCreateRequest,
    EntityUpdateRequest,
    EntityResponse,
)
from app.knowledge_graph.services.entity_service import EntityService
from app.knowledge_graph.dependencies.graph_deps import get_entity_service, get_entity_extraction_service
from app.knowledge_graph.services.entity_extraction_service import EntityExtractionService
from app.infrastructure.repositories.sql_repos import SQLMemoryRepository
from app.knowledge_graph.exceptions import EntityNotFoundError, DuplicateEntityError
from app.presentation.api.schemas import StandardErrorResponse


logger = logging.getLogger("ame_backend.api.kg_entities")

router = APIRouter(tags=["entities"])


@router.post(
    "/entities",
    response_model=EntityResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Entity successfully created"},
        400: {"model": StandardErrorResponse, "description": "Bad Request"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        409: {"model": StandardErrorResponse, "description": "Duplicate entity conflict"},
        422: {"model": StandardErrorResponse, "description": "Validation error"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def create_entity(
    payload: EntityCreateRequest,
    current_user: UserTable = Depends(get_current_user),
    entity_service: EntityService = Depends(get_entity_service),
):
    """Creates a new entity node for the authenticated user."""
    try:
        entity = await entity_service.create_entity(
            user_id=current_user.id,
            name=payload.name,
            entity_type=payload.entity_type,
            metadata=payload.metadata,
        )
        return entity
    except DuplicateEntityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating entity: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create entity."
        )


@router.get(
    "/entities",
    response_model=List[EntityResponse],
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Retrieved list of entities for the authenticated user"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def list_entities(
    entity_type: Optional[EntityType] = Query(None, description="Filter entities by type"),
    canonical_name: Optional[str] = Query(None, description="Filter entities by canonical name"),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Number of items to return per page"),
    sort_by: str = Query("created_at", description="Field to sort by (created_at, name)"),
    sort_order: str = Query("desc", description="Sorting direction (asc, desc)"),
    current_user: UserTable = Depends(get_current_user),
    entity_service: EntityService = Depends(get_entity_service),
):
    """Retrieves a paginated list of entity nodes belonging to the authenticated user."""
    try:
        entities = await entity_service.list_entities(
            user_id=current_user.id,
            entity_type=entity_type,
            canonical_name=canonical_name,
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return entities
    except Exception as e:
        logger.error(f"Error listing entities: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve entities."
        )


@router.get(
    "/entities/{entity_id}",
    response_model=EntityResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Retrieved entity details successfully"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        404: {"model": StandardErrorResponse, "description": "Entity not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def get_entity(
    entity_id: uuid.UUID,
    current_user: UserTable = Depends(get_current_user),
    entity_service: EntityService = Depends(get_entity_service),
):
    """Fetches details of a specific entity node."""
    try:
        entity = await entity_service.get_entity(
            user_id=current_user.id,
            entity_id=entity_id
        )
        return entity
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error retrieving entity details: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve entity details."
        )


@router.put(
    "/entities/{entity_id}",
    response_model=EntityResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Entity updated successfully"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        404: {"model": StandardErrorResponse, "description": "Entity not found"},
        409: {"model": StandardErrorResponse, "description": "Updated name duplicate conflict"},
        422: {"model": StandardErrorResponse, "description": "Validation error"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def update_entity(
    entity_id: uuid.UUID,
    payload: EntityUpdateRequest,
    current_user: UserTable = Depends(get_current_user),
    entity_service: EntityService = Depends(get_entity_service),
):
    """Updates fields of an existing entity node."""
    try:
        entity = await entity_service.update_entity(
            user_id=current_user.id,
            entity_id=entity_id,
            name=payload.name,
            entity_type=payload.entity_type,
            metadata=payload.metadata,
        )
        return entity
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except DuplicateEntityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating entity: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update entity."
        )


@router.delete(
    "/entities/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Entity successfully deleted"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        404: {"model": StandardErrorResponse, "description": "Entity not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def delete_entity(
    entity_id: uuid.UUID,
    current_user: UserTable = Depends(get_current_user),
    entity_service: EntityService = Depends(get_entity_service),
):
    """Hard-deletes an entity node and its associated relationships recursively."""
    try:
        await entity_service.delete_entity(
            user_id=current_user.id,
            entity_id=entity_id
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error deleting entity: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete entity."
        )


@router.post(
    "/memories/{memory_id}/entities/extract",
    response_model=List[EntityResponse],
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Entity extraction from memory executed successfully"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        403: {"model": StandardErrorResponse, "description": "Forbidden memory ownership check"},
        404: {"model": StandardErrorResponse, "description": "Memory not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def manual_extract_entities_from_memory(
    memory_id: uuid.UUID,
    current_user: UserTable = Depends(get_current_user),
    entity_extraction_service: EntityExtractionService = Depends(get_entity_extraction_service),
    db: AsyncSession = Depends(get_db),
):
    """
    Manually triggers entity extraction on a specific memory record.
    """
    try:
        memory_repo = SQLMemoryRepository(db)
        memory = await memory_repo.get_by_id(memory_id)
        if not memory:
            raise KeyError(f"Memory with ID {memory_id} not found.")
        if memory.user_id != current_user.id:
            raise PermissionError("Access forbidden: User does not own the memory")

        node_ids = await entity_extraction_service.extract_and_map_entities(
            user_id=current_user.id,
            memory_id=memory_id,
            content=memory.content
        )

        # Retrieve resolved entities
        entity_service = get_entity_service(db)
        resolved_entities = []
        for nid in node_ids:
            ent = await entity_service.get_entity(current_user.id, nid)
            resolved_entities.append(ent)
            
        return resolved_entities

    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(f"Manual entity extraction failed: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to run entity extraction.")

