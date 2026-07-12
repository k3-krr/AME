import uuid
from typing import Optional, List

from app.knowledge_graph.domain.entities import MemoryNodeMapping
from app.knowledge_graph.domain.repositories import IGraphRepository, IEntityRepository
from app.domain.repositories import IMemoryRepository
from app.knowledge_graph.services.entity_service import EntityService
from app.knowledge_graph.services.relationship_service import RelationshipService
from app.knowledge_graph.exceptions import EntityNotFoundError


class GraphService:
    """
    Central orchestration service for the Knowledge Graph.
    Delegates node and edge CRUD to EntityService and RelationshipService,
    and manages memory-node mapping boundaries.
    """

    def __init__(
        self,
        graph_repo: IGraphRepository,
        memory_repo: IMemoryRepository,
        entity_service: EntityService,
        relationship_service: RelationshipService,
    ):
        self.graph_repo = graph_repo
        self.memory_repo = memory_repo
        self.entities = entity_service
        self.relationships = relationship_service

    async def create_memory_node_mapping(
        self,
        user_id: uuid.UUID,
        memory_id: uuid.UUID,
        node_id: uuid.UUID,
        confidence: float = 1.0,
    ) -> MemoryNodeMapping:
        """Links a Memory record to a Knowledge Graph Node after validation."""
        if not (0.0 <= confidence <= 1.0):
            raise ValueError("Confidence must be between 0.0 and 1.0 inclusive")

        # 1. Enforce memory existence and user ownership
        memory = await self.memory_repo.get_by_id(memory_id)
        if not memory or memory.user_id != user_id:
            raise KeyError(f"Memory with ID {memory_id} not found.")

        # 2. Enforce node existence and user ownership
        node = await self.graph_repo.entities.get_by_id(node_id)
        if not node or node.user_id != user_id:
            raise EntityNotFoundError(f"Node with ID {node_id} not found.")

        # 3. Check for existing mapping to prevent duplication
        existing = await self.graph_repo.mappings.get_by_ids(memory_id, node_id)
        if existing:
            return existing

        mapping = MemoryNodeMapping(
            memory_id=memory_id,
            node_id=node_id,
            confidence=confidence,
        )
        mapping.validate()
        return await self.graph_repo.mappings.create(mapping)

    async def delete_memory_node_mapping(
        self,
        user_id: uuid.UUID,
        memory_id: uuid.UUID,
        node_id: uuid.UUID,
    ) -> bool:
        """Deletes an association link mapping between a memory and a node."""
        # 1. Enforce memory validation
        memory = await self.memory_repo.get_by_id(memory_id)
        if not memory or memory.user_id != user_id:
            raise KeyError(f"Memory with ID {memory_id} not found.")

        # 2. Enforce node validation
        node = await self.graph_repo.entities.get_by_id(node_id)
        if not node or node.user_id != user_id:
            raise EntityNotFoundError(f"Node with ID {node_id} not found.")

        return await self.graph_repo.mappings.delete(memory_id, node_id)

    async def list_mappings_by_memory(
        self,
        user_id: uuid.UUID,
        memory_id: uuid.UUID,
    ) -> List[MemoryNodeMapping]:
        """Lists all nodes linked to a specific memory, validating memory ownership."""
        memory = await self.memory_repo.get_by_id(memory_id)
        if not memory or memory.user_id != user_id:
            raise KeyError(f"Memory with ID {memory_id} not found.")

        return await self.graph_repo.mappings.list_by_memory(memory_id)

    async def list_mappings_by_node(
        self,
        user_id: uuid.UUID,
        node_id: uuid.UUID,
    ) -> List[MemoryNodeMapping]:
        """Lists all memories linked to a specific node, validating node ownership."""
        node = await self.graph_repo.entities.get_by_id(node_id)
        if not node or node.user_id != user_id:
            raise EntityNotFoundError(f"Node with ID {node_id} not found.")

        return await self.graph_repo.mappings.list_by_node(node_id)
