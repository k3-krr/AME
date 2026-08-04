# Knowledge Graph Subsystem Architecture & Integration Manual

This document provides a comprehensive overview of the design, extraction pipelines, traversal engines, retrieval composition, and API interfaces for the **Knowledge Graph Subsystem** (Milestone 8) in the **Adaptive Memory Engine (AME)**.

---

## 1. Subsystem Architecture Overview

The Knowledge Graph subsystem is designed under a decoupled, layered **Domain-Driven Design (DDD-Lite)** pattern. It separates core graph traversal logic from persistent database technologies and API presentation boundaries.

```
       +---------------------------------------------+
       |               Presentation                  |
       |         (FastAPI Routers & Schemas)         |
       +----------------------+----------------------+
                              |
                              v
       +----------------------+----------------------+
       |                Application                  |
       |  (MemoryGraphOrchestrator, Service Layer)   |
       +-------+--------------+---------------+------+
               |              |               |
               v              v               v
  +------------+---+  +-------+------+  +-----+------+
  |     Domain     |  |    Domain    |  |Infrastructure|
  | TraversalService| | EntityService |  |Repositories  |
  |  (Interface)   |  | (Interface)  |  | (SQLAlchemy) |
  +------+---------+  +-------+------+  +-----+------+
         |                    |               |
         v                    v               v
  +------------+---+  +-------+------+  +-----+------+
  | InMemoryGraph  |  |   Graph      |  | PostgreSQL  |
  | (BFS/DFS/Dijk) |  | Extraction   |  |  SQLite     |
  +----------------+  +--------------+  +------------+
```

### Multi-Tenant Isolation
Every node, relationship, and memory mapping is bound to a specific `user_id`. Security checks are enforced at:
1. **API Controller Entry**: Authenticates request cookies, mapping them to the active user context.
2. **Service Layer Resolution**: Rejects inputs referring to IDs not owned by the active tenant context.
3. **In-Memory Graphs**: Local subgraphs are dynamically loaded using user-scoped queries, ensuring zero memory leak across active tenant structures.

---

## 2. Entity & Relationship Extraction Pipeline

AME extracts concepts and constructs relationships dynamically as conversation turns are processed.

```
Conversation Turn
       │
       ▼
Memory Extraction (Consolidates dialogue text into Memory Table)
       │
       ▼
Entity Extraction (Parses entities and canonicalizes names: e.g., postgres -> postgresql)
       │
       ▼
Memory-Node Mapping (Links memory UUID to resolved entity node UUID)
       │
       ▼
Relationship Extraction (Identifies predicate links between extracted entities)
```

### 2.1 Entity Extraction (`EntityExtractionService`)
1. **Parsing**: Scrapes text to extract concepts and maps them to standard classifications (`PERSON`, `PROJECT`, `TECHNOLOGY`, etc.).
2. **Canonicalization**: Enforces strict normalization (stripping, converting to lowercase, resolving common aliases like `postgres` $\rightarrow$ `postgresql` and `js` $\rightarrow$ `javascript`).
3. **Mapping**: Inserts node records and creates cross-reference entries in `kg_memory_node_mappings`.

### 2.2 Relationship Extraction (`RelationshipExtractionService`)
1. **Triple Generation**: Runs pattern matching over the content to detect predicates between co-occurring entities mapped to the same memory.
2. **Self-Loop Prevention**: Rejects self-referential relations (where source node ID matches target node ID).
3. **Persistence**: Creates user-isolated directed relationship records in `kg_relationships`.

---

## 3. Graph Traversal Engine

To guarantee sub-millisecond execution times, traversal operations load scoped subgraphs into an in-memory adjacency index (`InMemoryGraph`) before traversing:

*   **Breadth-First Search (BFS)**: Explores adjacent neighbor nodes first. Used for query context expansions and density maps.
*   **Depth-First Search (DFS)**: Traverses deep path branches before backtracking. Used for finding far relationships.
*   **Dijkstra's Shortest Path**: Finds the lowest-weight connection path between two nodes using a weighted priority queue.

