import { create } from "zustand";
import { 
  Entity, 
  Relationship, 
  Neighbor, 
  Memory, 
  PathResponse, 
  TraversalResponse 
} from "@/types";
import { 
  knowledgeGraphApi, 
  CreateEntityPayload, 
  UpdateEntityPayload, 
  CreateRelationshipPayload 
} from "@/lib/api/knowledgeGraph";
import { ApiError } from "@/lib/api/client";

interface KnowledgeGraphState {
  entities: Entity[];
  relationships: Relationship[];
  selectedEntityId: string | null;
  selectedRelationshipId: string | null;
  neighbors: Neighbor[];
  connectedMemories: Memory[];
  shortestPath: PathResponse | null;
  traversalResult: TraversalResponse | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchGraphData: () => Promise<void>;
  selectEntity: (entityId: string | null) => Promise<void>;
  selectRelationship: (relationshipId: string | null) => void;
  createEntity: (payload: CreateEntityPayload) => Promise<Entity | null>;
  updateEntity: (entityId: string, payload: UpdateEntityPayload) => Promise<boolean>;
  deleteEntity: (entityId: string) => Promise<boolean>;
  createRelationship: (payload: CreateRelationshipPayload) => Promise<Relationship | null>;
  deleteRelationship: (relationshipId: string) => Promise<boolean>;
  fetchShortestPath: (sourceId: string, targetId: string) => Promise<void>;
  runTraversal: (startId: string, maxDepth: number) => Promise<void>;
  clearTraversalAndPaths: () => void;
  resetGraphStore: () => void;
}

