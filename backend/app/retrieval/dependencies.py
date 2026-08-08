from typing import List
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.sql_repos import (
    SQLMemoryRepository,
    SQLMemoryEmbeddingRepository,
    SQLMemoryStateRepository,
)
from app.knowledge_graph.repositories.sql_repositories import SQLGraphRepository
from app.infrastructure.clients.embedding_client import OpenAIEmbeddingProvider
from app.presentation.api.memories import get_ranking_service
from app.knowledge_graph.dependencies.graph_deps import get_hybrid_retrieval_service
from app.application.hybrid_ranking_service import HybridRankingService

from app.retrieval.domain.value_objects import RetrievalCapability
from app.retrieval.domain.context_fusion_service import ContextFusionService
from app.retrieval.domain.services import (
    QueryNormalizer,
    IntentDetector,
    QueryClassifier,
    IAbbreviationProvider,
    DefaultAbbreviationProvider,
    QueryRewriter,
    QueryExpansionService,
    MultiQueryGenerator,
)
from app.retrieval.domain.grounding import (
    IContextCompressor,
    DefaultContextCompressor,
    ICitationBuilder,
    DefaultCitationBuilder,
    IPromptBuilder,
    DefaultPromptBuilder,
    IGroundedContextValidator,
    DefaultGroundedContextValidator,
)
from app.retrieval.application.executor_registry import ExecutorRegistry
from app.retrieval.application.executors import (
    HybridRetrievalExecutor,
    GraphRetrievalExecutor,
    WorkingMemoryExecutor,
)
from app.retrieval.application.query_understanding_service import QueryUnderstandingService
from app.retrieval.application.query_rewrite_service import QueryRewriteService
from app.retrieval.application.retrieval_orchestrator import RetrievalOrchestrator
from app.retrieval.application.grounding_service import GroundingService
from app.config import settings


def get_query_normalizer() -> QueryNormalizer:
    """DI provider resolving the QueryNormalizer."""
    return QueryNormalizer()


def get_intent_detector() -> IntentDetector:
    """DI provider resolving the IntentDetector."""
    return IntentDetector()


def get_query_classifier() -> QueryClassifier:
    """DI provider resolving the QueryClassifier."""
    return QueryClassifier()


def get_query_understanding_service(
    normalizer: QueryNormalizer = Depends(get_query_normalizer),
    detector: IntentDetector = Depends(get_intent_detector),
    classifier: QueryClassifier = Depends(get_query_classifier)
) -> QueryUnderstandingService:
    """DI provider resolving the QueryUnderstandingService instantiation."""
    return QueryUnderstandingService(
        normalizer=normalizer,
        detector=detector,
        classifier=classifier
    )


def get_abbreviation_provider() -> IAbbreviationProvider:
    """DI provider resolving the abbreviation configuration mapping."""
    return DefaultAbbreviationProvider()


def get_query_rewriter(
    provider: IAbbreviationProvider = Depends(get_abbreviation_provider)
) -> QueryRewriter:
    """DI provider resolving the QueryRewriter with abbreviation provider injected."""
    return QueryRewriter(abbreviation_provider=provider)


def get_query_expansion_service() -> QueryExpansionService:
    """DI provider resolving the QueryExpansionService."""
    return QueryExpansionService()


def get_multi_query_generator() -> MultiQueryGenerator:
    """DI provider resolving the MultiQueryGenerator."""
    return MultiQueryGenerator()


def get_query_rewrite_service(
    normalizer: QueryNormalizer = Depends(get_query_normalizer),
    rewriter: QueryRewriter = Depends(get_query_rewriter),
    expansion: QueryExpansionService = Depends(get_query_expansion_service),
    generator: MultiQueryGenerator = Depends(get_multi_query_generator)
) -> QueryRewriteService:
    """DI provider resolving the QueryRewriteService instantiation."""
    return QueryRewriteService(
        normalizer=normalizer,
        rewriter=rewriter,
        expansion=expansion,
        generator=generator
    )


def get_context_fusion_service() -> ContextFusionService:
    """DI provider resolving the ContextFusionService."""
    return ContextFusionService()


