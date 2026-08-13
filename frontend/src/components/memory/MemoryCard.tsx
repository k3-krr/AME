import Link from "next/link";
import { Memory } from "@/types";
import MemoryStatusBadge from "./MemoryStatusBadge";
import { Clock, Eye } from "lucide-react";

interface MemoryCardProps {
  memory: Memory;
}

export default function MemoryCard({ memory }: MemoryCardProps) {
  // Format dates cleanly
  const formattedDate = new Date(memory.created_at).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  return (
    <div className="group border border-zinc-900 bg-zinc-950 hover:border-zinc-800 transition-all duration-200 rounded-xl p-4 md:p-5 flex flex-col justify-between h-48">
      {/* Top Header Card Info */}
      <div className="flex flex-col gap-2.5">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-1.5 flex-wrap">
            <MemoryStatusBadge value={memory.memory_system} type="system" />
            <MemoryStatusBadge value={memory.memory_type} type="type" />
          </div>
          {memory.status !== "ACTIVE" && (
            <MemoryStatusBadge value={memory.status} type="status" />
          )}
        </div>

        {/* Content Preview */}
        <p className="text-sm text-zinc-300 line-clamp-3 leading-relaxed mt-1 group-hover:text-zinc-200 transition-colors">
          {memory.content}
        </p>
      </div>

      {/* Footer Metrics Area */}
      <div className="flex items-center justify-between border-t border-zinc-900/60 pt-3 text-[11px] font-mono text-zinc-500">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1" title={`Importance: ${Math.round(memory.importance * 100)}%`}>
            <span>imp:</span>
            <span className="text-zinc-400 font-semibold">{Math.round(memory.importance * 100)}%</span>
          </div>
          <div className="flex items-center gap-1" title={`Confidence: ${Math.round(memory.confidence * 100)}%`}>
            <span>conf:</span>
            <span className="text-zinc-400 font-semibold">{Math.round(memory.confidence * 100)}%</span>
          </div>
        </div>

        {/* Details action */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 text-[10px]">
            <Clock className="h-3 w-3 text-zinc-650" />
            <span>{formattedDate}</span>
          </div>
          <Link
            href={`/memories/${memory.id}`}
            className="flex items-center gap-1.5 px-2 py-0.5 rounded border border-zinc-800 bg-zinc-900/40 text-[10px] text-zinc-400 group-hover:text-zinc-200 group-hover:bg-zinc-900 transition-all outline-none"
            aria-label={`View memory details for ${memory.id}`}
          >
            <Eye className="h-3 w-3" />
            <span>View</span>
          </Link>
        </div>
      </div>
    </div>
  );
}
