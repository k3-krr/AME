import { request } from "./client";
import { Agent, AgentCredential } from "@/types";

export interface CreateAgentPayload {
  name: string;
  description?: string | null;
  configuration?: Record<string, unknown> | null;
}

export interface UpdateAgentPayload {
  name?: string;
  description?: string | null;
  configuration?: Record<string, unknown> | null;
}

export interface IssueCredentialPayload {
  description?: string | null;
  expires_in_days?: number | null;
}

export interface RevokeCredentialResponse {
  id: string;
  revoked_at: string;
}

export const agentsApi = {
  async listAgents(): Promise<Agent[]> {
    return request<Agent[]>("/agents");
  },

  async getAgent(agentId: string): Promise<Agent> {
    return request<Agent>(`/agents/${agentId}`);
  },

  async createAgent(payload: CreateAgentPayload): Promise<Agent> {
    return request<Agent>("/agents", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async updateAgent(agentId: string, payload: UpdateAgentPayload): Promise<Agent> {
    return request<Agent>(`/agents/${agentId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  async suspendAgent(agentId: string): Promise<Agent> {
    return request<Agent>(`/agents/${agentId}/suspend`, {
      method: "POST",
    });
  },

  async reactivateAgent(agentId: string): Promise<Agent> {
    return request<Agent>(`/agents/${agentId}/reactivate`, {
      method: "POST",
    });
  },

  async revokeAgent(agentId: string): Promise<Agent> {
    return request<Agent>(`/agents/${agentId}/revoke`, {
      method: "POST",
    });
  },

  async issueCredential(agentId: string, payload: IssueCredentialPayload = {}): Promise<AgentCredential> {
    return request<AgentCredential>(`/agents/${agentId}/credentials`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async listCredentials(agentId: string): Promise<AgentCredential[]> {
    return request<AgentCredential[]>(`/agents/${agentId}/credentials`);
  },

  async revokeCredential(agentId: string, credentialId: string): Promise<RevokeCredentialResponse> {
    return request<RevokeCredentialResponse>(`/agents/${agentId}/credentials/${credentialId}/revoke`, {
      method: "POST",
    });
  },
};
