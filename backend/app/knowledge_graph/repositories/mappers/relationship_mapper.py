from app.knowledge_graph.domain.entities import Relationship, RelationshipType, MemoryNodeMapping
from app.knowledge_graph.models.models import RelationshipTable, MemoryNodeMappingTable


def relationship_to_domain(table: RelationshipTable) -> Relationship:
    """Translates database RelationshipTable representation to domain Relationship representation."""
    return Relationship(
        id=table.id,
        user_id=table.user_id,
        source_node_id=table.source_node_id,
        target_node_id=table.target_node_id,
        relationship_type=RelationshipType(table.relationship_type),
        confidence=table.confidence,
        metadata=table.metadata_dict or {},
        created_at=table.created_at,
    )


def relationship_to_table(domain: Relationship) -> RelationshipTable:
    """Translates domain Relationship representation to database RelationshipTable representation."""
    return RelationshipTable(
        id=domain.id,
        user_id=domain.user_id,
        source_node_id=domain.source_node_id,
        target_node_id=domain.target_node_id,
        relationship_type=domain.relationship_type.value,
        confidence=domain.confidence,
        metadata_dict=domain.metadata or {},
        created_at=domain.created_at,
    )


def mapping_to_domain(table: MemoryNodeMappingTable) -> MemoryNodeMapping:
    """Translates database MemoryNodeMappingTable representation to domain MemoryNodeMapping representation."""
    return MemoryNodeMapping(
        memory_id=table.memory_id,
        node_id=table.node_id,
        confidence=table.confidence,
        created_at=table.created_at,
    )


def mapping_to_table(domain: MemoryNodeMapping) -> MemoryNodeMappingTable:
    """Translates domain MemoryNodeMapping representation to database MemoryNodeMappingTable representation."""
    return MemoryNodeMappingTable(
        memory_id=domain.memory_id,
        node_id=domain.node_id,
        confidence=domain.confidence,
        created_at=domain.created_at,
    )
