import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from app.presentation.api.auth import get_current_user
from app.infrastructure.db.models import UserTable
from app.retrieval.api.schemas import RetrievalRequestDto, GroundedContextPackageDto
from app.retrieval.domain.entities import RetrievalRequest
from app.retrieval.domain.exceptions import StrategyNotFoundError
from app.retrieval.dependencies import get_retrieval_orchestrator
from app.retrieval.application.orchestrator import RetrievalPipelineOrchestrator

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post(
    "/retrieve",
    response_model=GroundedContextPackageDto,
    status_code=status.HTTP_200_OK,
)
async def retrieve_context(
    payload: RetrievalRequestDto,
    current_user: UserTable = Depends(get_current_user),
    orchestrator: RetrievalPipelineOrchestrator = Depends(get_retrieval_orchestrator),
):
    """
    Retrieves grounded context elements based on query criteria and dynamic strategy routing.
    """
    try:
        request = RetrievalRequest(
            id=uuid.uuid4(),
            user_id=current_user.id,
            query=payload.query,
            conversation_id=payload.conversation_id,
            options=payload.options or {},
        )
        package = await orchestrator.execute_retrieval(request)
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
