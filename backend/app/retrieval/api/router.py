import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from app.presentation.api.auth import get_current_user
from app.infrastructure.db.models import UserTable
from app.retrieval.api.schemas import (
    RetrievalRequestDto,
    GroundedContextPackageDto,
    QueryAnalysisResultDto,
    QueryRewriteResultDto,
    GroundedPromptPackageDto,
)
from app.retrieval.domain.exceptions import StrategyNotFoundError
from app.retrieval.dependencies import (
    get_retrieval_orchestrator,
    get_query_understanding_service,
    get_query_rewrite_service,
    get_grounding_service,
)
from app.retrieval.application.retrieval_orchestrator import RetrievalOrchestrator
from app.retrieval.application.query_understanding_service import QueryUnderstandingService
from app.retrieval.application.query_rewrite_service import QueryRewriteService
from app.retrieval.application.grounding_service import GroundingService

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post(
    "/retrieve",
    response_model=GroundedContextPackageDto,
    status_code=status.HTTP_200_OK,
)
async def retrieve_context(
    payload: RetrievalRequestDto,
    current_user: UserTable = Depends(get_current_user),
    orchestrator: RetrievalOrchestrator = Depends(get_retrieval_orchestrator),
):
    """
    Retrieves grounded context elements based on query criteria and dynamic capability execution.
    """
    try:
        package = await orchestrator.retrieve(
            user_id=current_user.id,
            query=payload.query,
            conversation_id=payload.conversation_id,
            options=payload.options or {},
        )
        return package
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except StrategyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Retrieval process execution failed: {str(e)}"
        )


@router.post(
    "/ground",
    response_model=GroundedPromptPackageDto,
    status_code=status.HTTP_200_OK,
)
async def ground_retrieval(
    payload: RetrievalRequestDto,
    current_user: UserTable = Depends(get_current_user),
    retrieval_orchestrator: RetrievalOrchestrator = Depends(get_retrieval_orchestrator),
    grounding_service: GroundingService = Depends(get_grounding_service),
):
    """
    Executes E2E context retrieval and formats outputs into a vendor-neutral prompt package.
    """
    try:
        # 1. Run context retrieval E2E
        context_package = await retrieval_orchestrator.retrieve(
            user_id=current_user.id,
            query=payload.query,
            conversation_id=payload.conversation_id,
            options=payload.options or {},
        )
        
        # 2. Extract options configurations
        options = payload.options or {}
        base_prompt = options.get("base_system_prompt")
        max_chars = options.get("max_context_chars", 4000)
        
        # 3. Compile prompt package
        prompt_package = grounding_service.prepare_grounded_prompt(
            user_query=payload.query,
            context_package=context_package,
            base_system_prompt=base_prompt,
            max_context_chars=max_chars,
        )
        return prompt_package
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prompt grounding execution failed: {str(e)}"
        )


@router.post(
    "/analyze",
    response_model=QueryAnalysisResultDto,
    status_code=status.HTTP_200_OK,
)
async def analyze_query(
    payload: RetrievalRequestDto,
    current_user: UserTable = Depends(get_current_user),
    service: QueryUnderstandingService = Depends(get_query_understanding_service),
):
    """
    Diagnostic endpoint to normalize, detect intent, and classify capabilities for a raw query.
    """
    try:
        return service.analyze_query(payload.query)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query analysis failed: {str(e)}"
        )


@router.post(
    "/rewrite",
    response_model=QueryRewriteResultDto,
    status_code=status.HTTP_200_OK,
)
async def rewrite_query(
    payload: RetrievalRequestDto,
    current_user: UserTable = Depends(get_current_user),
    service: QueryRewriteService = Depends(get_query_rewrite_service),
):
    """
    Diagnostic endpoint to normalize, rewrite, expand, and generate subqueries for a raw query.
    """
    try:
        return service.rewrite_query(payload.query)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query rewrite failed: {str(e)}"
        )
