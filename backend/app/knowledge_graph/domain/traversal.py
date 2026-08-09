import abc
import uuid
from enum import Enum
from typing import List, Dict, Any, Optional

from app.knowledge_graph.domain.entities import RelationshipType, NodeType, EntityType
from app.domain.entities import AccessContext


class TraversalStrategy(str, Enum):
    BREADTH_FIRST_SEARCH = "BFS"
    DEPTH_FIRST_SEARCH = "DFS"
    DIJKSTRA = "DIJKSTRA"
    RANDOM_WALK = "RANDOM_WALK"


class ITraversalCacheProvider(abc.ABC):
    """Extension point interface for graph traversal caching."""
    pass


class IGraphTraversalService(abc.ABC):
    """Domain interface establishing graph network pathing/traversal."""

    @abc.abstractmethod
    async def traverse(
        self,
        user_id: uuid.UUID,
        start_node_id: uuid.UUID,
        max_depth: int = 3,
        direction: str = "both",
        relationship_types: Optional[List[RelationshipType]] = None,
        node_types: Optional[List[NodeType]] = None,
        entity_types: Optional[List[EntityType]] = None,
        confidence_threshold: Optional[float] = None,
        access_context: Optional[AccessContext] = None,
    ) -> Dict[str, Any]:
        """Traverses the graph from a starting node, returning visited nodes and metadata."""
        raise NotImplementedError()

    @abc.abstractmethod
    async def find_shortest_path(
        self,
        user_id: uuid.UUID,
        source_node_id: uuid.UUID,
        target_node_id: uuid.UUID,
        direction: str = "both",
        relationship_types: Optional[List[RelationshipType]] = None,
        node_types: Optional[List[NodeType]] = None,
        entity_types: Optional[List[EntityType]] = None,
        confidence_threshold: Optional[float] = None,
        access_context: Optional[AccessContext] = None,
    ) -> Optional[Dict[str, Any]]:
        """Discovers the shortest path link chain connecting two node structures."""
        raise NotImplementedError()

