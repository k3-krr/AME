import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, status, Query, Response, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_db
from app.presentation.api.auth import get_current_user, get_access_context
from app.infrastructure.db.models import UserTable
from app.infrastructure.repositories.sql_repos import (
    SQLMemoryRepository,
    SQLConversationRepository,
    SQLMemoryEmbeddingRepository,
    SQLMemoryStateRepository,
    SQLMemoryAccessLogRepository,
    SQLAgentRepository,
    SQLMemoryAccessGrantRepository,
)
from app.application.memory_service import MemoryService
from app.application.retrieval_service import RetrievalService
from app.application.ranking_service import RankingService
from app.application.analytics_service import AnalyticsService
from app.config import settings
from app.infrastructure.clients.embedding_client import OpenAIEmbeddingProvider
from app.domain.entities import MemoryType, MemoryStatus, AccessContext, MemoryAccessLevel, MemoryAccessGrant
from app.presentation.api.schemas import (
    MemoryCreateRequest,
    MemoryUpdateRequest,
    MemoryResponse,
    MemorySearchResponse,
    ReindexResponse,
    StandardErrorResponse,
    MemoryStateResponse,
    MemoryAnalyticsResponse,
    MemoryAccessLogResponse,
    DecayTriggerResponse,
    MemoryAccessGrantCreateRequest,
    MemoryAccessGrantResponse,
    MemoryAccessGrantRevokeResponse,
)

logger = logging.getLogger("ame_backend.api.memories")

router = APIRouter(tags=["memories"])


# Instantiate singleton embedding provider
embedding_provider_impl = OpenAIEmbeddingProvider()


def get_ranking_service() -> RankingService:
    """Dependency helper instantiating RankingService using app config settings."""
    return RankingService(
        w_semantic=settings.W_SEMANTIC,
        w_importance=settings.W_IMPORTANCE,
        w_recency=settings.W_RECENCY,
        w_frequency=settings.W_FREQUENCY,
        w_decay=settings.W_DECAY,
        w_confidence=settings.W_CONFIDENCE,
        recency_half_life_hours=settings.RECENCY_HALF_LIFE_HOURS,
        frequency_threshold=settings.FREQUENCY_THRESHOLD,
    )


def get_analytics_service(db: AsyncSession = Depends(get_db)) -> AnalyticsService:
    """Dependency helper instantiating AnalyticsService."""
    access_log_repo = SQLMemoryAccessLogRepository(db)
    memory_state_repo = SQLMemoryStateRepository(db)
    return AnalyticsService(
        access_log_repo=access_log_repo,
        memory_state_repo=memory_state_repo,
    )


from app.knowledge_graph.dependencies.graph_deps import get_hybrid_retrieval_service


def get_memory_service(
    db: AsyncSession = Depends(get_db),
    ranking_service: RankingService = Depends(get_ranking_service),
    hybrid_retrieval_service = Depends(get_hybrid_retrieval_service),
) -> MemoryService:
    """Dependency helper instantiating MemoryService with standard database repositories."""
    memory_repo = SQLMemoryRepository(db)
    conversation_repo = SQLConversationRepository(db)
    embedding_repo = SQLMemoryEmbeddingRepository(db)
    memory_state_repo = SQLMemoryStateRepository(db)
    agent_repo = SQLAgentRepository(db)
    grant_repo = SQLMemoryAccessGrantRepository(db)

    from app.domain.memory_router import MemoryRouter
    from app.infrastructure.repositories.sql_repos import SQLRepositoryFactory
    from app.application.hybrid_ranking_service import HybridRankingService

    memory_router = MemoryRouter()
    repository_factory = SQLRepositoryFactory(db)
    hybrid_ranking_service = HybridRankingService(ranking_service)

    from fastapi.params import Depends as DependsClass
    if isinstance(hybrid_retrieval_service, DependsClass) or hybrid_retrieval_service is None:
        from app.application.hybrid_retrieval_service import HybridRetrievalService
        try:
            from app.knowledge_graph.services.expansion_service import KnowledgeGraphExpansionService
            from app.knowledge_graph.repositories.sql_repositories import SQLGraphRepository
            from app.application.graph_aware_hybrid_retrieval_service import GraphAwareHybridRetrievalService
            
            base_ret = HybridRetrievalService(repository_factory)
            graph_repo = SQLGraphRepository(db)
            exp_service = KnowledgeGraphExpansionService(graph_repo)
            hybrid_retrieval_service = GraphAwareHybridRetrievalService(
                base_retrieval_service=base_ret,
                expansion_service=exp_service,
                memory_repo=memory_repo,
            )
        except Exception:
            hybrid_retrieval_service = HybridRetrievalService(repository_factory)

    return MemoryService(
        memory_repo=memory_repo,
        conversation_repo=conversation_repo,
        embedding_repo=embedding_repo,
        embedding_provider=embedding_provider_impl,
        memory_state_repo=memory_state_repo,
        memory_router=memory_router,
        repository_factory=repository_factory,
        hybrid_retrieval_service=hybrid_retrieval_service,
        hybrid_ranking_service=hybrid_ranking_service,
        agent_repo=agent_repo,
        grant_repo=grant_repo,
    )


