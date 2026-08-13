"use client";

import { useEffect, useState } from "react";
import { useAgentStore } from "@/store/agentStore";
import AgentCard from "@/components/agents/AgentCard";
import AgentDetails from "@/components/agents/AgentDetails";
import AgentCredentialPanel from "@/components/agents/AgentCredentialPanel";
import AgentFormDialog from "@/components/agents/AgentFormDialog";
import { Agent } from "@/types";
import { CreateAgentPayload } from "@/lib/api/agents";
import { 
  Bot, 
  Search, 
  Plus, 
  HelpCircle, 
  Activity,
  Loader2
} from "lucide-react";

export default function AgentsPage() {
  const {
    agents,
    selectedAgentId,
    credentials,
    isLoading,
    error,
    fetchAgents,
    selectAgent,
    createAgent,
    updateAgent,
    suspendAgent,
    reactivateAgent,
    revokeAgent,
    issueCredential,
    revokeCredential,
  } = useAgentStore();

  const [searchQuery, setSearchQuery] = useState("");
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [formEditData, setFormEditData] = useState<Agent | undefined>(undefined);
  const [submitting, setSubmitting] = useState(false);

  // Initial load
  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  const activeAgent = agents.find((a) => a.id === selectedAgentId);

  // Filter list
  const filteredAgents = agents.filter((a) => 
    a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (a.description && a.description.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const handleCreateClick = () => {
    setFormEditData(undefined);
    setIsFormOpen(true);
  };

  const handleEditClick = () => {
    if (!activeAgent) return;
    setFormEditData(activeAgent);
    setIsFormOpen(true);
  };

  const handleFormSubmit = async (payload: CreateAgentPayload) => {
    setSubmitting(true);
    try {
      if (formEditData) {
        // Edit profile
        const ok = await updateAgent(formEditData.id, payload);
        if (ok) setIsFormOpen(false);
      } else {
        // Create new agent
        const agent = await createAgent(payload);
        if (agent) {
          setIsFormOpen(false);
          // Auto select and load credentials
          selectAgent(agent.id);
        }
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleSuspend = async () => {
    if (!activeAgent) return;
    if (confirm(`Are you sure you want to suspend agent "${activeAgent.name}"? Active connections will be paused.`)) {
      await suspendAgent(activeAgent.id);
    }
  };

  const handleReactivate = async () => {
    if (!activeAgent) return;
    await reactivateAgent(activeAgent.id);
  };

  const handleRevoke = async () => {
    if (!activeAgent) return;
    if (confirm(`CRITICAL WARNING: Revoking agent "${activeAgent.name}" is permanent and CANNOT be undone. All credentials assigned to this agent will be permanently revoked immediately. Proceed?`)) {
      await revokeAgent(activeAgent.id);
      // Refresh credentials to show revoked status
      selectAgent(activeAgent.id);
    }
  };

  const handleIssueCred = async (payload: { description?: string | null; expires_in_days?: number | null }) => {
    if (!selectedAgentId) return null;
    return issueCredential(selectedAgentId, payload);
  };

  const handleRevokeCred = async (credId: string) => {
    if (!selectedAgentId) return false;
    return revokeCredential(selectedAgentId, credId);
  };

  return (
    <div className="flex-1 flex flex-col md:flex-row min-h-0 bg-zinc-950">
      
      {/* 1. Left Panel: Sidebar listing */}
      <div className="w-full md:w-80 border-b md:border-b-0 md:border-r border-zinc-900 bg-zinc-950 flex flex-col p-4 gap-4 shrink-0">
        
        {/* Header section */}
        <div className="flex items-center justify-between border-b border-zinc-900 pb-3">
          <div>
            <h1 className="text-sm font-semibold text-zinc-200 tracking-tight flex items-center gap-2">
              <Bot className="h-4.5 w-4.5 text-zinc-400" />
              <span>AI Agents</span>
            </h1>
            <p className="text-[10px] text-zinc-550 font-mono mt-0.5">({agents.length} Profiles registered)</p>
          </div>
          <button
            onClick={handleCreateClick}
            className="flex h-7 w-7 items-center justify-center rounded-lg bg-zinc-100 hover:bg-zinc-200 text-zinc-950 transition-colors cursor-pointer outline-none"
            title="Register Agent"
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>

        {/* Search filter input */}
        <div className="relative w-full">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-zinc-650" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search agents..."
            className="w-full rounded-lg border border-zinc-800 bg-zinc-950 pl-8.5 pr-3 py-2 text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-zinc-700 transition-colors font-mono"
          />
        </div>

        {/* Scroll list */}
        <div className="flex-1 overflow-y-auto pr-1">
          {isLoading && agents.length === 0 ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-5 w-5 text-zinc-700 animate-spin" />
            </div>
          ) : filteredAgents.length > 0 ? (
            <div className="flex flex-col gap-1.5">
              {filteredAgents.map((a) => (
                <AgentCard
                  key={a.id}
                  agent={a}
                  isActive={a.id === selectedAgentId}
                  onClick={() => selectAgent(a.id === selectedAgentId ? null : a.id)}
                />
              ))}
            </div>
          ) : (
            <div className="py-16 text-center text-xs text-zinc-650 font-mono">
              No agents registered.
            </div>
          )}
        </div>
      </div>

      {/* 2. Center Panel: Detailed Configurations */}
      <div className="flex-1 flex flex-col p-4 md:p-6 gap-6 min-h-0 border-b md:border-b-0 md:border-r border-zinc-900 overflow-y-auto">
        {activeAgent ? (
          <AgentDetails
            agent={activeAgent}
            onSuspend={handleSuspend}
            onReactivate={handleReactivate}
            onRevoke={handleRevoke}
            onEdit={handleEditClick}
            isLoading={isLoading}
          />
        ) : (
          <div className="flex-grow flex flex-col items-center justify-center text-center p-6 my-auto text-zinc-650 font-mono text-xs max-w-sm mx-auto">
            <Bot className="h-8 w-8 text-zinc-800 mb-3 animate-pulse" />
            <span>Select an agent profile from the list to view its active configurations, monitor parameters, and manage credentials.</span>
          </div>
        )}
      </div>

      {/* 3. Right Panel: API Key Credentials */}
      <div className="w-full md:w-80 bg-zinc-950 flex flex-col p-4 gap-4 shrink-0 overflow-y-auto">
        {activeAgent ? (
          <AgentCredentialPanel
            credentials={credentials}
            onIssueCredential={handleIssueCred}
            onRevokeCredential={handleRevokeCred}
            agentName={activeAgent.name}
          />
        ) : (
          <div className="flex-grow flex flex-col items-center justify-center text-center p-6 my-auto text-zinc-700 font-mono text-xs">
            <HelpCircle className="h-6 w-6 text-zinc-850 mb-2" />
            <span>Select an agent profile to view or issue API keys.</span>
          </div>
        )}
      </div>

      {/* Edit Form Dialog Overlay */}
      {isFormOpen && (
        <AgentFormDialog
          isOpen={isFormOpen}
          onClose={() => setIsFormOpen(false)}
          onSubmit={handleFormSubmit}
          initialData={formEditData}
          isSubmitting={submitting}
        />
      )}

      {/* Global Error Banner */}
      {error && (
        <div className="fixed bottom-4 right-4 z-50 p-3 bg-red-950/20 border border-red-900/35 rounded-lg text-xs font-mono text-red-400 shadow-xl max-w-sm flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-red-500 shrink-0" />
            <span>{error}</span>
          </div>
        </div>
      )}

    </div>
  );
}