def get_executor_registry(
    db: AsyncSession = Depends(get_db),
    hybrid_retrieval_service = Depends(get_hybrid_retrieval_service),
) -> ExecutorRegistry:
    """DI provider instantiating the ExecutorRegistry containing all retrieval executors."""
    embedding_provider = OpenAIEmbeddingProvider()
    
    # 1. Initialize Hybrid Executors
    semantic_exec = HybridRetrievalExecutor(
        capability=RetrievalCapability.SEMANTIC_SEARCH,
        hybrid_retrieval_service=hybrid_retrieval_service,
        embedding_provider=embedding_provider,
    )
    episodic_exec = HybridRetrievalExecutor(
        capability=RetrievalCapability.EPISODIC_SEARCH,
        hybrid_retrieval_service=hybrid_retrieval_service,
        embedding_provider=embedding_provider,
    )
    procedural_exec = HybridRetrievalExecutor(
        capability=RetrievalCapability.PROCEDURAL_SEARCH,
        hybrid_retrieval_service=hybrid_retrieval_service,
        embedding_provider=embedding_provider,
    )
    
    # 2. Initialize Working Memory Executor
    working_exec = WorkingMemoryExecutor(
        hybrid_retrieval_service=hybrid_retrieval_service,
        embedding_provider=embedding_provider,
    )
    
    # 3. Initialize Graph Retrieval Executor
    graph_repo = SQLGraphRepository(db)
    memory_repo = SQLMemoryRepository(db)
    graph_exec = GraphRetrievalExecutor(
        graph_repo=graph_repo,
        memory_repo=memory_repo,
    )
    
    return ExecutorRegistry(
        executors=[
            semantic_exec,
            episodic_exec,
            procedural_exec,
            working_exec,
            graph_exec,
        ]
    )


def get_retrieval_orchestrator(
    query_understanding_service: QueryUnderstandingService = Depends(get_query_understanding_service),
    query_rewrite_service: QueryRewriteService = Depends(get_query_rewrite_service),
    executor_registry: ExecutorRegistry = Depends(get_executor_registry),
    ranking_service = Depends(get_ranking_service),
    db: AsyncSession = Depends(get_db),
    context_fusion_service: ContextFusionService = Depends(get_context_fusion_service),
) -> RetrievalOrchestrator:
    """DI provider resolving the end-to-end RetrievalOrchestrator."""
    embedding_repo = SQLMemoryEmbeddingRepository(db)
    memory_state_repo = SQLMemoryStateRepository(db)
    embedding_provider = OpenAIEmbeddingProvider()
    hybrid_ranking_service = HybridRankingService(ranking_service)
    
    return RetrievalOrchestrator(
        query_understanding_service=query_understanding_service,
        query_rewrite_service=query_rewrite_service,
        executor_registry=executor_registry,
        hybrid_ranking_service=hybrid_ranking_service,
        embedding_repo=embedding_repo,
        memory_state_repo=memory_state_repo,
        context_fusion_service=context_fusion_service,
        embedding_provider=embedding_provider,
    )


def get_context_compressor() -> IContextCompressor:
    """DI provider resolving the DefaultContextCompressor."""
    return DefaultContextCompressor()


def get_citation_builder() -> ICitationBuilder:
    """DI provider resolving the DefaultCitationBuilder."""
    return DefaultCitationBuilder()


def get_prompt_builder() -> IPromptBuilder:
    """DI provider resolving the DefaultPromptBuilder."""
    return DefaultPromptBuilder()


def get_grounded_context_validator() -> IGroundedContextValidator:
    """DI provider resolving the DefaultGroundedContextValidator."""
    return DefaultGroundedContextValidator()


def get_grounding_service(
    compressor: IContextCompressor = Depends(get_context_compressor),
    citation_builder: ICitationBuilder = Depends(get_citation_builder),
    prompt_builder: IPromptBuilder = Depends(get_prompt_builder),
    validator: IGroundedContextValidator = Depends(get_grounded_context_validator),
) -> GroundingService:
    """DI provider resolving the GroundingService."""
    return GroundingService(
        compressor=compressor,
        citation_builder=citation_builder,
        prompt_builder=prompt_builder,
        validator=validator,
    )
