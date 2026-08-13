import { AgentStatus } from "@/types";
import { cn } from "@/lib/utils";

interface AgentStatusBadgeProps {
  status: AgentStatus;
  className?: string;
}

export default function AgentStatusBadge({ status, className }: AgentStatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex px-1.5 py-0.5 rounded text-[9px] font-mono border uppercase tracking-wider font-semibold",
        status === "ACTIVE" && "bg-emerald-950/20 text-emerald-400 border-emerald-900/30",
        status === "SUSPENDED" && "bg-amber-950/20 text-amber-400 border-amber-900/30",
        status === "REVOKED" && "bg-red-950/20 text-red-400 border-red-900/30",
        className
      )}
    >
      {status}
    </span>
  );
}
