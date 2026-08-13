import { useState } from "react";
import { QueryRewriteResult } from "@/types";
import { Copy, Check } from "lucide-react";

interface QueryRewritePanelProps {
  rewriteResult: QueryRewriteResult | null;
}

export default function QueryRewritePanel({ rewriteResult }: QueryRewritePanelProps) {
  const [copiedRewrite, setCopiedRewrite] = useState(false);

  if (!rewriteResult) {
    return (
      <div className="py-20 text-center font-mono text-xs text-zinc-650">
        No query rewriting diagnostic performed yet.
      </div>
    );
  }

  const handleCopyRewrite = () => {
    navigator.clipboard.writeText(rewriteResult.rewritten_query);
    setCopiedRewrite(true);
    setTimeout(() => setCopiedRewrite(false), 2000);
  };

  return (
    <div className="flex flex-col gap-6 font-mono text-xs text-zinc-400">
      
      {/* Rewritten query output */}
      <div className="flex flex-col gap-2.5">
        <div className="flex items-center justify-between border-b border-zinc-900 pb-1.5">
          <span className="text-[10px] uppercase tracking-wider text-zinc-300 font-bold">Rewritten Target Query</span>
          <button
            onClick={handleCopyRewrite}
            className="flex items-center gap-1 text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors cursor-pointer outline-none"
            title="Copy rewritten query text"
          >
            {copiedRewrite ? <Check className="h-3.5 w-3.5 text-emerald-450" /> : <Copy className="h-3.5 w-3.5" />}
            <span>{copiedRewrite ? "Copied" : "Copy"}</span>
          </button>
        </div>
        <p className="text-zinc-200 text-xs font-sans leading-relaxed p-3.5 border border-zinc-900 rounded-xl bg-zinc-955/20 font-medium">
          {rewriteResult.rewritten_query || "N/A"}
        </p>
      </div>

      {/* Subqueries listing */}
      <div className="flex flex-col gap-3">
        <span className="text-[10px] uppercase tracking-wider text-zinc-300 font-bold border-b border-zinc-900 pb-1.5">
          Subqueries & Parallel Retrieval Routes ({rewriteResult.retrieval_queries.length})
        </span>

        {rewriteResult.retrieval_queries.length > 0 ? (
          <div className="flex flex-col gap-3">
            {rewriteResult.retrieval_queries.map((sub, idx) => {
              const priorityPercent = Math.round(sub.priority * 100);
              
              return (
                <div
                  key={idx}
                  className="p-3.5 rounded-lg border border-zinc-900 bg-zinc-950/20 flex flex-col gap-2.5"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 text-[9px] text-zinc-550 border-b border-zinc-900/60 pb-1.5">
                    <div className="flex items-center gap-1.5">
                      <span className="inline-flex h-4.5 w-4.5 items-center justify-center rounded-full bg-zinc-900 border border-zinc-800 text-[9px] text-zinc-400 font-bold font-mono">
                        #{idx + 1}
                      </span>
                      <span className="inline-flex items-center gap-0.5 px-1 py-0.25 rounded bg-zinc-900 border border-zinc-850 uppercase tracking-widest text-[8px]">
                        {sub.source}
                      </span>
                    </div>
                    <span className="text-emerald-450 font-semibold">{priorityPercent}% Priority Weight</span>
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <span className="text-zinc-600 uppercase text-[8px] tracking-wider">Subquery Prompt</span>
                    <p className="text-zinc-300 font-sans text-xs leading-normal font-medium">
                      {sub.query}
                    </p>
                  </div>

                  {sub.reason && (
                    <div className="flex flex-col gap-1.5 border-t border-zinc-900/50 pt-2 mt-0.5">
                      <span className="text-zinc-600 uppercase text-[8px] tracking-wider font-mono">Generation Reasoning Context</span>
                      <p className="text-zinc-450 font-sans text-xs leading-normal">
                        {sub.reason}
                      </p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <span className="text-[10px] text-zinc-650 font-mono italic">No subqueries generated.</span>
        )}
      </div>

      {/* Metadata settings */}
      {Object.keys(rewriteResult.metadata).length > 0 && (
        <div className="flex flex-col gap-2 border-t border-zinc-900 pt-4">
          <span className="text-[9px] text-zinc-550 uppercase tracking-wider font-mono">Execution Metadata</span>
          <pre className="p-3 rounded-lg border border-zinc-900 bg-zinc-950/20 max-h-[160px] overflow-auto text-[10px] text-zinc-400 leading-normal font-mono">
            {JSON.stringify(rewriteResult.metadata, null, 2)}
          </pre>
        </div>
      )}

    </div>
  );
}