export const useKnowledgeGraphStore = create<KnowledgeGraphState>((set, get) => ({
  entities: [],
  relationships: [],
  selectedEntityId: null,
  selectedRelationshipId: null,
  neighbors: [],
  connectedMemories: [],
  shortestPath: null,
  traversalResult: null,
  isLoading: false,
  error: null,

  resetGraphStore: () => set({
    entities: [],
    relationships: [],
    selectedEntityId: null,
    selectedRelationshipId: null,
    neighbors: [],
    connectedMemories: [],
    shortestPath: null,
    traversalResult: null,
    isLoading: false,
    error: null,
  }),

  clearTraversalAndPaths: () => set({
    shortestPath: null,
    traversalResult: null,
    error: null,
  }),

  fetchGraphData: async () => {
    set({ isLoading: true, error: null });
    try {
      // Load 100 entities and 200 relationships to show a rich visual local sub-graph neighborhood
      const [entitiesData, relationshipsData] = await Promise.all([
        knowledgeGraphApi.listEntities({ limit: 100 }),
        knowledgeGraphApi.listRelationships({ limit: 100 }),
      ]);
      set({ 
        entities: entitiesData, 
        relationships: relationshipsData 
      });
    } catch (err) {
      if (err instanceof ApiError) {
        set({ error: err.message });
      } else {
        set({ error: "Failed to load knowledge graph elements." });
      }
    } finally {
      set({ isLoading: false });
    }
  },

  selectEntity: async (entityId: string | null) => {
    if (!entityId) {
      set({ 
        selectedEntityId: null, 
        neighbors: [], 
        connectedMemories: [] 
      });
      return;
    }

    set({ 
      selectedEntityId: entityId, 
      selectedRelationshipId: null, 
      isLoading: true, 
      error: null 
    });

    try {
      const [neighborsData, memoriesData] = await Promise.all([
        knowledgeGraphApi.getNeighbors(entityId),
        knowledgeGraphApi.getConnectedMemories(entityId, 1), // Depth 1 connected memories
      ]);
      set({ 
        neighbors: neighborsData, 
        connectedMemories: memoriesData 
      });
    } catch (err) {
      if (err instanceof ApiError) {
        set({ error: err.message });
      } else {
        set({ error: "Failed to load entity relational details." });
      }
    } finally {
      set({ isLoading: false });
    }
  },

  selectRelationship: (relationshipId: string | null) => {
    set({ 
      selectedRelationshipId: relationshipId, 
      selectedEntityId: null 
    });
  },

  createEntity: async (payload: CreateEntityPayload) => {
    set({ isLoading: true, error: null });
    try {
      const entity = await knowledgeGraphApi.createEntity(payload);
      set((state) => ({
        entities: [entity, ...state.entities],
      }));
      return entity;
    } catch (err) {
      if (err instanceof ApiError) {
        set({ error: err.message });
      } else {
        set({ error: "Failed to create entity node." });
      }
      return null;
    } finally {
      set({ isLoading: false });
    }
  },

  updateEntity: async (entityId: string, payload: UpdateEntityPayload) => {
    set({ isLoading: true, error: null });
    try {
      const updated = await knowledgeGraphApi.updateEntity(entityId, payload);
      set((state) => ({
        entities: state.entities.map((e) => e.id === entityId ? updated : e),
      }));
      return true;
    } catch (err) {
      if (err instanceof ApiError) {
        set({ error: err.message });
      } else {
        set({ error: "Failed to modify entity node properties." });
      }
      return false;
    } finally {
      set({ isLoading: false });
    }
  },

  deleteEntity: async (entityId: string) => {
    set({ isLoading: true, error: null });
    try {
      await knowledgeGraphApi.deleteEntity(entityId);
      const isSelected = get().selectedEntityId === entityId;
      set((state) => ({
        entities: state.entities.filter((e) => e.id !== entityId),
        relationships: state.relationships.filter(
          (r) => r.source_entity_id !== entityId && r.target_entity_id !== entityId
        ),
        selectedEntityId: isSelected ? null : state.selectedEntityId,
        neighbors: isSelected ? [] : state.neighbors,
        connectedMemories: isSelected ? [] : state.connectedMemories,
      }));
      return true;
    } catch (err) {
      if (err instanceof ApiError) {
        set({ error: err.message });
      } else {
        set({ error: "Failed to delete entity node." });
      }
      return false;
    } finally {
      set({ isLoading: false });
    }
  },

  createRelationship: async (payload: CreateRelationshipPayload) => {
    set({ isLoading: true, error: null });
    try {
      const relationship = await knowledgeGraphApi.createRelationship(payload);
      set((state) => ({
        relationships: [relationship, ...state.relationships],
      }));
      return relationship;
    } catch (err) {
      if (err instanceof ApiError) {
        set({ error: err.message });
      } else {
        set({ error: "Failed to create relationship edge." });
      }
      return null;
    } finally {
      set({ isLoading: false });
    }
  },

  deleteRelationship: async (relationshipId: string) => {
    set({ isLoading: true, error: null });
    try {
      await knowledgeGraphApi.deleteRelationship(relationshipId);
      const isSelected = get().selectedRelationshipId === relationshipId;
      set((state) => ({
        relationships: state.relationships.filter((r) => r.id !== relationshipId),
        selectedRelationshipId: isSelected ? null : state.selectedRelationshipId,
      }));
      return true;
    } catch (err) {
      if (err instanceof ApiError) {
        set({ error: err.message });
      } else {
        set({ error: "Failed to delete relationship edge." });
      }
      return false;
    } finally {
      set({ isLoading: false });
    }
  },

  fetchShortestPath: async (sourceId: string, targetId: string) => {
    set({ isLoading: true, error: null, shortestPath: null, traversalResult: null });
    try {
      const pathData = await knowledgeGraphApi.findShortestPath(sourceId, targetId);
      set({ shortestPath: pathData });
    } catch (err) {
      if (err instanceof ApiError) {
        set({ error: err.message });
      } else {
        set({ error: "No path exists between the selected nodes." });
      }
    } finally {
      set({ isLoading: false });
    }
  },

  runTraversal: async (startId: string, maxDepth: number) => {
    set({ isLoading: true, error: null, traversalResult: null, shortestPath: null });
    try {
      const traversalData = await knowledgeGraphApi.traverseGraph(startId, maxDepth);
      set({ traversalResult: traversalData });
    } catch (err) {
      if (err instanceof ApiError) {
        set({ error: err.message });
      } else {
        set({ error: "Graph traversal procedure failed." });
      }
    } finally {
      set({ isLoading: false });
    }
  },
}));
