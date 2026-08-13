import Link from "next/link";
import { ContextElement } from "@/types";
import { ExternalLink, Percent, Layers } from "lucide-react";

interface RetrievalResultsProps {
  elements: ContextElement[];
}

export default function RetrievalResults({ elements }: RetrievalResultsProps) {
  if (elements.length === 0) {
    return (
      <div className="py-20 text-center font-mono text-xs text-zinc-600">
        No matching retrieval elements returned.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 font-mono text-xs text-zinc-400">
      {elements.map((el) => {
        const scorePercentage = Math.round(el.relevance_score * 100);
        
        return (
          <div
            key={el.memory_id}
            className="p-4 rounded-xl border border-zinc-900 bg-zinc-950/20 hover:border-zinc-850 transition-colors flex flex-col gap-3 group"
          >
            {/* Header info */}
            <div className="flex items-start justify-between gap-3 border-b border-zinc-900 pb-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-850 text-[9px] text-zinc-400 font-bold uppercase tracking-wider">
                  <Layers className="h-3 w-3 text-zinc-550 shrink-0" />
                  <span>{el.source_tier}</span>
                </span>
                <span className="text-[9px] text-zinc-600 truncate max-w-[120px]" title={el.memory_id}>
                  ID: {el.memory_id.slice(0, 18)}...
                </span>
              </div>
              
              <div className="flex items-center gap-2">
                {/* Score */}
                <span className="inline-flex items-center gap-0.5 text-[10px] text-emerald-400 font-semibold bg-emerald-950/20 px-1.5 py-0.5 rounded border border-emerald-900/30">
                  <Percent className="h-3 w-3 text-emerald-500 shrink-0" />
                  <span>{scorePercentage}% Relevance</span>
                </span>
                
                {/* Link */}
                <Link
                  href={`/memories/${el.memory_id}`}
                  className="p-1 rounded bg-zinc-900 hover:bg-zinc-850 text-zinc-500 hover:text-zinc-300 transition-colors outline-none shrink-0"
                  title="Inspect Memory detail page"
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                </Link>
              </div>
            </div>

            {/* Content text */}
            <p className="text-zinc-300 font-sans text-xs leading-relaxed group-hover:text-zinc-200 transition-colors whitespace-pre-wrap">
              {el.content}
            </p>

            {/* Metadata tags */}
            {Object.keys(el.provenance_metadata).length > 0 && (
              <div className="flex flex-col gap-1 border-t border-zinc-900 pt-2 mt-0.5 text-[9px] text-zinc-550">
                <span className="uppercase tracking-widest text-[8px] text-zinc-600">Provenance Context</span>
                <pre className="p-2 rounded bg-zinc-900/10 border border-zinc-900/50 max-h-[80px] overflow-auto text-zinc-400 text-[9px] leading-normal font-mono">
                  {JSON.stringify(el.provenance_metadata, null, 2)}
                </pre>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
