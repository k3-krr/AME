import uuid
import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass

from app.config import settings
from app.knowledge_graph.domain.entities import Node, Relationship, RelationshipType, NodeType, EntityType
from app.domain.entities import Memory, AccessContext
from app.knowledge_graph.repositories.sql_repositories import SQLGraphRepository

logger = logging.getLogger("ame_backend.knowledge_graph.expansion_service")


@dataclass
class GraphExpansionCandidate:
    memory_id: uuid.UUID
    origin_memory_id: uuid.UUID
    origin_node_id: uuid.UUID
    traversal_depth: int
    path_length: int
    graph_score: float
    path: List[uuid.UUID]


class KnowledgeGraphExpansionService:
    """
    Orchestrates Knowledge Graph query expansion.
    Given initial retrieved memories, it traverses the entity-relationship network
    and yields lightweight expansion candidates containing provenance metadata.
    """

    def __init__(self, graph_repo: SQLGraphRepository):
        self.graph_repo = graph_repo

    async def expand_memories(
        self,
        user_id: uuid.UUID,
        memories: List[Memory],
        max_depth: Optional[int] = None,
        max_nodes: Optional[int] = None,
        node_types: Optional[List[NodeType]] = None,
        relationship_types: Optional[List[RelationshipType]] = None,
        confidence_threshold: Optional[float] = None,
        access_context: Optional[AccessContext] = None,
    ) -> List[GraphExpansionCandidate]:
        """
        Accepts initial memories, traverses the graph, and yields expansion candidates.
        """
        if not settings.GRAPH_EXPANSION_ENABLED or not memories:
            return []

        # 1. Resolve parameters from settings
        depth_limit = max_depth if max_depth is not None else settings.GRAPH_EXPANSION_MAX_DEPTH
        nodes_limit = max_nodes if max_nodes is not None else settings.GRAPH_EXPANSION_MAX_NODES
        decay_factor = settings.GRAPH_EXPANSION_DECAY
        strategy = settings.GRAPH_EXPANSION_STRATEGY.upper()

        memory_ids = [m.id for m in memories]

        # 2. Batch load mapping relationships to avoid N+1 queries
        mappings = await self.graph_repo.mappings.list_by_memories(memory_ids)
        if not mappings:
            return []

        # Map memory_id -> list of node mappings
        mem_to_node_mappings: Dict[uuid.UUID, List[Any]] = {}
        for mapping in mappings:
            mem_to_node_mappings.setdefault(mapping.memory_id, []).append(mapping)

        # 3. Load entire graph for user context (optimizes traversals to be entirely in-memory)
        nodes = await self.graph_repo.entities.list_by_user(user_id, limit=100000)
        relationships = await self.graph_repo.relationships.list_by_user(user_id, limit=100000)

        from app.knowledge_graph.services.in_memory_graph import InMemoryGraph
        graph = InMemoryGraph(nodes, relationships)

        # De-duplicate starting node IDs to avoid multiple identical traversals
        starting_node_ids: Set[uuid.UUID] = {m.node_id for m in mappings if m.node_id in graph.nodes_by_id}
        if not starting_node_ids:
            return []

        # Maps target_node_id -> GraphExpansionCandidate (stores the best/highest scoring path link)
        best_candidates: Dict[uuid.UUID, GraphExpansionCandidate] = {}
        traversed_node_count = 0

        # Create mapping of node_id -> list of origin memory ID/confidence tuples
        node_origins: Dict[uuid.UUID, List[Tuple[uuid.UUID, float]]] = {}
        for memory_id, mappings_list in mem_to_node_mappings.items():
            for m in mappings_list:
                node_origins.setdefault(m.node_id, []).append((memory_id, m.confidence))

        # First pass: Run graph traversals and gather traversed node IDs
        traversals_run = []
        all_traversed_node_ids = set()

        for start_node_id in starting_node_ids:
            if traversed_node_count >= nodes_limit:
                break

            traversed_node_count += 1

            # Traverse the graph using the configured strategy
            if strategy == "DFS":
                traversed, _ = graph.dfs(
                    start_node_id=start_node_id,
                    max_depth=depth_limit,
                    node_types=node_types,
                    relationship_types=relationship_types,
                    confidence_threshold=confidence_threshold,
                )
            else:  # BFS
                traversed, _ = graph.bfs(
                    start_node_id=start_node_id,
                    max_depth=depth_limit,
                    node_types=node_types,
                    relationship_types=relationship_types,
                    confidence_threshold=confidence_threshold,
                )

            # Resolve original memory context for this start node
            origins = node_origins.get(start_node_id, [])
            if not origins:
                continue
            origin_memory_id, origin_mapping_conf = origins[0]  # Take first mapped origin memory
            
            traversals_run.append((origin_memory_id, origin_mapping_conf, start_node_id, traversed))
            for item in traversed:
                all_traversed_node_ids.add(item["node"].id)

        # Batch load mappings for all unique traversed target nodes (both all and authorized mappings)
        node_mappings_map: Dict[uuid.UUID, List[MemoryNodeMapping]] = {}
        unauthorized_node_ids = set()
        if all_traversed_node_ids:
            all_mappings = await self.graph_repo.mappings.list_by_nodes(list(all_traversed_node_ids))
            
            if access_context:
                auth_mappings = await self.graph_repo.mappings.list_by_nodes(list(all_traversed_node_ids), access_context=access_context)
            else:
                auth_mappings = all_mappings
                
            auth_memory_ids = {m.memory_id for m in auth_mappings}
            
            # Map node_id -> set of mapped memory_ids from all_mappings
            node_to_memories: Dict[uuid.UUID, Set[uuid.UUID]] = {}
            for m in all_mappings:
                node_to_memories.setdefault(m.node_id, set()).add(m.memory_id)
                
            # Compile unauthorized node IDs: mapped memories exist, but NONE of them are authorized
            for node_id, mapped_mids in node_to_memories.items():
                if mapped_mids and not (mapped_mids & auth_memory_ids):
                    unauthorized_node_ids.add(node_id)
                    
            # Populate node_mappings_map ONLY with authorized mappings so candidates are only created for authorized memories
            for mapping in auth_mappings:
                node_mappings_map.setdefault(mapping.node_id, []).append(mapping)


        # Second pass: Process traversal items and populate candidates using pre-fetched mappings in-memory
        for origin_memory_id, origin_mapping_conf, start_node_id, traversed in traversals_run:
            for item in traversed:
                target_node = item["node"]
                t_depth = item["depth"]
                path_node_ids = item["path"]

                # Prune if any node in the traversal path is unauthorized
                if access_context and any(nid in unauthorized_node_ids for nid in path_node_ids):
                    continue

                # Calculate graph path score with configurable decay
                graph_score = origin_mapping_conf * (decay_factor ** t_depth)

                # Skip starting node itself
                if target_node.id == start_node_id:
                    continue

                # If this target node is reached with a higher score, update/insert candidate
                if target_node.id not in best_candidates or graph_score > best_candidates[target_node.id].graph_score:
                    # Resolve node mappings from pre-fetched map (No database query!)
                    node_mappings = node_mappings_map.get(target_node.id, [])
                    for target_mapping in node_mappings:
                        # Skip if it maps back to the origin memory ID
                        if target_mapping.memory_id == origin_memory_id:
                            continue

                        # Combined final candidate score
                        final_score = graph_score * target_mapping.confidence

                        candidate = GraphExpansionCandidate(
                            memory_id=target_mapping.memory_id,
                            origin_memory_id=origin_memory_id,
                            origin_node_id=start_node_id,
                            traversal_depth=t_depth,
                            path_length=len(path_node_ids) - 1,
                            graph_score=final_score,
                            path=path_node_ids,
                        )

                        if target_mapping.memory_id not in best_candidates or final_score > best_candidates[target_mapping.memory_id].graph_score:
                            best_candidates[target_mapping.memory_id] = candidate

        # Return sorted candidates descending by score
        sorted_candidates = list(best_candidates.values())
        sorted_candidates.sort(key=lambda x: -x.graph_score)
        return sorted_candidates

