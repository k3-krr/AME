from app.knowledge_graph.domain.entities import Node, NodeType, EntityType
from app.knowledge_graph.models.models import NodeTable


def to_domain(table: NodeTable) -> Node:
    """Translates database NodeTable representation into pure domain Node dataclass."""
    return Node(
        id=table.id,
        user_id=table.user_id,
        node_type=NodeType(table.node_type),
        name=table.name,
        canonical_name=table.canonical_name,
        entity_type=EntityType(table.entity_type) if table.entity_type else None,
        metadata=table.metadata_dict or {},
        created_at=table.created_at,
        updated_at=table.updated_at,
    )


def to_table(domain: Node) -> NodeTable:
    """Translates domain Node representation into database NodeTable representation."""
    return NodeTable(
        id=domain.id,
        user_id=domain.user_id,
        node_type=domain.node_type.value,
        name=domain.name,
        canonical_name=domain.canonical_name,
        entity_type=domain.entity_type.value if domain.entity_type else None,
        metadata_dict=domain.metadata or {},
        created_at=domain.created_at,
        updated_at=domain.updated_at,
    )