def get_retrieval_service(
    db: AsyncSession = Depends(get_db),
    ranking_service: RankingService = Depends(get_ranking_service),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> RetrievalService:
    """Dependency helper instantiating RetrievalService for semantic query search."""
    memory_repo = SQLMemoryRepository(db)
    embedding_repo = SQLMemoryEmbeddingRepository(db)
    memory_state_repo = SQLMemoryStateRepository(db)
    return RetrievalService(
        memory_repo=memory_repo,
        embedding_repo=embedding_repo,
        embedding_provider=embedding_provider_impl,
        memory_state_repo=memory_state_repo,
        ranking_service=ranking_service,
        analytics_service=analytics_service,
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
    access_context: AccessContext = Depends(get_access_context),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Creates a new long-term memory. If linked to a conversation, validates conversation ownership and checks for duplicate active content.
    """
    try:
        memory = await memory_service.create_memory(
            user_id=access_context.tenant_id,
            conversation_id=payload.conversation_id,
            content=payload.content,
            memory_type=payload.memory_type,
            importance=payload.importance,
            confidence=payload.confidence,
            metadata=payload.metadata,
            memory_system=payload.memory_system,
            occurred_at=payload.occurred_at,
            expires_at=payload.expires_at,
            agent_id=access_context.agent_id,
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
    "/memories/search",
    response_model=List[MemorySearchResponse],
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Successfully retrieved similar memories"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def search_memories(
    query: str = Query(..., description="The semantic search query string"),
    top_k: int = Query(5, ge=1, le=100, description="Number of results to return"),
    memory_type: Optional[MemoryType] = Query(None, description="Filter results by memory type"),
    current_user: UserTable = Depends(get_current_user),
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
):
    """
    Semantic search endpoint to fetch user memories matching a text query.
    """
    try:
        results = await retrieval_service.retrieve_relevant_memories(
            user_id=current_user.id,
            query=query,
            top_k=top_k,
            memory_type=memory_type,
        )
        response_data = [
            MemorySearchResponse(memory=memory, similarity=score)
            for memory, score in results
        ]
        return response_data
    except Exception as e:
        logger.error(f"Error performing semantic memory search: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to perform semantic search."
        )


@router.post(
    "/memories/reindex",
    response_model=ReindexResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Successfully completed reindexing"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def reindex_memories(
    current_user: UserTable = Depends(get_current_user),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Triggers manual generation of missing vector embeddings for the user's active memories.
    """
    try:
        count = await memory_service.reindex_user_memories(user_id=current_user.id)
        return ReindexResponse(reindexed_count=count)
    except Exception as e:
        logger.error(f"Error during memory reindexing: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to run reindexing."
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
    access_context: AccessContext = Depends(get_access_context),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Retrieves details of a specific memory record.
    """
    try:
        memory = await memory_service.get_memory(
            user_id=access_context.tenant_id,
            memory_id=memory_id,
            access_context=access_context,
            required_level=MemoryAccessLevel.READ
        )
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
    access_context: AccessContext = Depends(get_access_context),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Updates fields of an existing memory. Bumps version and validates changes.
    """
    try:
        memory = await memory_service.update_memory(
            user_id=access_context.tenant_id,
            memory_id=memory_id,
            content=payload.content,
            memory_type=payload.memory_type,
            importance=payload.importance,
            confidence=payload.confidence,
            status=payload.status,
            metadata=payload.metadata,
            memory_system=payload.memory_system,
            occurred_at=payload.occurred_at,
            expires_at=payload.expires_at,
            access_context=access_context,
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
    access_context: AccessContext = Depends(get_access_context),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Soft-deletes an existing memory by setting its status state to DELETED.
    """
    try:
        await memory_service.delete_memory(user_id=access_context.tenant_id, memory_id=memory_id, access_context=access_context)
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


@router.post(
    "/memories/decay",
    response_model=DecayTriggerResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Successfully completed decay calculation cycle"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def trigger_decay(
    current_user: UserTable = Depends(get_current_user),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Manually triggers background decay calculations for active records.
    (Prod uses scheduled workers, endpoint exposes manual trigger capability).
    """
    try:
        updated_count = await memory_service.decay_active_memories(decay_rate=settings.DECAY_RATE)
        return DecayTriggerResponse(updated_count=updated_count)
    except Exception as e:
        logger.error(f"Error during memory decay calculation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to run decay cycle."
        )


@router.post(
    "/memories/{memory_id}/reinforce",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Memory successfully reinforced"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        403: {"model": StandardErrorResponse, "description": "Forbidden memory ownership validation"},
        404: {"model": StandardErrorResponse, "description": "Memory not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def manual_reinforce_memory(
    memory_id: uuid.UUID,
    access_context: AccessContext = Depends(get_access_context),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Diagnostic endpoint to manually trigger the reinforcement logic for a specific memory state.
    """
    try:
        # Check memory ownership first
        await memory_service.get_memory(
            user_id=access_context.tenant_id,
            memory_id=memory_id,
            access_context=access_context,
            required_level=MemoryAccessLevel.READ
        )
        await memory_service.reinforce_memories([memory_id])
        return {"message": "Memory reinforced successfully"}
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
        logger.error(f"Error reinforcing memory: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reinforce memory."
        )


@router.get(
    "/memories/{memory_id}/analytics",
    response_model=MemoryAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Retrieved memory analytics successfully"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        403: {"model": StandardErrorResponse, "description": "Forbidden memory ownership validation"},
        404: {"model": StandardErrorResponse, "description": "Memory not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def get_memory_analytics(
    memory_id: uuid.UUID,
    access_context: AccessContext = Depends(get_access_context),
    memory_service: MemoryService = Depends(get_memory_service),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves detailed access logs and stats for a specific memory.
    """
    try:
        # Check memory ownership
        await memory_service.get_memory(
            user_id=access_context.tenant_id,
            memory_id=memory_id,
            access_context=access_context,
            required_level=MemoryAccessLevel.READ
        )
        
        # Query memory state and access logs
        state_repo = SQLMemoryStateRepository(db)
        log_repo = SQLMemoryAccessLogRepository(db)
        
        state = await state_repo.get_by_memory_id(memory_id)
        logs = await log_repo.list_logs_by_memory(memory_id, limit=50)
        
        return MemoryAnalyticsResponse(
            memory_id=memory_id,
            state=state,
            access_logs=logs
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
        logger.error(f"Error fetching memory analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve memory analytics."
        )


@router.get(
    "/memories/hybrid/search",
    response_model=List[MemoryResponse],
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Successfully retrieved memories across system tiers"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def search_hybrid_memories(
    query: Optional[str] = Query(None, description="The hybrid search query keyword"),
    systems: Optional[str] = Query(None, description="Comma-separated tiers (semantic, episodic, procedural, working, all)"),
    conversation_id: Optional[uuid.UUID] = Query(None, description="Conversation context ID"),
    access_context: AccessContext = Depends(get_access_context),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Unified hybrid retrieval layer searching across specified memory system tiers.
    """
    try:
        from app.domain.memory_system import MemorySystem

        resolved_systems = None
        if systems and systems.strip():
            system_tokens = [s.strip().lower() for s in systems.split(",")]
            if "all" not in system_tokens:
                resolved_systems = []
                system_mapping = {
                    "semantic": MemorySystem.SEMANTIC,
                    "episodic": MemorySystem.EPISODIC,
                    "procedural": MemorySystem.PROCEDURAL,
                    "working": MemorySystem.WORKING,
                }
                for tok in system_tokens:
                    if tok in system_mapping:
                        resolved_systems.append(system_mapping[tok])

        memories = await memory_service.search_hybrid_memories(
            user_id=access_context.tenant_id,
            query=query,
            systems=resolved_systems,
            conversation_id=conversation_id,
            access_context=access_context,
        )
        return memories
    except Exception as e:
        logger.error(f"Hybrid search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Hybrid search operation failed."
        )


@router.post(
    "/memories/{memory_id}/grants",
    response_model=MemoryAccessGrantResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Memory access grant successfully created/updated"},
        400: {"model": StandardErrorResponse, "description": "Bad Request"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        403: {"model": StandardErrorResponse, "description": "Forbidden"},
        404: {"model": StandardErrorResponse, "description": "Memory or target agent not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def grant_memory_access(
    memory_id: uuid.UUID,
    payload: MemoryAccessGrantCreateRequest,
    access_context: AccessContext = Depends(get_access_context),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Grants or updates access to a specific memory for a target agent.
    """
    try:
        expires_at = None
        if payload.expires_in_days is not None:
            from datetime import datetime, timezone, timedelta
            expires_at = datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days)

        if not memory_service.auth_service:
            raise HTTPException(status_code=500, detail="Authorization service not configured")

        grant = await memory_service.auth_service.grant_access(
            access_context=access_context,
            memory_id=memory_id,
            target_agent_id=payload.agent_id,
            level=payload.access_level,
            expires_at=expires_at,
        )
        return grant
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
        logger.error(f"Error granting memory access: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to grant memory access."
        )


@router.get(
    "/memories/{memory_id}/grants",
    response_model=List[MemoryAccessGrantResponse],
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Retrieved list of active grants for the memory"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        403: {"model": StandardErrorResponse, "description": "Forbidden"},
        404: {"model": StandardErrorResponse, "description": "Memory not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def list_memory_grants(
    memory_id: uuid.UUID,
    access_context: AccessContext = Depends(get_access_context),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Lists all active, unexpired access grants for a memory.
    """
    try:
        if not memory_service.auth_service:
            raise HTTPException(status_code=500, detail="Authorization service not configured")

        grants = await memory_service.auth_service.list_active_grants(
            access_context=access_context,
            memory_id=memory_id
        )
        return grants
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
        logger.error(f"Error listing memory grants: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve memory grants."
        )


@router.post(
    "/memories/{memory_id}/grants/{agent_id}/revoke",
    response_model=MemoryAccessGrantRevokeResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Memory access grant successfully revoked"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        403: {"model": StandardErrorResponse, "description": "Forbidden"},
        404: {"model": StandardErrorResponse, "description": "Memory or grant not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def revoke_memory_access(
    memory_id: uuid.UUID,
    agent_id: uuid.UUID,
    access_context: AccessContext = Depends(get_access_context),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """
    Revokes access to a memory for a target agent.
    """
    try:
        if not memory_service.auth_service:
            raise HTTPException(status_code=500, detail="Authorization service not configured")

        grant = await memory_service.auth_service.revoke_access(
            access_context=access_context,
            memory_id=memory_id,
            target_agent_id=agent_id
        )
        return MemoryAccessGrantRevokeResponse(
            memory_id=grant.memory_id,
            agent_id=grant.agent_id,
            revoked_at=grant.revoked_at
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
        logger.error(f"Error revoking memory access: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke memory access."
        )






