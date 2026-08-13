import { create } from "zustand";
import { Agent, AgentCredential } from "@/types";
import { 
  agentsApi, 
  CreateAgentPayload, 
  UpdateAgentPayload, 
  IssueCredentialPayload 
} from "@/lib/api/agents";
import { ApiError } from "@/lib/api/client";

interface AgentState {
  agents: Agent[];
  selectedAgentId: string | null;
  credentials: AgentCredential[];
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchAgents: () => Promise<void>;
  selectAgent: (agentId: string | null) => Promise<void>;
  createAgent: (payload: CreateAgentPayload) => Promise<Agent | null>;
  updateAgent: (agentId: string, payload: UpdateAgentPayload) => Promise<boolean>;
  suspendAgent: (agentId: string) => Promise<boolean>;
  reactivateAgent: (agentId: string) => Promise<boolean>;
  revokeAgent: (agentId: string) => Promise<boolean>;
  issueCredential: (agentId: string, payload: IssueCredentialPayload) => Promise<AgentCredential | null>;
  revokeCredential: (agentId: string, credentialId: string) => Promise<boolean>;
  resetAgentStore: () => void;
}

export const useAgentStore = create<AgentState>((set) => ({
  agents: [],
  selectedAgentId: null,
  credentials: [],
  isLoading: false,
  error: null,

  resetAgentStore: () => set({
    agents: [],
    selectedAgentId: null,
    credentials: [],
    isLoading: false,
    error: null,
  }),

  fetchAgents: async () => {
    set({ isLoading: true, error: null });
    try {
      const agentsData = await agentsApi.listAgents();
      set({ agents: agentsData });
    } catch (err) {
      if (err instanceof ApiError) {
        set({ error: err.message });
      } else {
        set({ error: "Failed to retrieve agents list." });
      }
    } finally {
      set({ isLoading: false });
    }
  },

  selectAgent: async (agentId: string | null) => {
    if (!agentId) {
      set({ selectedAgentId: null, credentials: [] });
      return;
    }

    set({ selectedAgentId: agentId, isLoading: true, error: null });
    try {
      const credentialsData = await agentsApi.listCredentials(agentId);
      set({ credentials: credentialsData });
    } catch (err) {
      if (err instanceof ApiError) {
        set({ error: err.message });
      } else {
        set({ error: "Failed to load credentials for agent." });
      }
    } finally {
      set({ isLoading: false });
    }
  },

  createAgent: async (payload: CreateAgentPayload) => {
    set({ isLoading: true, error: null });
    try {
      const agent = await agentsApi.createAgent(payload);
      set((state) => ({
        agents: [agent, ...state.agents],
        selectedAgentId: agent.id,
        credentials: [], // New agent has no credentials yet
      }));
      return agent;
    } catch (err) {
      if (err instanceof ApiError) {
        set({ error: err.message });
      } else {
        set({ error: "Failed to create agent record." });
      }
      return null;
    } finally {
      set({ isLoading: false });
    }
  },

  updateAgent: async (agentId: string, payload: UpdateAgentPayload) => {
    set({ isLoading: true, error: null });
    try {
      const updated = await agentsApi.updateAgent(agentId, payload);
      set((state) => ({
        agents: state.agents.map((a) => a.id === agentId ? updated : a),
      }));
      return true;
    } catch (err) {
      if (err instanceof ApiError) {
        set({ error: err.message });
      } else {
        set({ error: "Failed to update agent configurations." });
      }
      return false;
    } finally {
      set({ isLoading: false });
    }
  },

  suspendAgent: async (agentId: string) => {
    set({ isLoading: true, error: null });
    try {
      const updated = await agentsApi.suspendAgent(agentId);
      set((state) => ({
        agents: state.agents.map((a) => a.id === agentId ? updated : a),
      }));
      return true;
    } catch (err) {
      if (err instanceof ApiError) {
        set({ error: err.message });
      } else {
        set({ error: "Failed to suspend agent." });
      }
      return false;
    } finally {
      set({ isLoading: false });
    }
  },

  reactivateAgent: async (agentId: string) => {
    set({ isLoading: true, error: null });
    try {
      const updated = await agentsApi.reactivateAgent(agentId);
      set((state) => ({
        agents: state.agents.map((a) => a.id === agentId ? updated : a),
      }));
      return true;
    } catch (err) {
      if (err instanceof ApiError) {
        set({ error: err.message });
      } else {
        set({ error: "Failed to reactivate agent." });
      }
      return false;
    } finally {
      set({ isLoading: false });
    }
  },

  revokeAgent: async (agentId: string) => {
    set({ isLoading: true, error: null });
    try {
      const updated = await agentsApi.revokeAgent(agentId);
      set((state) => ({
        agents: state.agents.map((a) => a.id === agentId ? updated : a),
      }));
      return true;
    } catch (err) {
      if (err instanceof ApiError) {
        set({ error: err.message });
      } else {
        set({ error: "Failed to revoke agent." });
      }
      return false;
    } finally {
      set({ isLoading: false });
    }
  },

  issueCredential: async (agentId: string, payload: IssueCredentialPayload) => {
    set({ isLoading: true, error: null });
    try {
      const cred = await agentsApi.issueCredential(agentId, payload);
      set((state) => ({
        credentials: [cred, ...state.credentials],
      }));
      return cred;
    } catch (err) {
      if (err instanceof ApiError) {
        set({ error: err.message });
      } else {
        set({ error: "Failed to issue new credentials." });
      }
      return null;
    } finally {
      set({ isLoading: false });
    }
  },

  revokeCredential: async (agentId: string, credentialId: string) => {
    set({ isLoading: true, error: null });
    try {
      const res = await agentsApi.revokeCredential(agentId, credentialId);
      set((state) => ({
        credentials: state.credentials.map((c) => 
          c.id === credentialId ? { ...c, revoked_at: res.revoked_at } : c
        ),
      }));
      return true;
    } catch (err) {
      if (err instanceof ApiError) {
        set({ error: err.message });
      } else {
        set({ error: "Failed to revoke credential." });
      }
      return false;
    } finally {
      set({ isLoading: false });
    }
  },
}));
