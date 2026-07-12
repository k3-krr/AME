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

