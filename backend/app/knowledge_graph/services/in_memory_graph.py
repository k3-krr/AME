import heapq
import uuid
from typing import List, Dict, Any, Tuple, Optional, Set

from app.knowledge_graph.domain.entities import Node, Relationship, RelationshipType, NodeType, EntityType


class InMemoryGraph:
    """
    Optimized in-memory graph representation of a user's knowledge graph.
    Designed for fast query-level traversal, Dijkstra pathfinding, and BFS/DFS strategies
    without triggering database round trips.
    """

    def __init__(self, nodes: List[Node], relationships: List[Relationship]):
        self.nodes_by_id = {node.id: node for node in nodes}
        # Adjacency lists store tuples of: (relationship, neighbor_node, weight)
        self.adjacency_outgoing = {node.id: [] for node in nodes}
        self.adjacency_incoming = {node.id: [] for node in nodes}

        for rel in relationships:
            src_id = rel.source_node_id
            tgt_id = rel.target_node_id
            if src_id in self.nodes_by_id and tgt_id in self.nodes_by_id:
                src_node = self.nodes_by_id[src_id]
                tgt_node = self.nodes_by_id[tgt_id]
                # Default weight to 1.0 (easily maps to 1.0 - rel.confidence or similar in the future)
                weight = 1.0
                self.adjacency_outgoing[src_id].append((rel, tgt_node, weight))
                self.adjacency_incoming[tgt_id].append((rel, src_node, weight))

    def get_filtered_neighbors(
        self,
        node_id: uuid.UUID,
        direction: str = "both",
        relationship_types: Optional[List[RelationshipType]] = None,
        node_types: Optional[List[NodeType]] = None,
        entity_types: Optional[List[EntityType]] = None,
        confidence_threshold: Optional[float] = None,
    ) -> List[Tuple[Node, Relationship, Node, float]]:
        """
        Retrieves filtered neighbors of a node.
        Returns a sorted, deterministic list of (source_node, relationship, target_node, weight) tuples.
        """
        results = []
        node = self.nodes_by_id.get(node_id)
        if not node:
            return []

        # Outgoing connections
        if direction in ("outgoing", "both") and node_id in self.adjacency_outgoing:
            for rel, target, weight in self.adjacency_outgoing[node_id]:
                if relationship_types and rel.relationship_type not in relationship_types:
                    continue
                if node_types and target.node_type not in node_types:
                    continue
                if entity_types and target.entity_type not in entity_types:
                    continue
                if confidence_threshold is not None and rel.confidence < confidence_threshold:
                    continue
                results.append((node, rel, target, weight))

        # Incoming connections
        if direction in ("incoming", "both") and node_id in self.adjacency_incoming:
            for rel, source, weight in self.adjacency_incoming[node_id]:
                if relationship_types and rel.relationship_type not in relationship_types:
                    continue
                if node_types and source.node_type not in node_types:
                    continue
                if entity_types and source.entity_type not in entity_types:
                    continue
                if confidence_threshold is not None and rel.confidence < confidence_threshold:
                    continue
                results.append((source, rel, node, weight))

        # Sort neighbors alphabetically by source name, relation type, target name to ensure 100% deterministic traversal order
        results.sort(key=lambda x: (x[0].canonical_name, x[1].relationship_type.value, x[2].canonical_name))
        return results

    def bfs(
        self,
        start_node_id: uuid.UUID,
        max_depth: int = 3,
        direction: str = "both",
        relationship_types: Optional[List[RelationshipType]] = None,
        node_types: Optional[List[NodeType]] = None,
        entity_types: Optional[List[EntityType]] = None,
        confidence_threshold: Optional[float] = None,
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Runs Breadth-First Search from start_node_id.
        Returns: (visited_nodes_list, termination_reason)
        """
        if start_node_id not in self.nodes_by_id:
            return [], "NO_MORE_NEIGHBORS"

        visited = {start_node_id}
        queue = [(start_node_id, 0, [start_node_id])]  # (node_id, depth, path)
        result = []
        termination_reason = "NO_MORE_NEIGHBORS"

        # Check if start node has any potential neighbors before filtering
        raw_outgoing = len(self.adjacency_outgoing.get(start_node_id, []))
        raw_incoming = len(self.adjacency_incoming.get(start_node_id, []))
        if raw_outgoing + raw_incoming == 0:
            return [{"node": self.nodes_by_id[start_node_id], "depth": 0, "path": [start_node_id]}], "NO_MORE_NEIGHBORS"

        while queue:
            curr_id, depth, path = queue.pop(0)
            curr_node = self.nodes_by_id[curr_id]
            result.append({"node": curr_node, "depth": depth, "path": path})

            if depth >= max_depth:
                raw_neighbors = (
                    len(self.adjacency_outgoing.get(curr_id, [])) +
                    len(self.adjacency_incoming.get(curr_id, []))
                )
                if raw_neighbors > 0:
                    termination_reason = "MAX_DEPTH"
                continue

            neighbors = self.get_filtered_neighbors(
                node_id=curr_id,
                direction=direction,
                relationship_types=relationship_types,
                node_types=node_types,
                entity_types=entity_types,
                confidence_threshold=confidence_threshold,
            )

            # Check if all neighbors were exhausted/filtered
            raw_neighbors = (
                len(self.adjacency_outgoing.get(curr_id, [])) +
                len(self.adjacency_incoming.get(curr_id, []))
            )
            if raw_neighbors > 0 and len(neighbors) == 0:
                termination_reason = "FILTER_EXHAUSTED"

            for src, rel, tgt, weight in neighbors:
                neighbor_node = tgt if src.id == curr_id else src
                if neighbor_node.id not in visited:
                    visited.add(neighbor_node.id)
                    queue.append((neighbor_node.id, depth + 1, path + [neighbor_node.id]))

        return result, termination_reason

    def dfs(
        self,
        start_node_id: uuid.UUID,
        max_depth: int = 3,
        direction: str = "both",
        relationship_types: Optional[List[RelationshipType]] = None,
        node_types: Optional[List[NodeType]] = None,
        entity_types: Optional[List[EntityType]] = None,
        confidence_threshold: Optional[float] = None,
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Runs Depth-First Search from start_node_id.
        Returns: (visited_nodes_list, termination_reason)
        """
        if start_node_id not in self.nodes_by_id:
            return [], "NO_MORE_NEIGHBORS"

        visited = set()
        result = []
        termination_reason = "NO_MORE_NEIGHBORS"

        def _dfs_recurse(curr_id: uuid.UUID, depth: int, path: List[uuid.UUID]):
            nonlocal termination_reason
            if curr_id in visited:
                return

            visited.add(curr_id)
            curr_node = self.nodes_by_id[curr_id]
            result.append({"node": curr_node, "depth": depth, "path": path})

            if depth >= max_depth:
                raw_neighbors = (
                    len(self.adjacency_outgoing.get(curr_id, [])) +
                    len(self.adjacency_incoming.get(curr_id, []))
                )
                if raw_neighbors > 0:
                    termination_reason = "MAX_DEPTH"
                return

            neighbors = self.get_filtered_neighbors(
                node_id=curr_id,
                direction=direction,
                relationship_types=relationship_types,
                node_types=node_types,
                entity_types=entity_types,
                confidence_threshold=confidence_threshold,
            )

            raw_neighbors = (
                len(self.adjacency_outgoing.get(curr_id, [])) +
                len(self.adjacency_incoming.get(curr_id, []))
            )
            if raw_neighbors > 0 and len(neighbors) == 0:
                termination_reason = "FILTER_EXHAUSTED"

            for src, rel, tgt, weight in neighbors:
                neighbor_node = tgt if src.id == curr_id else src
                _dfs_recurse(neighbor_node.id, depth + 1, path + [neighbor_node.id])

        _dfs_recurse(start_node_id, 0, [start_node_id])
        return result, termination_reason

    def find_shortest_path(
        self,
        source_id: uuid.UUID,
        target_id: uuid.UUID,
        direction: str = "both",
        relationship_types: Optional[List[RelationshipType]] = None,
        node_types: Optional[List[NodeType]] = None,
        entity_types: Optional[List[EntityType]] = None,
        confidence_threshold: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Finds the shortest path from source_id to target_id using Dijkstra's algorithm.
        Supports weighted edges.
        Returns: {
            "nodes": List[Node],
            "relationships": List[Relationship],
            "hop_count": int,
            "termination_reason": str
        } or None if no path exists.
        """
        if source_id not in self.nodes_by_id or target_id not in self.nodes_by_id:
            return None

        if source_id == target_id:
            return {
                "nodes": [self.nodes_by_id[source_id]],
                "relationships": [],
                "hop_count": 0,
                "termination_reason": "TARGET_FOUND",
            }

        # Priority queue stores tuples of: (cumulative_weight, unique_counter, current_node_id, path_list)
        # where path_list contains tuples: (node_id, relationship_or_none)
        pq = []
        counter = 0
        heapq.heappush(pq, (0.0, counter, source_id, [(source_id, None)]))

        distances = {source_id: 0.0}

        while pq:
            dist, _, curr_id, path = heapq.heappop(pq)

            if curr_id == target_id:
                # Target found! Reconstruct
                path_nodes = []
                path_relationships = []
                for node_id, rel in path:
                    path_nodes.append(self.nodes_by_id[node_id])
                    if rel is not None:
                        path_relationships.append(rel)
                return {
                    "nodes": path_nodes,
                    "relationships": path_relationships,
                    "hop_count": len(path_relationships),
                    "termination_reason": "TARGET_FOUND",
                }

            if dist > distances.get(curr_id, float("inf")):
                continue

            neighbors = self.get_filtered_neighbors(
                node_id=curr_id,
                direction=direction,
                relationship_types=relationship_types,
                node_types=node_types,
                entity_types=entity_types,
                confidence_threshold=confidence_threshold,
            )

            for src, rel, tgt, weight in neighbors:
                neighbor_node = tgt if src.id == curr_id else src
                new_dist = dist + weight

                if new_dist < distances.get(neighbor_node.id, float("inf")):
                    distances[neighbor_node.id] = new_dist
                    new_path = list(path)
                    new_path.append((neighbor_node.id, rel))
                    counter += 1
                    heapq.heappush(pq, (new_dist, counter, neighbor_node.id, new_path))

        return None