### Path Explainability
BFS and DFS traversals return a list of path nodes traversed from the origin:
*   Returns: `{"node": Node, "depth": int, "path": [node_ids_in_path]}`
*   Enforces early-exit conditions: `MAX_DEPTH` (depth limit reached), `TARGET_FOUND` (destination node discovered), and `FILTER_EXHAUSTED` (candidates filtered out).

---

## 4. Graph-Aware Query Expansion (`GraphAwareHybridRetrievalService`)

The query expansion pipeline augments standard vector similarity search by traversing connected concept graphs:

```
1. Fetch base memories from hybrid systems (Semantic, Episodic, Working, Procedural)
       │
       ▼
2. Batch-resolve memories to graph node mappings (list_by_memories query)
       │
       ▼
3. Run BFS/DFS traversal to extract connected entities
       │
       ▼
4. Batch-load memories linked to traversed entities (list_by_nodes query)
       │
       ▼
5. Merge baseline and expanded memories with decay weights
       │
       ▼
6. Record detailed traversal path context in retrieval metadata
```

### Path Decay Scoring Heuristic
Expanded memories are weighted based on path distance and confidence levels:
$$\text{graph\_score} = \text{origin\_mapping.confidence} \times (\text{GRAPH\_EXPANSION\_DECAY}^{\text{depth}}) \times \text{target\_mapping.confidence}$$

### Provenance Tracking
Metadata preserves how each memory was retrieved:
*   `memory.metadata["retrieval_sources"]`: e.g. `["semantic", "graph_expansion"]`
*   `memory.metadata["graph_provenance"]`: Records details of the traversal path (`origin_memory_id`, `origin_node_id`, `traversal_depth`, `path_length`, `graph_score`, `path`).

---

## 5. API Reference & Swagger Specifications

### 5.1 Entities API (`/api/v1/entities`)
*   `POST /entities`: Creates a new entity node.
    - Input: `EntityCreateRequest` (name, entity_type, metadata).
*   `GET /entities`: Paginated list of entities filtered by type/canonical name.
*   `GET /entities/{entity_id}`: Retrieves entity details.
*   `PUT /entities/{entity_id}`: Updates entity details.
*   `DELETE /entities/{entity_id}`: Hard-deletes node and cascades to relationships.
*   `POST /memories/{memory_id}/entities/extract`: Manually triggers entity extraction.

### 5.2 Relationships API (`/api/v1/relationships`)
*   `POST /relationships`: Creates a directed relationship edge.
    - Input: `RelationshipCreateRequest` (source, target, type, confidence, metadata).
*   `GET /relationships`: Lists relations filtered by endpoints or type.
*   `DELETE /relationships/{relationship_id}`: Deletes relationship edge.
*   `POST /memories/{memory_id}/relationships/extract`: Manually triggers relationship extraction.

### 5.3 Traversal API (`/api/v1/graph`)
*   `GET /graph/nodes/{node_id}/neighbors`: Returns direct adjacent nodes.
*   `GET /graph/nodes/{node_id}/connected`: Returns memories mapped to nodes up to `max_depth`.
*   `GET /graph/path`: Shortest path connecting two nodes using Dijkstra's algorithm.
*   `GET /graph/traverse`: Runs BFS graph traversal from a start node.

---

## 6. Operational Configuration Options

Fine-tune retrieval and graph configurations inside `.env` or [config.py](file:///c:/AME/backend/app/config.py):
*   `GRAPH_MAX_TRAVERSAL_DEPTH` (default `5`): Maximum allowed depth limit for traversal query inputs.
*   `GRAPH_EXPANSION_ENABLED` (default `True`): Toggles graph context injection.
*   `GRAPH_EXPANSION_MAX_DEPTH` (default `2`): Traversal hop limit for expansion search.
*   `GRAPH_EXPANSION_MAX_MEMORIES` (default `50`): Cap on total graph memories injected.
*   `GRAPH_EXPANSION_MAX_NODES` (default `20`): Limits traversed nodes to prevent latency spikes.
*   `GRAPH_EXPANSION_DECAY` (default `0.9`): Penalty rate applied per hop.
*   `GRAPH_EXPANSION_STRATEGY` (default `BFS`): Graph exploration algorithm choice (`BFS` or `DFS`).
