import abc
import uuid
from typing import Optional, List, Tuple
from datetime import datetime

from app.knowledge_graph.domain.entities import Node, Relationship, MemoryNodeMapping, EntityType, RelationshipType


class IEntityRepository(abc.ABC):
    """Domain interface managing Node records of type ENTITY."""

    @abc.abstractmethod
    async def get_by_id(self, entity_id: uuid.UUID) -> Optional[Node]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def get_by_name(self, user_id: uuid.UUID, canonical_name: str) -> Optional[Node]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def create(self, entity: Node) -> Node:
        raise NotImplementedError()

    @abc.abstractmethod
    async def update(self, entity: Node) -> Node:
        raise NotImplementedError()

    @abc.abstractmethod
    async def delete(self, entity_id: uuid.UUID) -> bool:
        raise NotImplementedError()

    @abc.abstractmethod
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
        raise NotImplementedError()


class IRelationshipRepository(abc.ABC):
    """Domain interface managing Relationship directed edges."""

    @abc.abstractmethod
    async def get_by_id(self, relationship_id: uuid.UUID) -> Optional[Relationship]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def get_by_endpoints(
        self,
        user_id: uuid.UUID,
        source_node_id: uuid.UUID,
        target_node_id: uuid.UUID,
        relationship_type: RelationshipType,
    ) -> Optional[Relationship]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def create(self, relationship: Relationship) -> Relationship:
        raise NotImplementedError()

    @abc.abstractmethod
    async def update(self, relationship: Relationship) -> Relationship:
        raise NotImplementedError()

    @abc.abstractmethod
    async def delete(self, relationship_id: uuid.UUID) -> bool:
        raise NotImplementedError()

    @abc.abstractmethod
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
        raise NotImplementedError()


class IMemoryNodeMappingRepository(abc.ABC):
    """Domain interface mapping memories to nodes."""

    @abc.abstractmethod
    async def create(self, mapping: MemoryNodeMapping) -> MemoryNodeMapping:
        raise NotImplementedError()

    @abc.abstractmethod
    async def delete(self, memory_id: uuid.UUID, node_id: uuid.UUID) -> bool:
        raise NotImplementedError()

    @abc.abstractmethod
    async def get_by_ids(self, memory_id: uuid.UUID, node_id: uuid.UUID) -> Optional[MemoryNodeMapping]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def list_by_memory(self, memory_id: uuid.UUID) -> List[MemoryNodeMapping]:
        raise NotImplementedError()

    @abc.abstractmethod
    async def list_by_node(self, node_id: uuid.UUID) -> List[MemoryNodeMapping]:
        raise NotImplementedError()


class IGraphRepository(abc.ABC):
    """
    Domain repository aggregator contract serving as the core layout
    for graph operations, traversals, and expansion routines.
    """

    @property
    @abc.abstractmethod
    def entities(self) -> IEntityRepository:
        raise NotImplementedError()

    @property
    @abc.abstractmethod
    def relationships(self) -> IRelationshipRepository:
        raise NotImplementedError()

    @property
    @abc.abstractmethod
    def mappings(self) -> IMemoryNodeMappingRepository:
        raise NotImplementedError()

    # --- Future Graph Traversal Extension Hooks (Phase 4) ---

    @abc.abstractmethod
    async def get_neighbors(
        self,
        node_id: uuid.UUID,
        relationship_types: Optional[List[RelationshipType]] = None,
    ) -> List[Tuple[Node, Relationship, Node]]:
        """Placeholder for neighborhood discovery and multi-hop node adjacency list fetches."""
        raise NotImplementedError()

    @abc.abstractmethod
    async def find_paths(
        self,
        source_node_id: uuid.UUID,
        target_node_id: uuid.UUID,
        max_depth: int = 3,
    ) -> List[List[Relationship]]:
        """Placeholder logic tracing semantic path routes connecting nodes."""
        raise NotImplementedError()
