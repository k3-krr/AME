import uuid
from typing import Optional, List, Tuple
from sqlalchemy import select, delete, desc, asc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_graph.domain.entities import (
    Node,
    NodeType,
    EntityType,
    Relationship,
    RelationshipType,
    MemoryNodeMapping,
)
from app.knowledge_graph.domain.repositories import (
    IEntityRepository,
    IRelationshipRepository,
    IMemoryNodeMappingRepository,
    IGraphRepository,
)
from app.knowledge_graph.models.models import (
    NodeTable,
    RelationshipTable,
    MemoryNodeMappingTable,
)
from app.knowledge_graph.repositories.mappers.entity_mapper import to_domain, to_table
from app.knowledge_graph.repositories.mappers.relationship_mapper import (
    relationship_to_domain,
    relationship_to_table,
    mapping_to_domain,
    mapping_to_table,
)


class SQLEntityRepository(IEntityRepository):
    """SQLAlchemy concrete repository managing Entity Node records."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, entity_id: uuid.UUID) -> Optional[Node]:
        result = await self.session.execute(
            select(NodeTable).where(
                and_(
                    NodeTable.id == entity_id,
                    NodeTable.node_type == NodeType.ENTITY.value,
                )
            )
        )
        table = result.scalars().first()
        return to_domain(table) if table else None

    async def get_by_name(self, user_id: uuid.UUID, canonical_name: str) -> Optional[Node]:
        result = await self.session.execute(
            select(NodeTable).where(
                and_(
                    NodeTable.user_id == user_id,
                    NodeTable.canonical_name == canonical_name,
                    NodeTable.node_type == NodeType.ENTITY.value,
                )
            )
        )
        table = result.scalars().first()
        return to_domain(table) if table else None

    async def create(self, entity: Node) -> Node:
        table = to_table(entity)
        table.node_type = NodeType.ENTITY.value
        self.session.add(table)
        await self.session.flush()
        await self.session.refresh(table)
        return to_domain(table)

    async def update(self, entity: Node) -> Node:
        result = await self.session.execute(
            select(NodeTable).where(
                and_(
                    NodeTable.id == entity.id,
                    NodeTable.node_type == NodeType.ENTITY.value,
                )
            )
        )
        table = result.scalars().first()
        if not table:
            raise KeyError("Entity node not found")
        
        table.name = entity.name
        table.canonical_name = entity.canonical_name
        table.entity_type = entity.entity_type.value if entity.entity_type else None
        table.metadata_dict = entity.metadata or {}
        table.updated_at = entity.updated_at

        await self.session.flush()
        await self.session.refresh(table)
        return to_domain(table)

    async def delete(self, entity_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            delete(NodeTable).where(
                and_(
                    NodeTable.id == entity_id,
                    NodeTable.node_type == NodeType.ENTITY.value,
                )
            )
        )
        await self.session.flush()
        return result.rowcount > 0

    async def list_by_user(
        self,
        user_id: uuid.UUID,
        entity_type: Optional[EntityType] = None,
        canonical_name: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> List[Node]:
        query = select(NodeTable).where(
            and_(
                NodeTable.user_id == user_id,
                NodeTable.node_type == NodeType.ENTITY.value,
            )
        )
        if entity_type:
            query = query.where(NodeTable.entity_type == entity_type.value)
        if canonical_name:
            query = query.where(NodeTable.canonical_name == canonical_name)

        sort_col = getattr(NodeTable, sort_by, NodeTable.created_at)
        if sort_order == "desc":
            query = query.order_by(desc(sort_col))
        else:
            query = query.order_by(asc(sort_col))

        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)

        result = await self.session.execute(query)
        return [to_domain(r) for r in result.scalars().all()]


class SQLRelationshipRepository(IRelationshipRepository):
    """SQLAlchemy concrete repository managing Relationship edges."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, relationship_id: uuid.UUID) -> Optional[Relationship]:
        result = await self.session.execute(
            select(RelationshipTable).where(RelationshipTable.id == relationship_id)
        )
        table = result.scalars().first()
        return relationship_to_domain(table) if table else None

    async def get_by_endpoints(
        self,
        user_id: uuid.UUID,
        source_node_id: uuid.UUID,
        target_node_id: uuid.UUID,
        relationship_type: RelationshipType,
    ) -> Optional[Relationship]:
        result = await self.session.execute(
            select(RelationshipTable).where(
                and_(
                    RelationshipTable.user_id == user_id,
                    RelationshipTable.source_node_id == source_node_id,
                    RelationshipTable.target_node_id == target_node_id,
                    RelationshipTable.relationship_type == relationship_type.value,
                )
            )
        )
        table = result.scalars().first()
        return relationship_to_domain(table) if table else None

    async def create(self, relationship: Relationship) -> Relationship:
        table = relationship_to_table(relationship)
        self.session.add(table)
        await self.session.flush()
        await self.session.refresh(table)
        return relationship_to_domain(table)

    async def update(self, relationship: Relationship) -> Relationship:
        result = await self.session.execute(
            select(RelationshipTable).where(RelationshipTable.id == relationship.id)
        )
        table = result.scalars().first()
        if not table:
            raise KeyError("Relationship edge not found")

        table.relationship_type = relationship.relationship_type.value
        table.confidence = relationship.confidence
        table.metadata_dict = relationship.metadata or {}

        await self.session.flush()
        await self.session.refresh(table)
        return relationship_to_domain(table)

    async def delete(self, relationship_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            delete(RelationshipTable).where(RelationshipTable.id == relationship_id)
        )
        await self.session.flush()
        return result.rowcount > 0

    async def list_by_user(
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
        query = select(RelationshipTable).where(RelationshipTable.user_id == user_id)
        if source_node_id:
            query = query.where(RelationshipTable.source_node_id == source_node_id)
        if target_node_id:
            query = query.where(RelationshipTable.target_node_id == target_node_id)
        if relationship_type:
            query = query.where(RelationshipTable.relationship_type == relationship_type.value)

        sort_col = getattr(RelationshipTable, sort_by, RelationshipTable.created_at)
        if sort_order == "desc":
            query = query.order_by(desc(sort_col))
        else:
            query = query.order_by(asc(sort_col))

        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)

        result = await self.session.execute(query)
        return [relationship_to_domain(r) for r in result.scalars().all()]


