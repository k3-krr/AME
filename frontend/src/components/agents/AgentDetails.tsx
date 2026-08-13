import { Agent } from "@/types";
import AgentStatusBadge from "./AgentStatusBadge";
import { 
  Trash2, 
  Play, 
  Pause, 
  AlertOctagon,
  Edit
} from "lucide-react";

interface AgentDetailsProps {
  agent: Agent;
  onSuspend: () => Promise<void>;
  onReactivate: () => Promise<void>;
  onRevoke: () => Promise<void>;
  onEdit: () => void;
  isLoading: boolean;
}

export default function AgentDetails({
  agent,
  onSuspend,
  onReactivate,
  onRevoke,
  onEdit,
  isLoading,
}: AgentDetailsProps) {
  const isRevoked = agent.status === "REVOKED";
  const isSuspended = agent.status === "SUSPENDED";
  const isActive = agent.status === "ACTIVE";

  return (
    <div className="flex flex-col gap-5 text-xs font-mono text-zinc-400">
      
      {/* 1. Header block */}
      <div className="border-b border-zinc-900 pb-3 flex flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          <span className="text-[9px] uppercase tracking-widest text-zinc-550">Agent Profile</span>
          {!isRevoked && (
            <button
              onClick={onEdit}
              disabled={isLoading}
              className="p-1 rounded bg-zinc-900 border border-zinc-800 hover:bg-zinc-850 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer outline-none disabled:opacity-50"
              title="Edit configuration"
            >
              <Edit className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
        <h2 className="text-base font-bold text-zinc-100 tracking-tight leading-tight">{agent.name}</h2>
        <div className="flex items-center gap-2">
          <AgentStatusBadge status={agent.status} />
          <span className="text-[9px] text-zinc-600">ID: {agent.id}</span>
        </div>
      </div>

      {/* Revoked Warning Banner */}
      {isRevoked && (
        <div className="flex items-start gap-2.5 p-3 rounded-lg bg-red-950/20 border border-red-900/30 text-red-400 leading-normal font-sans">
          <AlertOctagon className="h-4.5 w-4.5 text-red-500 shrink-0 mt-0.5" />
          <div className="flex flex-col gap-0.5">
            <span className="font-semibold text-zinc-200 text-xs">Revoked Permanent State</span>
            <span>This agent has been permanently terminated. Revocation is a terminal state; it cannot be reactivated, configured, or utilized.</span>
          </div>
        </div>
      )}

      {/* 2. Metadata details */}
      <div className="flex flex-col gap-2.5 p-3 rounded-lg border border-zinc-900 bg-zinc-950/20">
        <div className="flex items-center justify-between">
          <span className="text-zinc-650">Tenant Scopes:</span>
          <span className="text-zinc-300 truncate max-w-[140px]" title={agent.tenant_id}>{agent.tenant_id}</span>
        </div>
        <div className="flex items-center justify-between border-t border-zinc-900 pt-2 mt-1">
          <span className="text-zinc-650">Registered:</span>
          <span>{new Date(agent.created_at).toLocaleString()}</span>
        </div>
        <div className="flex items-center justify-between border-t border-zinc-900 pt-2 mt-1">
          <span className="text-zinc-650">Last Update:</span>
          <span>{new Date(agent.updated_at).toLocaleString()}</span>
        </div>
      </div>

      {/* 3. Description description */}
      {agent.description && (
        <div className="flex flex-col gap-1.5 border-t border-zinc-900 pt-4">
          <span className="text-[9px] text-zinc-550 uppercase tracking-widest">Purpose Description</span>
          <p className="text-zinc-350 leading-relaxed font-sans text-xs">{agent.description}</p>
        </div>
      )}

      {/* 4. Configuration JSON dictionary */}
      <div className="flex flex-col gap-2 border-t border-zinc-900 pt-4">
        <span className="text-[9px] text-zinc-550 uppercase tracking-widest">Configuration State</span>
        <pre className="p-3 rounded-lg border border-zinc-900 bg-zinc-950/20 max-h-[220px] overflow-auto text-[10px] text-zinc-300 leading-normal">
          {JSON.stringify(agent.configuration, null, 2)}
        </pre>
      </div>

      {/* 5. Lifecycle actions */}
      {!isRevoked && (
        <div className="flex flex-col gap-2 border-t border-zinc-900 pt-4">
          <span className="text-[9px] text-zinc-550 uppercase tracking-widest">Lifecycle Actions</span>
          <div className="flex flex-wrap gap-2 mt-1">
            {isActive && (
              <button
                onClick={onSuspend}
                disabled={isLoading}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-zinc-800 bg-zinc-900 hover:bg-zinc-850 hover:text-zinc-200 transition-all cursor-pointer outline-none font-semibold disabled:opacity-50 text-[10px]"
              >
                <Pause className="h-3.5 w-3.5 text-amber-500" />
                <span>Suspend</span>
              </button>
            )}
            {isSuspended && (
              <button
                onClick={onReactivate}
                disabled={isLoading}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-zinc-800 bg-zinc-900 hover:bg-zinc-850 hover:text-zinc-200 transition-all cursor-pointer outline-none font-semibold disabled:opacity-50 text-[10px]"
              >
                <Play className="h-3.5 w-3.5 text-emerald-500" />
                <span>Reactivate</span>
              </button>
            )}
            <button
              onClick={onRevoke}
              disabled={isLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-red-900/40 bg-red-950/10 hover:bg-red-950/20 text-red-400 hover:text-red-300 transition-all cursor-pointer outline-none font-semibold disabled:opacity-50 text-[10px]"
            >
              <Trash2 className="h-3.5 w-3.5 text-red-500" />
              <span>Revoke Agent</span>
            </button>
          </div>
        </div>
      )}

    </div>
  );
}
