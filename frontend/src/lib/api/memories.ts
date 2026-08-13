import { request } from "./client";
import { 
  Memory, 
  MemoryType, 
  MemoryStatus, 
  MemorySystem, 
  MemorySearchResponse, 
  MemoryAnalytics 
} from "@/types";

export interface ListMemoriesParams {
  memory_type?: MemoryType | "";
  status?: MemoryStatus | "";
  page?: number;
  limit?: number;
  sort_by?: "created_at" | "updated_at" | "importance" | "confidence";
  sort_order?: "asc" | "desc";
}

export interface CreateMemoryPayload {
  conversation_id?: string | null;
  content: string;
  memory_type: MemoryType;
  importance: number;
  confidence: number;
  metadata?: Record<string, unknown> | null;
  memory_system?: MemorySystem | null;
  occurred_at?: string | null;
  expires_at?: string | null;
}

export interface UpdateMemoryPayload {
  content?: string;
  memory_type?: MemoryType;
  importance?: number;
  confidence?: number;
  status?: MemoryStatus;
  metadata?: Record<string, unknown> | null;
  memory_system?: MemorySystem;
  occurred_at?: string | null;
  expires_at?: string | null;
}

export const memoriesApi = {
  async listMemories(params: ListMemoriesParams = {}): Promise<Memory[]> {
    const query = new URLSearchParams();
    if (params.memory_type) query.append("memory_type", params.memory_type);
    if (params.status) query.append("status", params.status);
    if (params.page !== undefined) query.append("page", String(params.page));
    if (params.limit !== undefined) query.append("limit", String(params.limit));
    if (params.sort_by) query.append("sort_by", params.sort_by);
    if (params.sort_order) query.append("sort_order", params.sort_order);

    const queryString = query.toString();
    return request<Memory[]>(`/memories${queryString ? `?${queryString}` : ""}`);
  },

  async getMemory(id: string): Promise<Memory> {
    return request<Memory>(`/memories/${id}`);
  },

  async createMemory(payload: CreateMemoryPayload): Promise<Memory> {
    return request<Memory>("/memories", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async updateMemory(id: string, payload: UpdateMemoryPayload): Promise<Memory> {
    return request<Memory>(`/memories/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },

  async deleteMemory(id: string): Promise<void> {
    await request<void>(`/memories/${id}`, {
      method: "DELETE",
    });
  },

  async searchMemories(query: string, topK = 5, memoryType?: MemoryType | ""): Promise<MemorySearchResponse[]> {
    const params = new URLSearchParams({ query, top_k: String(topK) });
    if (memoryType) {
      params.append("memory_type", memoryType);
    }
    return request<MemorySearchResponse[]>(`/memories/search?${params.toString()}`);
  },

  async reinforceMemory(id: string): Promise<{ message: string }> {
    return request<{ message: string }>(`/memories/${id}/reinforce`, {
      method: "POST",
    });
  },

  async getMemoryAnalytics(id: string): Promise<MemoryAnalytics> {
    return request<MemoryAnalytics>(`/memories/${id}/analytics`);
  },

  async triggerDecay(): Promise<{ updated_count: number }> {
    return request<{ updated_count: number }>("/memories/decay", {
      method: "POST",
    });
  },

  async triggerReindex(): Promise<{ reindexed_count: number }> {
    return request<{ reindexed_count: number }>("/memories/reindex", {
      method: "POST",
    });
  },
};
