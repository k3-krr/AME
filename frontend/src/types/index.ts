// Adaptive Memory Engine (AME) - Frontend Common Type Definitions

export interface User {
  id: string;
  email: string;
  createdAt: string;
}

export interface Conversation {
  id: string;
  title: string;
  system_prompt?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  sender_role: 'user' | 'assistant' | 'system';
  content: string;
  memory_status: 'pending' | 'consolidated' | 'ignored';
  created_at: string;
}

// --- Memory Domain Types ---

export type MemoryType =
  | "Preference"
  | "Fact"
  | "Goal"
  | "Task"
  | "Profile"
  | "Relationship"
  | "Skill"
  | "Custom"
  | "Education"
  | "Work"
  | "Project"
  | "Habit"
  | "Event"
  | "Correction"
  | "Instruction";

export type MemoryStatus = "ACTIVE" | "ARCHIVED" | "DELETED";

export type MemorySystem = "Semantic" | "Episodic" | "Procedural" | "Working";

export interface Memory {
  id: string;
  user_id: string;
  conversation_id: string | null;
  content: string;
  memory_type: MemoryType;
  memory_system: MemorySystem;
  importance: number;
  confidence: number;
  status: MemoryStatus;
  created_at: string;
  updated_at: string;
  last_accessed_at: string;
  version: number;
  occurred_at: string | null;
  expires_at: string | null;
  metadata: Record<string, unknown>;
}

export interface MemorySearchResponse {
  memory: Memory;
  similarity: number;
}

export interface MemoryState {
  memory_id: string;
  access_count: number;
  retrieval_count: number;
  reinforcement_count: number;
  last_accessed_at: string;
  last_reinforced_at: string | null;
  decay_score: number;
  confidence_score: number;
  importance_score: number;
  source_type: string;
}

export interface MemoryAccessLog {
  id: string;
  memory_id: string;
  conversation_id: string | null;
  timestamp: string;
  similarity_score: number;
  ranking_score: number;
  retrieval_success: boolean;
}

export interface MemoryAnalytics {
  memory_id: string;
  state: MemoryState | null;
  access_logs: MemoryAccessLog[];
}

export interface AccessContext {
  tenant_id: string;
  principal_type: "USER" | "AGENT";
  user_id: string | null;
  agent_id: string | null;
}

