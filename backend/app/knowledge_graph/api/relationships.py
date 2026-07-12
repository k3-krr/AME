import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, status, Query, Depends, HTTPException, Response

from app.presentation.api.auth import get_current_user
from app.infrastructure.db.models import UserTable
from app.knowledge_graph.domain.entities import RelationshipType
from app.knowledge_graph.schemas.schemas import (
    RelationshipCreateRequest,
    RelationshipUpdateRequest,
    RelationshipResponse,
)
from app.knowledge_graph.services.relationship_service import RelationshipService
from app.knowledge_graph.dependencies.graph_deps import get_relationship_service
from app.knowledge_graph.exceptions import (
    RelationshipNotFoundError,
    EntityNotFoundError,
    DuplicateRelationshipError,
)
from app.presentation.api.schemas import StandardErrorResponse

logger = logging.getLogger("ame_backend.api.kg_relationships")

router = APIRouter(tags=["relationships"])


@router.post(
    "/relationships",
    response_model=RelationshipResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Relationship successfully created"},
        400: {"model": StandardErrorResponse, "description": "Bad Request"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        404: {"model": StandardErrorResponse, "description": "Source or target node not found"},
        409: {"model": StandardErrorResponse, "description": "Duplicate relationship conflict"},
        422: {"model": StandardErrorResponse, "description": "Validation error"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def create_relationship(
    payload: RelationshipCreateRequest,
    current_user: UserTable = Depends(get_current_user),
    relationship_service: RelationshipService = Depends(get_relationship_service),
):
    """Creates a directed relationship edge between two nodes."""
    try:
        relationship = await relationship_service.create_relationship(
            user_id=current_user.id,
            source_node_id=payload.source_entity_id,
            target_node_id=payload.target_entity_id,
            relationship_type=payload.relationship_type,
            confidence=payload.confidence,
            metadata=payload.metadata,
        )
        return relationship
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except DuplicateRelationshipError as e:
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
        logger.error(f"Error creating relationship: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create relationship."
        )


@router.get(
    "/relationships",
    response_model=List[RelationshipResponse],
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Retrieved list of relationships for the authenticated user"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def list_relationships(
    source_entity_id: Optional[uuid.UUID] = Query(None, description="Filter by source node ID"),
    target_entity_id: Optional[uuid.UUID] = Query(None, description="Filter by target node ID"),
    relationship_type: Optional[RelationshipType] = Query(None, description="Filter by edge predicate type"),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Number of items to return per page"),
    sort_by: str = Query("created_at", description="Field to sort by (created_at, confidence)"),
    sort_order: str = Query("desc", description="Sorting direction (asc, desc)"),
    current_user: UserTable = Depends(get_current_user),
    relationship_service: RelationshipService = Depends(get_relationship_service),
):
    """Retrieves a paginated list of relationship edges belonging to the authenticated user."""
    try:
        relationships = await relationship_service.list_relationships(
            user_id=current_user.id,
            source_node_id=source_entity_id,
            target_node_id=target_entity_id,
            relationship_type=relationship_type,
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return relationships
    except Exception as e:
        logger.error(f"Error listing relationships: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve relationships."
        )


@router.get(
    "/relationships/{relationship_id}",
    response_model=RelationshipResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Retrieved relationship details successfully"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        404: {"model": StandardErrorResponse, "description": "Relationship not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def get_relationship(
    relationship_id: uuid.UUID,
    current_user: UserTable = Depends(get_current_user),
    relationship_service: RelationshipService = Depends(get_relationship_service),
):
    """Fetches details of a specific relationship edge."""
    try:
        relationship = await relationship_service.get_relationship(
            user_id=current_user.id,
            relationship_id=relationship_id
        )
        return relationship
    except RelationshipNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error retrieving relationship details: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve relationship details."
        )


@router.put(
    "/relationships/{relationship_id}",
    response_model=RelationshipResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Relationship updated successfully"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        404: {"model": StandardErrorResponse, "description": "Relationship not found"},
        409: {"model": StandardErrorResponse, "description": "Duplicate connection conflict"},
        422: {"model": StandardErrorResponse, "description": "Validation error"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def update_relationship(
    relationship_id: uuid.UUID,
    payload: RelationshipUpdateRequest,
    current_user: UserTable = Depends(get_current_user),
    relationship_service: RelationshipService = Depends(get_relationship_service),
):
    """Updates fields of an existing relationship edge."""
    try:
        relationship = await relationship_service.update_relationship(
            user_id=current_user.id,
            relationship_id=relationship_id,
            relationship_type=payload.relationship_type,
            confidence=payload.confidence,
            metadata=payload.metadata,
        )
        return relationship
    except RelationshipNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except DuplicateRelationshipError as e:
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
        logger.error(f"Error updating relationship: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update relationship."
        )


@router.delete(
    "/relationships/{relationship_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Relationship successfully deleted"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        404: {"model": StandardErrorResponse, "description": "Relationship not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def delete_relationship(
    relationship_id: uuid.UUID,
    current_user: UserTable = Depends(get_current_user),
    relationship_service: RelationshipService = Depends(get_relationship_service),
):
    """Hard-deletes a specific relationship edge."""
    try:
        await relationship_service.delete_relationship(
            user_id=current_user.id,
            relationship_id=relationship_id
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except RelationshipNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error deleting relationship: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete relationship."
        )
