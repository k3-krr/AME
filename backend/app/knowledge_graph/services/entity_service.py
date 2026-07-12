import uuid
from typing import Optional, List
from datetime import datetime

from app.knowledge_graph.domain.entities import Node, NodeType, EntityType, normalize_canonical_name
from app.knowledge_graph.domain.repositories import IEntityRepository
from app.knowledge_graph.exceptions import EntityNotFoundError, DuplicateEntityError


class EntityService:
    """Service layer managing business rules, validation, and CRUD operations for Entities."""

    def __init__(self, entity_repo: IEntityRepository):
        self.entity_repo = entity_repo

    async def create_entity(
        self,
        user_id: uuid.UUID,
        name: str,
        entity_type: EntityType,
        metadata: Optional[dict] = None,
    ) -> Node:
        """Validates and creates a new Entity node for a user."""
        if not name or not name.strip():
            raise ValueError("Entity name cannot be empty")
        if not entity_type:
            raise ValueError("Entity type is required")

        canonical = normalize_canonical_name(name)

        # Check for duplication within the user's graph scope
        existing = await self.entity_repo.get_by_name(user_id, canonical)
        if existing:
            raise DuplicateEntityError(
                f"Entity with canonical name '{canonical}' already exists for this user."
            )

        entity = Node(
            id=uuid.uuid4(),
            user_id=user_id,
            node_type=NodeType.ENTITY,
            name=name.strip(),
            canonical_name=canonical,
            entity_type=entity_type,
            metadata=metadata or {},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        entity.validate()
        return await self.entity_repo.create(entity)

    async def get_entity(self, user_id: uuid.UUID, entity_id: uuid.UUID) -> Node:
        """Retrieves an entity, raising an error if it doesn't exist or is not owned by the user."""
        entity = await self.entity_repo.get_by_id(entity_id)
        if not entity or entity.user_id != user_id:
            raise EntityNotFoundError(f"Entity with ID {entity_id} not found.")
        return entity

    async def update_entity(
        self,
        user_id: uuid.UUID,
        entity_id: uuid.UUID,
        name: Optional[str] = None,
        entity_type: Optional[EntityType] = None,
        metadata: Optional[dict] = None,
    ) -> Node:
        """Updates attributes of an existing entity node."""
        entity = await self.get_entity(user_id, entity_id)

        if name is not None:
            name_str = name.strip()
            if not name_str:
                raise ValueError("Entity name cannot be empty")
            canonical = normalize_canonical_name(name_str)
            if canonical != entity.canonical_name:
                # Check duplication for updated name
                existing = await self.entity_repo.get_by_name(user_id, canonical)
                if existing and existing.id != entity_id:
                    raise DuplicateEntityError(
                        f"Entity with canonical name '{canonical}' already exists."
                    )
                entity.name = name_str
                entity.canonical_name = canonical

        if entity_type is not None:
            entity.entity_type = entity_type

        if metadata is not None:
            entity.metadata = metadata

        entity.updated_at = datetime.utcnow()
        entity.validate()
        return await self.entity_repo.update(entity)

    async def delete_entity(self, user_id: uuid.UUID, entity_id: uuid.UUID) -> bool:
        """Hard deletes an entity node. Triggers DB-level cascades to remove linked relationships."""
        # Ensure existence & ownership first
        await self.get_entity(user_id, entity_id)
        return await self.entity_repo.delete(entity_id)

    async def list_entities(
        self,
        user_id: uuid.UUID,
        entity_type: Optional[EntityType] = None,
        canonical_name: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> List[Node]:
        """Lists and filters entities with support for pagination."""
        if page < 1:
            page = 1
        if limit < 1 or limit > 100:
            limit = 20
        if sort_by not in ("created_at", "updated_at", "name"):
            sort_by = "created_at"
        if sort_order not in ("asc", "desc"):
            sort_order = "desc"

        return await self.entity_repo.list_by_user(
            user_id=user_id,
            entity_type=entity_type,
            canonical_name=canonical_name,
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    async def resolve_entity(
        self,
        user_id: uuid.UUID,
        name: str,
        entity_type: EntityType,
        metadata: Optional[dict] = None,
    ) -> Node:
        """
        Resolves an entity: if a node with the same canonical name exists, returns it.
        Otherwise, creates a new entity node.
        """
        canonical = normalize_canonical_name(name)
        existing = await self.entity_repo.get_by_name(user_id, canonical)
        if existing:
            return existing
        return await self.create_entity(user_id, name, entity_type, metadata)

stream = None
