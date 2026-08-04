import uuid
import logging
from typing import List, Optional, Any

from fastapi import APIRouter, status, Query, Depends, HTTPException

from app.config import settings

from app.presentation.api.auth import get_current_user
from app.infrastructure.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.db.models import UserTable
from app.infrastructure.repositories.sql_repos import SQLMemoryRepository

from app.knowledge_graph.domain.entities import RelationshipType, NodeType, EntityType
from app.knowledge_graph.schemas.schemas import (
    EntityResponse,
    RelationshipResponse,
    TraversalResponse,
    PathResponse,
    NeighborResponse,
)
from app.presentation.api.schemas import MemoryResponse, StandardErrorResponse
from app.knowledge_graph.services.graph_traversal_service import GraphTraversalService
from app.knowledge_graph.dependencies.graph_deps import get_graph_traversal_service

logger = logging.getLogger("ame_backend.api.kg_traversal")

router = APIRouter(tags=["traversal"])


def parse_enum_list(param: Optional[str], enum_cls: Any) -> Optional[List[Any]]:
    if not param:
        return None
    res = []
    for s in param.split(","):
        s_clean = s.strip()
        # Handle lowercase/uppercase matching
        s_upper = s_clean.upper()
        if s_clean:
            try:
                res.append(enum_cls(s_upper))
            except ValueError:
                # Provide a descriptive message
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid query parameter value: '{s_clean}'. Expected one of {[e.value for e in enum_cls]}."
                )
    return res if res else None