class SQLMemoryNodeMappingRepository(IMemoryNodeMappingRepository):
    """SQLAlchemy concrete repository managing Memory-Node mappings."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, mapping: MemoryNodeMapping) -> MemoryNodeMapping:
        table = mapping_to_table(mapping)
        self.session.add(table)
        await self.session.flush()
        await self.session.refresh(table)
        return mapping_to_domain(table)

    async def delete(self, memory_id: uuid.UUID, node_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            delete(MemoryNodeMappingTable).where(
                and_(
                    MemoryNodeMappingTable.memory_id == memory_id,
                    MemoryNodeMappingTable.node_id == node_id,
                )
            )
        )
        await self.session.flush()
        return result.rowcount > 0

    async def get_by_ids(self, memory_id: uuid.UUID, node_id: uuid.UUID) -> Optional[MemoryNodeMapping]:
        result = await self.session.execute(
            select(MemoryNodeMappingTable).where(
                and_(
                    MemoryNodeMappingTable.memory_id == memory_id,
                    MemoryNodeMappingTable.node_id == node_id,
                )
            )
        )
        table = result.scalars().first()
        return mapping_to_domain(table) if table else None

    async def list_by_memory(self, memory_id: uuid.UUID) -> List[MemoryNodeMapping]:
        result = await self.session.execute(
            select(MemoryNodeMappingTable).where(MemoryNodeMappingTable.memory_id == memory_id)
        )
        return [mapping_to_domain(r) for r in result.scalars().all()]

    async def list_by_node(self, node_id: uuid.UUID) -> List[MemoryNodeMapping]:
        result = await self.session.execute(
            select(MemoryNodeMappingTable).where(MemoryNodeMappingTable.node_id == node_id)
        )
        return [mapping_to_domain(r) for r in result.scalars().all()]


class SQLGraphRepository(IGraphRepository):
    """SQLAlchemy aggregated root repository wrapper with traversal method stubs."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._entities = SQLEntityRepository(session)
        self._relationships = SQLRelationshipRepository(session)
        self._mappings = SQLMemoryNodeMappingRepository(session)

    @property
    def entities(self) -> IEntityRepository:
        return self._entities

    @property
    def relationships(self) -> IRelationshipRepository:
        return self._relationships

    @property
    def mappings(self) -> IMemoryNodeMappingRepository:
        return self._mappings

    # --- Placeholder Implementations for Neighborhood / Traversal (Phase 4) ---

    async def get_neighbors(
        self,
        node_id: uuid.UUID,
        relationship_types: Optional[List[RelationshipType]] = None,
    ) -> List[Tuple[Node, Relationship, Node]]:
        return []

    async def find_paths(
        self,
        source_node_id: uuid.UUID,
        target_node_id: uuid.UUID,
        max_depth: int = 3,
    ) -> List[List[Relationship]]:
        return []
