import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_db
from app.presentation.api.auth import get_current_user
from app.infrastructure.db.models import UserTable
from app.config import settings

from app.infrastructure.repositories.sql_repos import (
    SQLMemoryExtractionRepository,
    SQLMessageRepository,
    SQLMemoryRepository,
    SQLMemoryEmbeddingRepository,
    SQLMemoryStateRepository,
    SQLConversationRepository,
)
from app.infrastructure.clients.embedding_client import OpenAIEmbeddingProvider
from app.infrastructure.clients.llm_client import OpenAIExtractionProvider
from app.application.duplicate_detection_service import DuplicateDetectionService
from app.application.memory_update_service import MemoryUpdateService
from app.application.memory_extraction_service import MemoryExtractionService
from app.application.memory_graph_orchestrator import MemoryGraphOrchestrator
from app.knowledge_graph.dependencies.graph_deps import get_entity_extraction_service, get_relationship_extraction_service

from app.application.memory_service import MemoryService


from app.presentation.api.schemas import (
    MemoryExtractionResponse,
    MemoryExtractionCandidateResponse,
    MemoryExtractionDetailResponse,
    ReprocessRequest,
    ReprocessResponse,
    StandardErrorResponse,
)

logger = logging.getLogger("ame_backend.api.extractions")

router = APIRouter(tags=["extractions"])


from app.knowledge_graph.dependencies.graph_deps import get_hybrid_retrieval_service


def get_extraction_service(
    db: AsyncSession = Depends(get_db),
    hybrid_retrieval_service = Depends(get_hybrid_retrieval_service),
) -> MemoryGraphOrchestrator:
    """Dependency helper instantiating MemoryGraphOrchestrator wrapping extraction service."""
    from app.application.orchestrator_factory import build_memory_graph_orchestrator
    return build_memory_graph_orchestrator(
        db=db,
        hybrid_retrieval_service=hybrid_retrieval_service
    )



@router.post(
    "/conversations/{conversation_id}/extract",
    response_model=MemoryExtractionResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Dialogue memory extraction executed successfully"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        403: {"model": StandardErrorResponse, "description": "Forbidden conversation owner check"},
        404: {"model": StandardErrorResponse, "description": "Conversation not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def manual_extract_memories(
    conversation_id: uuid.UUID,
    current_user: UserTable = Depends(get_current_user),
    extraction_service: MemoryGraphOrchestrator = Depends(get_extraction_service),
    db: AsyncSession = Depends(get_db),
):
    """
    Manually triggers autonomous memory extraction for a conversation turn.
    """
    try:
        # Check conversation ownership
        conversation_repo = SQLConversationRepository(db)
        conversation = await conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise KeyError("Conversation not found")
        if conversation.user_id != current_user.id:
            raise PermissionError("Access forbidden: User does not own the conversation")

        extraction_id = await extraction_service.extract_memories_from_turns(conversation_id)

        # Load result
        state_repo = SQLMemoryExtractionRepository(db)
        result = await state_repo.get_extraction_with_candidates(extraction_id)
        if not result:
            raise HTTPException(status_code=500, detail="Failed to retrieve extraction log result.")

        return MemoryExtractionResponse.from_orm(result[0])

    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(f"Manual extraction failed: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to run extraction pipeline.")


@router.get(
    "/extractions/history",
    response_model=List[MemoryExtractionResponse],
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Retrieved list of extraction audit records successfully"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def list_extractions_history(
    conversation_id: uuid.UUID,
    page: int = 1,
    limit: int = 20,
    current_user: UserTable = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves the list of past extraction audit records for a given conversation.
    """
    try:
        # Validate conversation ownership
        conversation_repo = SQLConversationRepository(db)
        conversation = await conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise KeyError("Conversation not found")
        if conversation.user_id != current_user.id:
            raise PermissionError("Access forbidden")

        extraction_repo = SQLMemoryExtractionRepository(db)
        history = await extraction_repo.list_extractions_by_conversation(
            conversation_id=conversation_id, page=page, limit=limit
        )
        return [MemoryExtractionResponse.from_orm(h) for h in history]

    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing extraction history: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch history.")


@router.get(
    "/extractions/{extraction_id}",
    response_model=MemoryExtractionDetailResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Retrieved detailed extraction log successfully"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        403: {"model": StandardErrorResponse, "description": "Forbidden context access check"},
        404: {"model": StandardErrorResponse, "description": "Extraction log not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def get_extraction_details(
    extraction_id: uuid.UUID,
    current_user: UserTable = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves details of a specific memory extraction operation and its candidates.
    """
    try:
        extraction_repo = SQLMemoryExtractionRepository(db)
        result = await extraction_repo.get_extraction_with_candidates(extraction_id)
        if not result:
            raise KeyError("Extraction log not found")

        # Verify owner of conversation linked to this extraction
        conversation_repo = SQLConversationRepository(db)
        conversation = await conversation_repo.get_by_id(result[0].conversation_id)
        if not conversation or conversation.user_id != current_user.id:
            raise PermissionError("Access forbidden")

        extraction_domain, candidates_domain = result
        return MemoryExtractionDetailResponse(
            extraction=MemoryExtractionResponse.from_orm(extraction_domain),
            candidates=[MemoryExtractionCandidateResponse.from_orm(c) for c in candidates_domain]
        )

    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching extraction details: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch extraction log.")


@router.post(
    "/extractions/reprocess",
    response_model=ReprocessResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Batch reprocessing completed successfully"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def reprocess_conversations(
    request: ReprocessRequest,
    current_user: UserTable = Depends(get_current_user),
    extraction_service: MemoryGraphOrchestrator = Depends(get_extraction_service),
    db: AsyncSession = Depends(get_db),
):
    """
    Batch processes a list of conversations to backfill and synchronize extracted memories.
    """
    reprocessed_count = 0
    conversation_repo = SQLConversationRepository(db)
    for conversation_id in request.conversation_ids:
        try:
            conversation = await conversation_repo.get_by_id(conversation_id)
            if not conversation or conversation.user_id != current_user.id:
                continue
            await extraction_service.extract_memories_from_turns(conversation_id)
            reprocessed_count += 1
        except Exception as e:
            logger.error(f"Error reprocessing conversation {conversation_id}: {e}")
            continue

    return ReprocessResponse(reprocessed_count=reprocessed_count)
