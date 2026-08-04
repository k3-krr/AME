import uuid
from typing import Optional, List
from datetime import datetime

from app.knowledge_graph.domain.entities import Relationship, RelationshipType
from app.knowledge_graph.domain.repositories import IRelationshipRepository, IEntityRepository
from app.knowledge_graph.exceptions import (
    RelationshipNotFoundError,
    EntityNotFoundError,
    DuplicateRelationshipError,
)


class RelationshipService:
    """Service layer managing business rules, validation, and CRUD operations for Relationships."""

    def __init__(
        self,
        relationship_repo: IRelationshipRepository,
        entity_repo: IEntityRepository,
    ):
        self.relationship_repo = relationship_repo
        self.entity_repo = entity_repo

    async def create_relationship(
        self,
        user_id: uuid.UUID,
        source_node_id: uuid.UUID,
        target_node_id: uuid.UUID,
        relationship_type: RelationshipType,
        confidence: float = 1.0,
        metadata: Optional[dict] = None,
        prevent_self_loops: bool = False,
    ) -> Relationship:
        """Creates a relationship edge after validating endpoint existence and uniqueness."""
        if not relationship_type:
            raise ValueError("Relationship type is required")
        if not (0.0 <= confidence <= 1.0):
            raise ValueError("Confidence must be between 0.0 and 1.0 inclusive")

        # 1. Validate endpoints exist and belong to the user
        source = await self.entity_repo.get_by_id(source_node_id)
        if not source or source.user_id != user_id:
            raise EntityNotFoundError(f"Source entity with ID {source_node_id} not found.")

        target = await self.entity_repo.get_by_id(target_node_id)
        if not target or target.user_id != user_id:
            raise EntityNotFoundError(f"Target entity with ID {target_node_id} not found.")

        if prevent_self_loops and source_node_id == target_node_id:
            raise ValueError("Self-referential loops are not allowed in relationships")

        # 2. Check for duplicate relationship edge
        existing = await self.relationship_repo.get_by_endpoints(
            user_id, source_node_id, target_node_id, relationship_type
        )
        if existing:
            raise DuplicateRelationshipError(
                f"Relationship '{relationship_type.value}' already exists between these entities."
            )

        relationship = Relationship(
            id=uuid.uuid4(),
            user_id=user_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            relationship_type=relationship_type,
            confidence=confidence,
            metadata=metadata or {},
            created_at=datetime.utcnow(),
        )
        relationship.validate(prevent_self_loops=prevent_self_loops)
        return await self.relationship_repo.create(relationship)

    async def resolve_relationship(
        self,
        user_id: uuid.UUID,
        source_node_id: uuid.UUID,
        target_node_id: uuid.UUID,
        relationship_type: RelationshipType,
        confidence: float = 1.0,
        metadata: Optional[dict] = None,
        prevent_self_loops: bool = False,
    ) -> Relationship:
        """
        Resolves a relationship: if the edge already exists for endpoints and type,
        reuses/returns it. Otherwise, creates a new relationship edge.
        """
        existing = await self.relationship_repo.get_by_endpoints(
            user_id, source_node_id, target_node_id, relationship_type
        )
        if existing:
            return existing
        return await self.create_relationship(
            user_id=user_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            relationship_type=relationship_type,
            confidence=confidence,
            metadata=metadata,
            prevent_self_loops=prevent_self_loops,
        )


    async def get_relationship(self, user_id: uuid.UUID, relationship_id: uuid.UUID) -> Relationship:
        """Retrieves a relationship edge, validating user ownership."""
        rel = await self.relationship_repo.get_by_id(relationship_id)
        if not rel or rel.user_id != user_id:
            raise RelationshipNotFoundError(f"Relationship with ID {relationship_id} not found.")
        return rel

    async def update_relationship(
        self,
        user_id: uuid.UUID,
        relationship_id: uuid.UUID,
        relationship_type: Optional[RelationshipType] = None,
        confidence: Optional[float] = None,
        metadata: Optional[dict] = None,
        prevent_self_loops: bool = False,
    ) -> Relationship:
        """Updates attributes of an existing relationship edge."""
        rel = await self.get_relationship(user_id, relationship_id)

        if relationship_type is not None:
            # Check duplication if relationship type is changing
            if relationship_type != rel.relationship_type:
                existing = await self.relationship_repo.get_by_endpoints(
                    user_id, rel.source_node_id, rel.target_node_id, relationship_type
                )
                if existing and existing.id != relationship_id:
                    raise DuplicateRelationshipError(
                        f"Relationship '{relationship_type.value}' already exists between these entities."
                    )
            rel.relationship_type = relationship_type

        if confidence is not None:
            if not (0.0 <= confidence <= 1.0):
                raise ValueError("Confidence must be between 0.0 and 1.0 inclusive")
            rel.confidence = confidence

        if metadata is not None:
            rel.metadata = metadata

        rel.validate(prevent_self_loops=prevent_self_loops)
        return await self.relationship_repo.update(rel)

    async def delete_relationship(self, user_id: uuid.UUID, relationship_id: uuid.UUID) -> bool:
        """Hard deletes a relationship edge."""
        # Ensure existence & ownership first
        await self.get_relationship(user_id, relationship_id)
        return await self.relationship_repo.delete(relationship_id)

    async def list_relationships(
        self,
        user_id: uuid.UUID,
        source_node_id: Optional[uuid.UUID] = None,
        target_node_id: Optional[uuid.UUID] = None,
        relationship_type: Optional[RelationshipType] = None,
        page: int = 1,
        limit: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> List[Relationship]:
        """Lists and filters relationships for a user with pagination support."""
        if page < 1:
            page = 1
        if limit < 1 or limit > 100:
            limit = 20
        if sort_by not in ("created_at", "confidence"):
            sort_by = "created_at"
        if sort_order not in ("asc", "desc"):
            sort_order = "desc"

        return await self.relationship_repo.list_by_user(
            user_id=user_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            relationship_type=relationship_type,
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
        )
