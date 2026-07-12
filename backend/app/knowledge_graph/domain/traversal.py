import abc
import uuid
from enum import Enum
from typing import List, Dict, Any, Protocol


class TraversalStrategy(str, Enum):
    BREADTH_FIRST_SEARCH = "BFS"
    DEPTH_FIRST_SEARCH = "DFS"
    DIJKSTRA = "DIJKSTRA"
    RANDOM_WALK = "RANDOM_WALK"


class GraphTraversalProtocol(Protocol):
    """Protocol establishing execution contract for graph network pathing/traversal."""

    async def traverse(
        self,
        start_node_id: uuid.UUID,
        strategy: TraversalStrategy,
        max_depth: int = 3,
        relationship_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Traverses the graph from a starting node based on specified search strategy."""
        ...

    async def find_shortest_path(
        self,
        source_node_id: uuid.UUID,
        target_node_id: uuid.UUID,
    ) -> List[uuid.UUID]:
        """Discovers the shortest path link chain connecting two node structures."""
        ...
