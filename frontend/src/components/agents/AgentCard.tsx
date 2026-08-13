import { Agent } from "@/types";
import AgentStatusBadge from "./AgentStatusBadge";
import { Calendar } from "lucide-react";
import { cn } from "@/lib/utils";

interface AgentCardProps {
  agent: Agent;
  isActive: boolean;
  onClick: () => void;
}

export default function AgentCard({ agent, isActive, onClick }: AgentCardProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full text-left rounded-lg p-3 border transition-all duration-200 outline-none flex flex-col gap-2 cursor-pointer font-mono",
        isActive
          ? "bg-zinc-900 border-zinc-800 text-zinc-100 shadow-sm"
          : "text-zinc-400 hover:bg-zinc-900/40 hover:text-zinc-200 border-transparent"
      )}
    >
      <div className="flex items-start justify-between gap-2 w-full">
        <span className="font-semibold text-xs truncate max-w-[150px]">
          {agent.name}
        </span>
        <AgentStatusBadge status={agent.status} />
      </div>

      {agent.description && (
        <p className="text-[10px] text-zinc-550 font-sans line-clamp-2 leading-relaxed">
          {agent.description}
        </p>
      )}

      <div className="flex items-center gap-1 text-[9px] text-zinc-600 mt-0.5">
        <Calendar className="h-3 w-3" />
        <span>{new Date(agent.created_at).toLocaleDateString()}</span>
      </div>
    </button>
  );
}
