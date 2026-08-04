from typing import List
from fastapi import Depends
from app.retrieval.domain.strategy import IRetrievalStrategy
from app.retrieval.application.orchestrator import RetrievalPipelineOrchestrator
from app.config import settings


def get_retrieval_strategies() -> List[IRetrievalStrategy]:
    """
    DI provider resolving a list of available retrieval strategies.
    In Phase 1, we return an empty list as concrete strategies are not yet implemented.
    """
    return []


def get_retrieval_orchestrator(
    strategies: List[IRetrievalStrategy] = Depends(get_retrieval_strategies)
) -> RetrievalPipelineOrchestrator:
    """
    DI provider instantiating the orchestrator with resolved strategies injected.
    """
    return RetrievalPipelineOrchestrator(
        strategies=strategies,
        default_strategy_name=settings.RETRIEVAL_DEFAULT_STRATEGY
    )
