import { request } from "./client";
import { 
  Entity, 
  Relationship, 
  Neighbor, 
  TraversalResponse, 
  PathResponse,
  EntityType,
  RelationshipType,
  Memory
} from "@/types";

export interface ListEntitiesParams {
  entity_type?: EntityType | "";
  canonical_name?: string;
  page?: number;
  limit?: number;
  sort_by?: "created_at" | "name";
  sort_order?: "asc" | "desc";
}

export interface CreateEntityPayload {
  name: string;
  canonical_name?: string | null;
  entity_type: EntityType;
  metadata?: Record<string, unknown> | null;
}

export interface UpdateEntityPayload {
  name?: string;
  canonical_name?: string | null;
  entity_type?: EntityType;
  metadata?: Record<string, unknown> | null;
}

export interface ListRelationshipsParams {
  source_entity_id?: string;
  target_entity_id?: string;
  relationship_type?: RelationshipType | "";
  page?: number;
  limit?: number;
  sort_by?: "created_at" | "confidence";
  sort_order?: "asc" | "desc";
}

export interface CreateRelationshipPayload {
  source_entity_id: string;
  target_entity_id: string;
  relationship_type: RelationshipType;
  confidence?: number;
  metadata?: Record<string, unknown> | null;
}

export interface TraversalParams {
  direction?: "incoming" | "outgoing" | "both";
  relationship_types?: string; // Comma separated list
  node_types?: string; // Comma separated list
  entity_types?: string; // Comma separated list
  confidence_threshold?: number;
}

export const knowledgeGraphApi = {
  // --- Entities ---
  async listEntities(params: ListEntitiesParams = {}): Promise<Entity[]> {
    const q = new URLSearchParams();
    if (params.entity_type) q.append("entity_type", params.entity_type);
    if (params.canonical_name) q.append("canonical_name", params.canonical_name);
    if (params.page !== undefined) q.append("page", String(params.page));
    if (params.limit !== undefined) q.append("limit", String(params.limit));
    if (params.sort_by) q.append("sort_by", params.sort_by);
    if (params.sort_order) q.append("sort_order", params.sort_order);

    const queryStr = q.toString() ? `?${q.toString()}` : "";
    return request<Entity[]>(`/entities${queryStr}`);
  },

  async getEntity(entityId: string): Promise<Entity> {
    return request<Entity>(`/entities/${entityId}`);
  },

  async createEntity(payload: CreateEntityPayload): Promise<Entity> {
    return request<Entity>("/entities", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async updateEntity(entityId: string, payload: UpdateEntityPayload): Promise<Entity> {
    return request<Entity>(`/entities/${entityId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },

  async deleteEntity(entityId: string): Promise<void> {
    return request<void>(`/entities/${entityId}`, {
      method: "DELETE",
    });
  },

  async extractEntitiesFromMemory(memoryId: string): Promise<Entity[]> {
    return request<Entity[]>(`/memories/${memoryId}/entities/extract`, {
      method: "POST",
    });
  },

  // --- Relationships ---
  async listRelationships(params: ListRelationshipsParams = {}): Promise<Relationship[]> {
    const q = new URLSearchParams();
    if (params.source_entity_id) q.append("source_entity_id", params.source_entity_id);
    if (params.target_entity_id) q.append("target_entity_id", params.target_entity_id);
    if (params.relationship_type) q.append("relationship_type", params.relationship_type);
    if (params.page !== undefined) q.append("page", String(params.page));
    if (params.limit !== undefined) q.append("limit", String(params.limit));
    if (params.sort_by) q.append("sort_by", params.sort_by);
    if (params.sort_order) q.append("sort_order", params.sort_order);

    const queryStr = q.toString() ? `?${q.toString()}` : "";
    return request<Relationship[]>(`/relationships${queryStr}`);
  },

  async createRelationship(payload: CreateRelationshipPayload): Promise<Relationship> {
    return request<Relationship>("/relationships", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async deleteRelationship(relationshipId: string): Promise<void> {
    return request<void>(`/relationships/${relationshipId}`, {
      method: "DELETE",
    });
  },

  async extractRelationshipsFromMemory(memoryId: string): Promise<Relationship[]> {
    return request<Relationship[]>(`/memories/${memoryId}/relationships/extract`, {
      method: "POST",
    });
  },

  // --- Traversal & Graph Neighborhoods ---
  async getNeighbors(nodeId: string, params: TraversalParams = {}): Promise<Neighbor[]> {
    const q = new URLSearchParams();
    if (params.direction) q.append("direction", params.direction);
    if (params.relationship_types) q.append("relationship_types", params.relationship_types);
    if (params.node_types) q.append("node_types", params.node_types);
    if (params.entity_types) q.append("entity_types", params.entity_types);
    if (params.confidence_threshold !== undefined) {
      q.append("confidence_threshold", String(params.confidence_threshold));
    }

    const queryStr = q.toString() ? `?${q.toString()}` : "";
    return request<Neighbor[]>(`/graph/nodes/${nodeId}/neighbors${queryStr}`);
  },

  async getConnectedMemories(nodeId: string, maxDepth: number = 0, params: TraversalParams = {}): Promise<Memory[]> {
    const q = new URLSearchParams();
    q.append("max_depth", String(maxDepth));
    if (params.direction) q.append("direction", params.direction);
    if (params.relationship_types) q.append("relationship_types", params.relationship_types);
    if (params.node_types) q.append("node_types", params.node_types);
    if (params.entity_types) q.append("entity_types", params.entity_types);
    if (params.confidence_threshold !== undefined) {
      q.append("confidence_threshold", String(params.confidence_threshold));
    }

    const queryStr = q.toString() ? `?${q.toString()}` : "";
    return request<Memory[]>(`/graph/nodes/${nodeId}/connected${queryStr}`);
  },

  async findShortestPath(sourceNodeId: string, targetNodeId: string, params: TraversalParams = {}): Promise<PathResponse> {
    const q = new URLSearchParams();
    q.append("source_node_id", sourceNodeId);
    q.append("target_node_id", targetNodeId);
    if (params.direction) q.append("direction", params.direction);
    if (params.relationship_types) q.append("relationship_types", params.relationship_types);
    if (params.node_types) q.append("node_types", params.node_types);
    if (params.entity_types) q.append("entity_types", params.entity_types);
    if (params.confidence_threshold !== undefined) {
      q.append("confidence_threshold", String(params.confidence_threshold));
    }

    const queryStr = q.toString() ? `?${q.toString()}` : "";
    return request<PathResponse>(`/graph/path${queryStr}`);
  },

  async traverseGraph(startNodeId: string, maxDepth: number = 3, params: TraversalParams = {}): Promise<TraversalResponse> {
    const q = new URLSearchParams();
    q.append("start_node_id", startNodeId);
    q.append("max_depth", String(maxDepth));
    if (params.direction) q.append("direction", params.direction);
    if (params.relationship_types) q.append("relationship_types", params.relationship_types);
    if (params.node_types) q.append("node_types", params.node_types);
    if (params.entity_types) q.append("entity_types", params.entity_types);
    if (params.confidence_threshold !== undefined) {
      q.append("confidence_threshold", String(params.confidence_threshold));
    }

    const queryStr = q.toString() ? `?${q.toString()}` : "";
    return request<TraversalResponse>(`/graph/traverse${queryStr}`);
  },
};
