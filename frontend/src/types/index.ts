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

// --- Knowledge Graph Types (Phase 4) ---

export type EntityType = 
  | "PERSON"
  | "ORGANIZATION"
  | "PROJECT"
  | "TECHNOLOGY"
  | "FRAMEWORK"
  | "DATABASE"
  | "API"
  | "DOCUMENT"
  | "CUSTOM";

export type RelationshipType =
  | "USES"
  | "DEPENDS_ON"
  | "IMPLEMENTS"
  | "REFERENCES"
  | "RELATED_TO"
  | "PART_OF"
  | "CREATED_BY"
  | "LOCATED_IN"
  | "INDEXED_BY"
  | "CUSTOM";

export interface Entity {
  id: string;
  user_id: string;
  name: string;
  canonical_name: string;
  entity_type: EntityType;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Relationship {
  id: string;
  user_id: string;
  source_entity_id: string;
  target_entity_id: string;
  relationship_type: RelationshipType;
  confidence: number;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface Neighbor {
  node: Entity;
  relationship: Relationship;
  direction: "incoming" | "outgoing";
}

export interface TraversalNodeInfo {
  node: Entity;
  depth: number;
}

export interface TraversalMetadata {
  traversal_strategy: string;
  max_depth: number;
  traversal_depth: number;
  visited_node_count: number;
  visited_relationship_count: number;
  path_length: number | null;
  execution_time_ms: number;
  termination_reason: string;
}

export interface TraversalResponse {
  nodes: TraversalNodeInfo[];
  metadata: TraversalMetadata;
}

export interface PathResponse {
  nodes: Entity[];
  relationships: Relationship[];
  hop_count: number;
  metadata: TraversalMetadata;
}

// --- Agent Types (Phase 5) ---

export type AgentStatus = "ACTIVE" | "SUSPENDED" | "REVOKED";

export interface Agent {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  status: AgentStatus;
  configuration: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface AgentCredential {
  id: string;
  agent_id: string;
  description: string | null;
  raw_key?: string | null;
  created_at: string;
  expires_at: string | null;
  revoked_at: string | null;
  last_used_at: string | null;
}

// --- Retrieval Types (Phase 6) ---

export interface RetrievalRequest {
  query: string;
  conversation_id?: string | null;
  options?: Record<string, unknown> | null;
}

export interface ContextElement {
  memory_id: string;
  content: string;
  relevance_score: number;
  source_tier: string;
  provenance_metadata: Record<string, unknown>;
}

export interface GroundedContextPackage {
  request_id: string;
  fused_elements: ContextElement[];
  metadata: Record<string, unknown>;
  compiled_at: string;
  status: string;
}

export interface RetrievalPlan {
  intent: string;
  recommended_capabilities: string[];
  confidence: number;
  metadata: Record<string, unknown>;
}

export interface QueryAnalysisResult {
  original_query: string;
  normalized_query: string;
  retrieval_plan: RetrievalPlan;
}

export interface RetrievalQuery {
  query: string;
  priority: number;
  reason: string;
  source: string;
}

export interface QueryRewriteResult {
  original_query: string;
  rewritten_query: string;
  retrieval_queries: RetrievalQuery[];
  metadata: Record<string, unknown>;
}

export interface Citation {
  index: number;
  memory_id: string;
  source_tier: string;
  content: string;
  relevance_score: number;
  originating_queries: string[];
}

export interface GroundedPromptPackage {
  request_id: string;
  user_query: string;
  system_prompt: string;
  formatted_context: string;
  citations: Citation[];
  grounding_metadata: Record<string, unknown>;
  compiled_at: string;
  status: string;
}




