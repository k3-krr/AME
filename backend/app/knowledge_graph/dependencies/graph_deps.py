from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.sql_repos import SQLMemoryRepository
from app.knowledge_graph.repositories.sql_repositories import (
    SQLEntityRepository,
    SQLRelationshipRepository,
    SQLGraphRepository,
)
from app.knowledge_graph.services.entity_service import EntityService
from app.knowledge_graph.services.relationship_service import RelationshipService
from app.knowledge_graph.services.graph_service import GraphService


def get_entity_service(db: AsyncSession = Depends(get_db)) -> EntityService:
    entity_repo = SQLEntityRepository(db)
    return EntityService(entity_repo)


def get_relationship_service(db: AsyncSession = Depends(get_db)) -> RelationshipService:
    relationship_repo = SQLRelationshipRepository(db)
    entity_repo = SQLEntityRepository(db)
    return RelationshipService(relationship_repo, entity_repo)


def get_graph_service(db: AsyncSession = Depends(get_db)) -> GraphService:
    graph_repo = SQLGraphRepository(db)
    memory_repo = SQLMemoryRepository(db)
    entity_service = get_entity_service(db)
    relationship_service = get_relationship_service(db)
    return GraphService(
        graph_repo=graph_repo,
        memory_repo=memory_repo,
        entity_service=entity_service,
        relationship_service=relationship_service,
    )


from app.knowledge_graph.services.extraction_provider import RuleBasedProvider
from app.knowledge_graph.services.entity_extractor import EntityExtractor
from app.knowledge_graph.services.entity_extraction_service import EntityExtractionService


def get_entity_extraction_service(db: AsyncSession = Depends(get_db)) -> EntityExtractionService:
    provider = RuleBasedProvider()
    extractor = EntityExtractor(provider)
    entity_service = get_entity_service(db)
    graph_service = get_graph_service(db)
    return EntityExtractionService(
        extractor=extractor,
        entity_service=entity_service,
        graph_service=graph_service,
    )


from app.knowledge_graph.services.relationship_provider import RuleBasedRelationshipProvider
from app.knowledge_graph.services.relationship_builder import RelationshipBuilder
from app.knowledge_graph.services.relationship_extraction_service import RelationshipExtractionService


def get_relationship_extraction_service(db: AsyncSession = Depends(get_db)) -> RelationshipExtractionService:
    provider = RuleBasedRelationshipProvider()
    builder = RelationshipBuilder(provider)
    relationship_service = get_relationship_service(db)
    return RelationshipExtractionService(
        builder=builder,
        relationship_service=relationship_service,
    )


from app.knowledge_graph.services.graph_traversal_service import GraphTraversalService


def get_graph_traversal_service(db: AsyncSession = Depends(get_db)) -> GraphTraversalService:
    graph_repo = SQLGraphRepository(db)
    return GraphTraversalService(graph_repo)


from app.knowledge_graph.services.expansion_service import KnowledgeGraphExpansionService
from app.application.graph_aware_hybrid_retrieval_service import GraphAwareHybridRetrievalService
from app.application.hybrid_retrieval_service import HybridRetrievalService
from app.infrastructure.repositories.sql_repos import SQLMemoryRepository


def get_graph_expansion_service(db: AsyncSession = Depends(get_db)) -> KnowledgeGraphExpansionService:
    graph_repo = SQLGraphRepository(db)
    return KnowledgeGraphExpansionService(graph_repo)


def get_hybrid_retrieval_service(db: AsyncSession = Depends(get_db)) -> HybridRetrievalService:
    from app.infrastructure.repositories.sql_repos import SQLRepositoryFactory
    repository_factory = SQLRepositoryFactory(db)
    base_retrieval_service = HybridRetrievalService(repository_factory)
    
    expansion_service = get_graph_expansion_service(db)
    memory_repo = SQLMemoryRepository(db)
    
    # Compose services inside GraphAwareHybridRetrievalService
    return GraphAwareHybridRetrievalService(
        base_retrieval_service=base_retrieval_service,
        expansion_service=expansion_service,
        memory_repo=memory_repo,
    )




