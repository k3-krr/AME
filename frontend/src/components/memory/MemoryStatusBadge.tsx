import { MemorySystem, MemoryStatus, MemoryType } from "@/types";
import { cn } from "@/lib/utils";

interface BadgeProps {
  value: MemorySystem | MemoryStatus | MemoryType;
  type: "system" | "status" | "type";
  className?: string;
}

export default function MemoryStatusBadge({ value, type, className }: BadgeProps) {
  if (type === "system") {
    const sys = value as MemorySystem;
    const systemColors: Record<MemorySystem, string> = {
      Semantic: "bg-blue-950/30 text-blue-400 border-blue-900/40",
      Episodic: "bg-purple-955/30 text-purple-400 border-purple-900/40", // standard purple or violet
      Procedural: "bg-amber-950/30 text-amber-400 border-amber-900/40",
      Working: "bg-rose-950/30 text-rose-400 border-rose-900/40",
    };
    
    // Fix class names slightly: purple is standard
    const resolvedColor = systemColors[sys] || "bg-zinc-900 text-zinc-400 border-zinc-800";
    
    return (
      <span className={cn("inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-mono border", resolvedColor, className)}>
        {sys}
      </span>
    );
  }

  if (type === "status") {
    const stat = value as MemoryStatus;
    const statusColors: Record<MemoryStatus, string> = {
      ACTIVE: "bg-emerald-950/20 text-emerald-400 border-emerald-900/30",
      ARCHIVED: "bg-zinc-900 text-zinc-400 border-zinc-800",
      DELETED: "bg-red-950/20 text-red-400 border-red-900/30",
    };

    const resolvedColor = statusColors[stat] || "bg-zinc-900 text-zinc-400 border-zinc-800";

    return (
      <span className={cn("inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-mono border font-semibold", resolvedColor, className)}>
        {stat}
      </span>
    );
  }

  // Type-specific badge
  const t = value as MemoryType;
  return (
    <span className={cn("inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-mono bg-zinc-900 border border-zinc-800/80 text-zinc-300", className)}>
      {t}
    </span>
  );
}