@router.get(
    "/graph/nodes/{node_id}/neighbors",
    response_model=List[NeighborResponse],
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Retrieved list of neighbors for the specified node"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        404: {"model": StandardErrorResponse, "description": "Node not found"},
        422: {"model": StandardErrorResponse, "description": "Validation error"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def get_neighbors(
    node_id: uuid.UUID,
    direction: str = Query("both", description="Direction filter: outgoing, incoming, both"),
    relationship_types: Optional[str] = Query(None, description="Comma-separated relationship types"),
    node_types: Optional[str] = Query(None, description="Comma-separated node types"),
    entity_types: Optional[str] = Query(None, description="Comma-separated entity types"),
    confidence_threshold: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum edge confidence"),
    current_user: UserTable = Depends(get_current_user),
    traversal_service: GraphTraversalService = Depends(get_graph_traversal_service),
):
    """
    Exposes direct neighbors of a specified node, returning their entities and connecting relationships.
    """
    try:
        rel_types = parse_enum_list(relationship_types, RelationshipType)
        n_types = parse_enum_list(node_types, NodeType)
        e_types = parse_enum_list(entity_types, EntityType)

        if direction not in ("incoming", "outgoing", "both"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Direction query parameter must be 'incoming', 'outgoing', or 'both'."
            )

        neighbors = await traversal_service.get_neighbors(
            user_id=current_user.id,
            node_id=node_id,
            direction=direction,
            relationship_types=rel_types,
            node_types=n_types,
            entity_types=e_types,
            confidence_threshold=confidence_threshold,
        )

        response = []
        for src, rel, tgt in neighbors:
            # The neighbor node is the opposite side of node_id
            neighbor_node = tgt if src.id == node_id else src
            edge_dir = "outgoing" if src.id == node_id else "incoming"
            response.append(NeighborResponse(
                node=EntityResponse.from_orm(neighbor_node),
                relationship=RelationshipResponse.from_orm(rel),
                direction=edge_dir
            ))
        return response

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Failed to retrieve neighbors: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch neighbors.")


@router.get(
    "/graph/nodes/{node_id}/connected",
    response_model=List[MemoryResponse],
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Retrieved list of memories connected to the specified node"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        404: {"model": StandardErrorResponse, "description": "Node not found"},
        422: {"model": StandardErrorResponse, "description": "Validation error"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def get_connected_memories(
    node_id: uuid.UUID,
    max_depth: int = Query(0, ge=0, description="Max depth traversal to collect memories"),
    direction: str = Query("both", description="Direction filter: outgoing, incoming, both"),
    relationship_types: Optional[str] = Query(None, description="Comma-separated relationship types"),
    node_types: Optional[str] = Query(None, description="Comma-separated node types"),
    entity_types: Optional[str] = Query(None, description="Comma-separated entity types"),
    confidence_threshold: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum edge confidence"),
    current_user: UserTable = Depends(get_current_user),
    traversal_service: GraphTraversalService = Depends(get_graph_traversal_service),
    db: AsyncSession = Depends(get_db),
):
    """
    Exposes memories mapped to a node. Optionally traverses the node's neighbors up to max_depth.
    """
    try:
        limit_depth = settings.GRAPH_MAX_TRAVERSAL_DEPTH
        if max_depth > limit_depth:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Traversal depth cannot exceed the configured limit of {limit_depth}."
            )

        rel_types = parse_enum_list(relationship_types, RelationshipType)
        n_types = parse_enum_list(node_types, NodeType)
        e_types = parse_enum_list(entity_types, EntityType)

        memory_repo = SQLMemoryRepository(db)

        memories = await traversal_service.get_connected_memories(
            user_id=current_user.id,
            node_id=node_id,
            max_depth=max_depth,
            direction=direction,
            relationship_types=rel_types,
            node_types=n_types,
            entity_types=e_types,
            confidence_threshold=confidence_threshold,
            memory_repo=memory_repo,
        )

        return [MemoryResponse.from_orm(m) for m in memories]

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Failed to retrieve connected memories: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch connected memories.")


@router.get(
    "/graph/path",
    response_model=PathResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Retrieved shortest path between specified nodes"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        404: {"model": StandardErrorResponse, "description": "Source or target node not found, or path doesn't exist"},
        422: {"model": StandardErrorResponse, "description": "Validation error"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def find_shortest_path(
    source_node_id: uuid.UUID = Query(..., description="UUID of starting source node"),
    target_node_id: uuid.UUID = Query(..., description="UUID of ending target node"),
    direction: str = Query("both", description="Direction filter: outgoing, incoming, both"),
    relationship_types: Optional[str] = Query(None, description="Comma-separated relationship types"),
    node_types: Optional[str] = Query(None, description="Comma-separated node types"),
    entity_types: Optional[str] = Query(None, description="Comma-separated entity types"),
    confidence_threshold: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum edge confidence"),
    current_user: UserTable = Depends(get_current_user),
    traversal_service: GraphTraversalService = Depends(get_graph_traversal_service),
):
    """
    Exposes shortest path link chain connecting two nodes. Uses Dijkstra internally.
    """
    try:
        rel_types = parse_enum_list(relationship_types, RelationshipType)
        n_types = parse_enum_list(node_types, NodeType)
        e_types = parse_enum_list(entity_types, EntityType)

        path_result = await traversal_service.find_shortest_path(
            user_id=current_user.id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            direction=direction,
            relationship_types=rel_types,
            node_types=n_types,
            entity_types=e_types,
            confidence_threshold=confidence_threshold,
        )

        if not path_result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Path not found between source {source_node_id} and target {target_node_id}."
            )

        return PathResponse(
            nodes=[EntityResponse.from_orm(n) for n in path_result["nodes"]],
            relationships=[RelationshipResponse.from_orm(r) for r in path_result["relationships"]],
            hop_count=path_result["hop_count"],
            metadata=path_result["metadata"],
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Failed to find shortest path: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to compute shortest path.")


@router.get(
    "/graph/traverse",
    response_model=TraversalResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Graph successfully traversed from start node"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        404: {"model": StandardErrorResponse, "description": "Starting node not found"},
        422: {"model": StandardErrorResponse, "description": "Validation error"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def traverse_graph(
    start_node_id: uuid.UUID = Query(..., description="UUID of starting traversal node"),
    max_depth: int = Query(3, ge=0, description="Max depth traversal limits"),
    direction: str = Query("both", description="Direction filter: outgoing, incoming, both"),
    relationship_types: Optional[str] = Query(None, description="Comma-separated relationship types"),
    node_types: Optional[str] = Query(None, description="Comma-separated node types"),
    entity_types: Optional[str] = Query(None, description="Comma-separated entity types"),
    confidence_threshold: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum edge confidence"),
    current_user: UserTable = Depends(get_current_user),
    traversal_service: GraphTraversalService = Depends(get_graph_traversal_service),
):
    """
    Exposes semantic graph traversal starting from a node. Uses BFS internally.
    """
    try:
        limit_depth = settings.GRAPH_MAX_TRAVERSAL_DEPTH
        if max_depth > limit_depth:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Traversal depth cannot exceed the configured limit of {limit_depth}."
            )

        rel_types = parse_enum_list(relationship_types, RelationshipType)
        n_types = parse_enum_list(node_types, NodeType)
        e_types = parse_enum_list(entity_types, EntityType)

        traversal_result = await traversal_service.traverse(
            user_id=current_user.id,
            start_node_id=start_node_id,
            max_depth=max_depth,
            direction=direction,
            relationship_types=rel_types,
            node_types=n_types,
            entity_types=e_types,
            confidence_threshold=confidence_threshold,
        )

        return TraversalResponse(
            nodes=[
                {"node": EntityResponse.from_orm(item["node"]), "depth": item["depth"]}
                for item in traversal_result["nodes"]
            ],
            metadata=traversal_result["metadata"],
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Failed to traverse graph: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to run graph traversal.")
