import time
import uuid
import logging
from typing import List, Dict, Any, Optional, Tuple

from app.config import settings
from app.knowledge_graph.domain.entities import Node, Relationship, RelationshipType, NodeType, EntityType
from app.knowledge_graph.domain.traversal import IGraphTraversalService, TraversalStrategy, ITraversalCacheProvider
from app.knowledge_graph.repositories.sql_repositories import SQLGraphRepository
from app.domain.entities import AccessContext

logger = logging.getLogger("ame_backend.graph_traversal_service")


class GraphTraversalService(IGraphTraversalService):
    """
    Coordinates multi-tenant Knowledge Graph traversal, neighborhood navigation,
    shortest path pathfinding, and memory mapping discovery.
    """

    def __init__(
        self,
        graph_repo: SQLGraphRepository,
        cache_provider: Optional[ITraversalCacheProvider] = None,
    ):
        self.graph_repo = graph_repo
        self.cache_provider = cache_provider  # Traversal caching extension point stub

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
        """
        Traverses nodes starting at start_node_id using BFS.
        Enforces GRAPH_MAX_TRAVERSAL_DEPTH boundaries.
        """
        start_time = time.perf_counter()

        tenant_id = access_context.tenant_id if access_context else user_id

        # 1. Validate starting node exists and belongs to the user/tenant boundary
        start_node = await self.graph_repo.entities.get_by_id(start_node_id)
        if not start_node or start_node.user_id != tenant_id:
            raise ValueError(f"Node with ID {start_node_id} not found.")

        # 2. Validate parameters
        if max_depth < 0:
            raise ValueError("Traversal depth must be greater than or equal to 0.")
        
        limit_depth = settings.GRAPH_MAX_TRAVERSAL_DEPTH
        if max_depth > limit_depth:
            raise ValueError(f"Traversal depth cannot exceed the configured limit of {limit_depth}.")

        if direction not in ("incoming", "outgoing", "both"):
            raise ValueError("Direction must be 'incoming', 'outgoing', or 'both'.")

        # 3. Load graph components for the user context
        nodes = await self.graph_repo.entities.list_by_user(tenant_id, limit=100000)
        relationships = await self.graph_repo.relationships.list_by_user(tenant_id, limit=100000)

        from app.knowledge_graph.services.in_memory_graph import InMemoryGraph
        graph = InMemoryGraph(nodes, relationships)

        # 4. Execute BFS traversal internally (encapsulating algorithm choice)
        traversed, termination_reason = graph.bfs(
            start_node_id=start_node_id,
            max_depth=max_depth,
            direction=direction,
            relationship_types=relationship_types,
            node_types=node_types,
            entity_types=entity_types,
            confidence_threshold=confidence_threshold,
        )

        # 5. Apply authorization path pruning
        visited_node_ids = {item["node"].id for item in traversed}
        unauthorized_node_ids = set()
        if visited_node_ids:
            all_mappings = await self.graph_repo.mappings.list_by_nodes(list(visited_node_ids))
            if access_context:
                auth_mappings = await self.graph_repo.mappings.list_by_nodes(list(visited_node_ids), access_context=access_context)
            else:
                auth_mappings = all_mappings
            auth_memory_ids = {m.memory_id for m in auth_mappings}

            node_to_memories: Dict[uuid.UUID, Set[uuid.UUID]] = {}
            for m in all_mappings:
                node_to_memories.setdefault(m.node_id, set()).add(m.memory_id)

            if access_context:
                for node_id, mapped_mids in node_to_memories.items():
                    if mapped_mids and not (mapped_mids & auth_memory_ids):
                        unauthorized_node_ids.add(node_id)

            # Debug prints
            print("DEBUG TRAVERSE:")
            print("Traversed before prune:", [(item["node"].name, [graph.nodes_by_id[nid].name for nid in item["path"]]) for item in traversed])
            print("Unauthorized node ids:", [graph.nodes_by_id[nid].name for nid in unauthorized_node_ids if nid in graph.nodes_by_id])

            # Prune paths containing unauthorized nodes
            traversed = [item for item in traversed if not (access_context and any(nid in unauthorized_node_ids for nid in item["path"]))]

        execution_time = (time.perf_counter() - start_time) * 1000.0

        # Calculate visited counts for traversal metadata
        visited_node_ids = {item["node"].id for item in traversed}
        visited_rels = set()
        for rel in relationships:
            if rel.source_node_id in visited_node_ids and rel.target_node_id in visited_node_ids:
                if not (access_context and (rel.source_node_id in unauthorized_node_ids or rel.target_node_id in unauthorized_node_ids)):
                    visited_rels.add(rel.id)

        max_depth_reached = max([item["depth"] for item in traversed], default=0)

        metadata = {
            "traversal_strategy": TraversalStrategy.BREADTH_FIRST_SEARCH.value,
            "max_depth": max_depth,
            "traversal_depth": max_depth_reached,
            "visited_node_count": len(visited_node_ids),
            "visited_relationship_count": len(visited_rels),
            "execution_time_ms": round(execution_time, 2),
            "termination_reason": termination_reason,
        }

        return {
            "nodes": traversed,
            "metadata": metadata,
        }

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
        """
        Discovers the shortest path between source and target using Dijkstra's algorithm.
        Enforces user ownership constraints.
        """
        start_time = time.perf_counter()

        tenant_id = access_context.tenant_id if access_context else user_id

        # 1. Validate endpoints
        source = await self.graph_repo.entities.get_by_id(source_node_id)
        if not source or source.user_id != tenant_id:
            raise ValueError(f"Source node with ID {source_node_id} not found.")

        target = await self.graph_repo.entities.get_by_id(target_node_id)
        if not target or target.user_id != tenant_id:
            raise ValueError(f"Target node with ID {target_node_id} not found.")

        # 2. Load graph components for the user context
        nodes = await self.graph_repo.entities.list_by_user(tenant_id, limit=100000)
        relationships = await self.graph_repo.relationships.list_by_user(tenant_id, limit=100000)

        from app.knowledge_graph.services.in_memory_graph import InMemoryGraph
        graph = InMemoryGraph(nodes, relationships)

        # 3. Execute Dijkstra pathfinder
        path_result = graph.find_shortest_path(
            source_id=source_node_id,
            target_id=target_node_id,
            direction=direction,
            relationship_types=relationship_types,
            node_types=node_types,
            entity_types=entity_types,
            confidence_threshold=confidence_threshold,
        )

        execution_time = (time.perf_counter() - start_time) * 1000.0

        if not path_result:
            return None

        # 4. Check path authorization
        path_node_ids = [n.id for n in path_result["nodes"]]
        if path_node_ids:
            all_mappings = await self.graph_repo.mappings.list_by_nodes(path_node_ids)
            if access_context:
                auth_mappings = await self.graph_repo.mappings.list_by_nodes(path_node_ids, access_context=access_context)
            else:
                auth_mappings = all_mappings
            auth_memory_ids = {m.memory_id for m in auth_mappings}

            node_to_memories: Dict[uuid.UUID, Set[uuid.UUID]] = {}
            for m in all_mappings:
                node_to_memories.setdefault(m.node_id, set()).add(m.memory_id)

            unauthorized_node_ids = set()
            if access_context:
                for node_id, mapped_mids in node_to_memories.items():
                    if mapped_mids and not (mapped_mids & auth_memory_ids):
                        unauthorized_node_ids.add(node_id)

            # If any node in path is unauthorized, discard the path
            if access_context and any(nid in unauthorized_node_ids for nid in path_node_ids):
                return None

        metadata = {
            "traversal_strategy": TraversalStrategy.DIJKSTRA.value,
            "max_depth": settings.GRAPH_MAX_TRAVERSAL_DEPTH,
            "traversal_depth": path_result["hop_count"],
            "visited_node_count": len(path_result["nodes"]),
            "visited_relationship_count": len(path_result["relationships"]),
            "path_length": path_result["hop_count"],
            "execution_time_ms": round(execution_time, 2),
            "termination_reason": path_result["termination_reason"],
        }

        return {
            "nodes": path_result["nodes"],
            "relationships": path_result["relationships"],
            "hop_count": path_result["hop_count"],
            "metadata": metadata,
        }

    async def get_neighbors(
        self,
        user_id: uuid.UUID,
        node_id: uuid.UUID,
        direction: str = "both",
        relationship_types: Optional[List[RelationshipType]] = None,
        node_types: Optional[List[NodeType]] = None,
        entity_types: Optional[List[EntityType]] = None,
        confidence_threshold: Optional[float] = None,
        access_context: Optional[AccessContext] = None,
    ) -> List[Tuple[Node, Relationship, Node]]:
        """
        Retrieves neighbor entities joined to the source node,
        applying type and confidence threshold constraints.
        """
        tenant_id = access_context.tenant_id if access_context else user_id

        # Validate existence & ownership
        node = await self.graph_repo.entities.get_by_id(node_id)
        if not node or node.user_id != tenant_id:
            raise ValueError(f"Node with ID {node_id} not found.")

        # Call the optimized join query from repo
        neighbors = await self.graph_repo.get_neighbors(
            user_id=tenant_id,
            node_id=node_id,
            direction=direction,
            relationship_types=relationship_types,
        )

        neighbor_node_ids = {tgt.id if src.id == node_id else src.id for src, rel, tgt in neighbors}
        neighbor_node_ids.add(node_id)

        unauthorized_node_ids = set()
        if neighbor_node_ids:
            all_mappings = await self.graph_repo.mappings.list_by_nodes(list(neighbor_node_ids))
            if access_context:
                auth_mappings = await self.graph_repo.mappings.list_by_nodes(list(neighbor_node_ids), access_context=access_context)
            else:
                auth_mappings = all_mappings
            auth_memory_ids = {m.memory_id for m in auth_mappings}

            node_to_memories: Dict[uuid.UUID, Set[uuid.UUID]] = {}
            for m in all_mappings:
                node_to_memories.setdefault(m.node_id, set()).add(m.memory_id)

            if access_context:
                for nid, mapped_mids in node_to_memories.items():
                    if mapped_mids and not (mapped_mids & auth_memory_ids):
                        unauthorized_node_ids.add(nid)

        filtered = []
        for src, rel, tgt in neighbors:
            if access_context and (src.id in unauthorized_node_ids or tgt.id in unauthorized_node_ids):
                continue
            neighbor_node = tgt if src.id == node_id else src
            if node_types and neighbor_node.node_type not in node_types:
                continue
            if entity_types and neighbor_node.entity_type not in entity_types:
                continue
            if confidence_threshold is not None and rel.confidence < confidence_threshold:
                continue
            filtered.append((src, rel, tgt))
        return filtered

    async def get_connected_memories(
        self,
        user_id: uuid.UUID,
        node_id: uuid.UUID,
        max_depth: int = 0,
        direction: str = "both",
        relationship_types: Optional[List[RelationshipType]] = None,
        node_types: Optional[List[NodeType]] = None,
        entity_types: Optional[List[EntityType]] = None,
        confidence_threshold: Optional[float] = None,
        memory_repo: Optional[Any] = None,
        access_context: Optional[AccessContext] = None,
    ) -> List[Any]:
        """
        Finds de-duplicated memories mapped to node_id.
        Optionally traverses neighboring nodes up to max_depth to find memories.
        """
        tenant_id = access_context.tenant_id if access_context else user_id

        # Validate existence & ownership
        node = await self.graph_repo.entities.get_by_id(node_id)
        if not node or node.user_id != tenant_id:
            raise ValueError(f"Node with ID {node_id} not found.")

        # Traverse to collect reachable node IDs
        if max_depth > 0:
            traversal_res = await self.traverse(
                user_id=tenant_id,
                start_node_id=node_id,
                max_depth=max_depth,
                direction=direction,
                relationship_types=relationship_types,
                node_types=node_types,
                entity_types=entity_types,
                confidence_threshold=confidence_threshold,
                access_context=access_context,
            )
            node_ids = [n["node"].id for n in traversal_res["nodes"]]
        else:
            node_ids = [node_id]

        # Batch load mappings
        mappings = await self.graph_repo.mappings.list_by_nodes(node_ids, access_context=access_context)

        # De-duplicate memory IDs using a set
        memory_ids = list({m.memory_id for m in mappings})
        if not memory_ids or not memory_repo:
            return []

        # Batch fetch memories
        memories = await memory_repo.get_by_ids(memory_ids, access_context=access_context)

        seen_memory_ids = set()
        user_memories = []
        for memory in memories:
            if memory.user_id == tenant_id and memory.id not in seen_memory_ids:
                seen_memory_ids.add(memory.id)
                user_memories.append(memory)

        return user_memories
