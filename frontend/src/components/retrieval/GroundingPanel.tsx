import { useState } from "react";
import Link from "next/link";
import { GroundedPromptPackage } from "@/types";
import { Copy, Check, ExternalLink } from "lucide-react";

interface GroundingPanelProps {
  promptPackage: GroundedPromptPackage | null;
}

export default function GroundingPanel({ promptPackage }: GroundingPanelProps) {
  const [copiedSystem, setCopiedSystem] = useState(false);
  const [copiedContext, setCopiedContext] = useState(false);

  if (!promptPackage) {
    return (
      <div className="py-20 text-center font-mono text-xs text-zinc-650">
        No context grounding package executed yet.
      </div>
    );
  }

  const handleCopySystem = () => {
    navigator.clipboard.writeText(promptPackage.system_prompt);
    setCopiedSystem(true);
    setTimeout(() => setCopiedSystem(false), 2000);
  };

  const handleCopyContext = () => {
    navigator.clipboard.writeText(promptPackage.formatted_context);
    setCopiedContext(true);
    setTimeout(() => setCopiedContext(false), 2000);
  };

  return (
    <div className="flex flex-col gap-6 font-mono text-xs text-zinc-400">
      
      {/* System Prompt Section */}
      <div className="flex flex-col gap-2.5">
        <div className="flex items-center justify-between border-b border-zinc-900 pb-1.5">
          <span className="text-[10px] uppercase tracking-wider text-zinc-300 font-bold">System Instructions (Template Output)</span>
          <button
            onClick={handleCopySystem}
            className="flex items-center gap-1 text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors cursor-pointer outline-none"
            title="Copy system instruction text"
          >
            {copiedSystem ? <Check className="h-3.5 w-3.5 text-emerald-450" /> : <Copy className="h-3.5 w-3.5" />}
            <span>{copiedSystem ? "Copied" : "Copy"}</span>
          </button>
        </div>
        <pre className="p-3.5 rounded-xl border border-zinc-900 bg-zinc-950/20 max-h-[160px] overflow-auto text-[10px] text-zinc-350 leading-relaxed whitespace-pre-wrap font-mono">
          {promptPackage.system_prompt}
        </pre>
      </div>

      {/* Formatted context package */}
      <div className="flex flex-col gap-2.5">
        <div className="flex items-center justify-between border-b border-zinc-900 pb-1.5">
          <span className="text-[10px] uppercase tracking-wider text-zinc-300 font-bold">Compiled Grounded Context Text</span>
          <button
            onClick={handleCopyContext}
            className="flex items-center gap-1 text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors cursor-pointer outline-none"
            title="Copy formatted context package"
          >
            {copiedContext ? <Check className="h-3.5 w-3.5 text-emerald-450" /> : <Copy className="h-3.5 w-3.5" />}
            <span>{copiedContext ? "Copied" : "Copy"}</span>
          </button>
        </div>
        <pre className="p-3.5 rounded-xl border border-zinc-900 bg-zinc-950/20 max-h-[220px] overflow-auto text-[10px] text-zinc-350 leading-relaxed whitespace-pre-wrap font-mono">
          {promptPackage.formatted_context}
        </pre>
      </div>

      {/* Citations List */}
      <div className="flex flex-col gap-3">
        <span className="text-[10px] uppercase tracking-wider text-zinc-300 font-bold border-b border-zinc-900 pb-1.5">
          Citations Directory ({promptPackage.citations.length})
        </span>

        {promptPackage.citations.length > 0 ? (
          <div className="flex flex-col gap-2.5">
            {promptPackage.citations.map((cite) => (
              <div
                key={cite.index}
                className="p-3 rounded-lg border border-zinc-900 bg-zinc-955/10 flex flex-col gap-2"
              >
                <div className="flex items-center justify-between gap-3 border-b border-zinc-900/60 pb-1.5 text-[9px] text-zinc-550">
                  <div className="flex items-center gap-1.5">
                    <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-zinc-900 border border-zinc-800 text-[9px] text-zinc-300 font-bold font-mono">
                      {cite.index}
                    </span>
                    <span className="inline-flex items-center gap-0.5 px-1 py-0.25 rounded bg-zinc-900 border border-zinc-850 uppercase tracking-widest text-[8px]">
                      {cite.source_tier}
                    </span>
                    <span className="truncate max-w-[100px]" title={cite.memory_id}>ID: {cite.memory_id.slice(0, 10)}...</span>
                  </div>
                  
                  <div className="flex items-center gap-1.5">
                    <span className="text-emerald-450 font-semibold">{Math.round(cite.relevance_score * 100)}% Match</span>
                    <Link
                      href={`/memories/${cite.memory_id}`}
                      className="p-0.5 rounded bg-zinc-900 hover:bg-zinc-850 text-zinc-550 hover:text-zinc-350 transition-colors cursor-pointer outline-none"
                    >
                      <ExternalLink className="h-3 w-3" />
                    </Link>
                  </div>
                </div>

                <p className="text-zinc-300 font-sans text-xs leading-relaxed leading-normal truncate">
                  {cite.content}
                </p>

                {cite.originating_queries.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-0.5 items-center">
                    <span className="text-[8px] text-zinc-600 uppercase tracking-wider shrink-0">Subqueries:</span>
                    {cite.originating_queries.map((q, idx) => (
                      <span
                        key={idx}
                        className="px-1.5 py-0.25 rounded bg-zinc-900 border border-zinc-900/80 text-[8px] text-zinc-500 font-mono"
                      >
                        {q}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <span className="text-[10px] text-zinc-650 font-mono italic">No citations found.</span>
        )}
      </div>

    </div>
  );
}
