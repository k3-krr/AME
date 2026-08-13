import { QueryAnalysisResult } from "@/types";
import { Compass } from "lucide-react";

interface QueryAnalysisPanelProps {
  analysisResult: QueryAnalysisResult | null;
}

export default function QueryAnalysisPanel({ analysisResult }: QueryAnalysisPanelProps) {
  if (!analysisResult) {
    return (
      <div className="py-20 text-center font-mono text-xs text-zinc-650">
        No query analysis performed yet.
      </div>
    );
  }

  const { original_query, normalized_query, retrieval_plan } = analysisResult;
  const confidencePercent = Math.round(retrieval_plan.confidence * 100);

  return (
    <div className="flex flex-col gap-5 font-mono text-xs text-zinc-400">
      
      {/* 1. Comparison view */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Original Query */}
        <div className="flex flex-col gap-1.5 p-3 rounded-lg border border-zinc-900 bg-zinc-950/20">
          <span className="text-[9px] text-zinc-600 uppercase tracking-widest">Original Input Query</span>
          <p className="text-zinc-350 text-xs font-sans leading-relaxed">{original_query}</p>
        </div>

        {/* Normalized Query */}
        <div className="flex flex-col gap-1.5 p-3 rounded-lg border border-zinc-900 bg-zinc-950/20">
          <span className="text-[9px] text-zinc-600 uppercase tracking-widest font-bold">Normalized Form</span>
          <p className="text-zinc-300 text-xs font-sans leading-relaxed">{normalized_query || "N/A"}</p>
        </div>
      </div>

      {/* 2. Intent Details */}
      <div className="border border-zinc-900 bg-zinc-950/20 p-4 rounded-xl flex flex-col gap-3">
        <div className="flex items-center gap-1.5 text-zinc-300 font-semibold border-b border-zinc-900 pb-2">
          <Compass className="h-4 w-4 text-zinc-550" />
          <span>Intent Classification Package</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-y-3.5 gap-x-6 text-[11px] mt-1">
          {/* Detected Intent */}
          <div className="flex flex-col gap-1">
            <span className="text-zinc-600 uppercase text-[9px] tracking-wider">Detected Intent category</span>
            <span className="text-zinc-200 font-semibold text-xs tracking-tight">{retrieval_plan.intent || "GENERAL_QUERY"}</span>
          </div>

          {/* Confidence Slider */}
          <div className="flex flex-col gap-1">
            <div className="flex justify-between items-center text-[9px] text-zinc-600 uppercase tracking-wider">
              <span>Intent Confidence</span>
              <span className="text-emerald-400 font-bold">{confidencePercent}%</span>
            </div>
            <div className="w-full bg-zinc-900 rounded-full h-1.5 mt-1 border border-zinc-900/60 overflow-hidden">
              <div 
                className="bg-emerald-500 h-1.5 rounded-full" 
                style={{ width: `${confidencePercent}%` }} 
              />
            </div>
          </div>
        </div>

        {/* Recommended Capabilities */}
        <div className="flex flex-col gap-1.5 border-t border-zinc-900/80 pt-3.5 mt-1.5">
          <span className="text-zinc-600 uppercase text-[9px] tracking-wider">Recommended Search Capabilities</span>
          {retrieval_plan.recommended_capabilities.length > 0 ? (
            <div className="flex flex-wrap gap-1.5 mt-0.5">
              {retrieval_plan.recommended_capabilities.map((cap, idx) => (
                <span
                  key={idx}
                  className="px-2.5 py-0.5 rounded-lg border border-zinc-850 bg-zinc-900/40 text-[10px] text-zinc-300 font-mono font-semibold"
                >
                  {cap}
                </span>
              ))}
            </div>
          ) : (
            <span className="text-[10px] text-zinc-650 font-mono italic">No special retrieval capabilities identified.</span>
          )}
        </div>
      </div>

      {/* 3. Reason/Plan Metadata */}
      {Object.keys(retrieval_plan.metadata).length > 0 && (
        <div className="flex flex-col gap-2 border-t border-zinc-900 pt-4">
          <span className="text-[9px] text-zinc-550 uppercase tracking-wider">Reasoning Plan Metadata</span>
          <pre className="p-3 rounded-lg border border-zinc-900 bg-zinc-950/20 max-h-[160px] overflow-auto text-[10px] text-zinc-400 leading-normal font-mono">
            {JSON.stringify(retrieval_plan.metadata, null, 2)}
          </pre>
        </div>
      )}

    </div>
  );
}
