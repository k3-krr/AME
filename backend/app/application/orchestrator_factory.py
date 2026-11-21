from sqlalchemy.ext.asyncio import AsyncSession

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
from app.domain.memory_router import MemoryRouter
from app.infrastructure.repositories.sql_repos import SQLRepositoryFactory
from app.application.hybrid_ranking_service import HybridRankingService
from app.application.ranking_service import RankingService
from app.application.memory_service import MemoryService
from app.application.memory_update_service import MemoryUpdateService
from app.application.memory_extraction_service import MemoryExtractionService
from app.application.memory_graph_orchestrator import MemoryGraphOrchestrator
from app.knowledge_graph.dependencies.graph_deps import (
    get_entity_extraction_service,
    get_relationship_extraction_service,
    get_hybrid_retrieval_service,
)


def build_memory_graph_orchestrator(
    db: AsyncSession,
    hybrid_retrieval_service=None
) -> MemoryGraphOrchestrator:
    """
    Constructs the MemoryGraphOrchestrator and all its required dependencies.
    """
    extraction_repo = SQLMemoryExtractionRepository(db)
    message_repo = SQLMessageRepository(db)
    memory_repo = SQLMemoryRepository(db)
    embedding_repo = SQLMemoryEmbeddingRepository(db)
    memory_state_repo = SQLMemoryStateRepository(db)
    conversation_repo = SQLConversationRepository(db)

    embedding_provider = OpenAIEmbeddingProvider()
    extraction_provider = OpenAIExtractionProvider()

    duplicate_detection_service = DuplicateDetectionService(
        embedding_repo=embedding_repo,
        embedding_provider=embedding_provider,
        memory_repo=memory_repo,
        conversation_repo=conversation_repo,
        extraction_provider=extraction_provider,
        similarity_threshold=0.82
    )

    memory_router = MemoryRouter()
    repository_factory = SQLRepositoryFactory(db)
    ranking_service = RankingService()
    hybrid_ranking_service = HybridRankingService(ranking_service)

    if hybrid_retrieval_service is None:
        hybrid_retrieval_service = get_hybrid_retrieval_service(db)

    memory_service = MemoryService(
        memory_repo=memory_repo,
        conversation_repo=conversation_repo,
        embedding_repo=embedding_repo,
        embedding_provider=embedding_provider,
        memory_state_repo=memory_state_repo,
        memory_router=memory_router,
        repository_factory=repository_factory,
        hybrid_retrieval_service=hybrid_retrieval_service,
        hybrid_ranking_service=hybrid_ranking_service
    )

    memory_update_service = MemoryUpdateService(
        memory_service=memory_service,
        memory_repo=memory_repo,
        memory_state_repo=memory_state_repo,
        conversation_repo=conversation_repo
    )

    memory_extraction_service = MemoryExtractionService(
        extraction_provider=extraction_provider,
        duplicate_detection_service=duplicate_detection_service,
        memory_update_service=memory_update_service,
        extraction_repo=extraction_repo,
        message_repo=message_repo
    )

    entity_extraction_service = get_entity_extraction_service(db)
    relationship_extraction_service = get_relationship_extraction_service(db)

    return MemoryGraphOrchestrator(
        memory_extraction_service=memory_extraction_service,
        entity_extraction_service=entity_extraction_service,
        memory_repo=memory_repo,
        extraction_repo=extraction_repo,
        relationship_extraction_service=relationship_extraction_service,
    )
