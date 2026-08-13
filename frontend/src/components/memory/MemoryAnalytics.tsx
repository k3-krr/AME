import { MemoryAnalytics } from "@/types";
import { Activity, Clock, FileText } from "lucide-react";

interface MemoryAnalyticsViewProps {
  analytics: MemoryAnalytics;
}

export default function MemoryAnalyticsView({ analytics }: MemoryAnalyticsViewProps) {
  const { state, access_logs } = analytics;

  // Format dates
  const formatTime = (timeStr?: string | null) => {
    if (!timeStr) return "Never";
    return new Date(timeStr).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className="flex flex-col gap-6">
      {/* 1. Core State Metrics */}
      {state ? (
        <div className="flex flex-col gap-4">
          <h3 className="text-xs font-mono uppercase tracking-wider text-zinc-550 flex items-center gap-1.5">
            <Activity className="h-3.5 w-3.5 text-zinc-600" />
            <span>State Metrics</span>
          </h3>
          
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="border border-zinc-900 bg-zinc-950 p-3.5 rounded-lg flex flex-col gap-1">
              <span className="text-[10px] font-mono text-zinc-500 uppercase">Access Count</span>
              <span className="text-lg font-semibold text-zinc-200">{state.access_count}</span>
            </div>
            
            <div className="border border-zinc-900 bg-zinc-950 p-3.5 rounded-lg flex flex-col gap-1">
              <span className="text-[10px] font-mono text-zinc-500 uppercase">Retrievals</span>
              <span className="text-lg font-semibold text-zinc-200">{state.retrieval_count}</span>
            </div>

            <div className="border border-zinc-900 bg-zinc-950 p-3.5 rounded-lg flex flex-col gap-1">
              <span className="text-[10px] font-mono text-zinc-500 uppercase">Reinforcements</span>
              <span className="text-lg font-semibold text-zinc-200">{state.reinforcement_count}</span>
            </div>

            <div className="border border-zinc-900 bg-zinc-950 p-3.5 rounded-lg flex flex-col gap-1">
              <span className="text-[10px] font-mono text-zinc-500 uppercase">Decay Score</span>
              <span className="text-lg font-semibold text-zinc-200">{state.decay_score.toFixed(4)}</span>
            </div>
          </div>

          <div className="border border-zinc-900 bg-zinc-950 p-4 rounded-lg mt-1 text-xs font-mono text-zinc-400 flex flex-col gap-2.5">
            <div className="flex items-center justify-between">
              <span className="text-zinc-500">Source Type:</span>
              <span className="text-zinc-200 uppercase">{state.source_type}</span>
            </div>
            <div className="flex items-center justify-between border-t border-zinc-900 pt-2">
              <span className="text-zinc-500">Last Accessed:</span>
              <span className="text-zinc-200">{formatTime(state.last_accessed_at)}</span>
            </div>
            <div className="flex items-center justify-between border-t border-zinc-900 pt-2">
              <span className="text-zinc-500">Last Reinforced:</span>
              <span className="text-zinc-200">{formatTime(state.last_reinforced_at)}</span>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-4 border border-dashed border-zinc-900 rounded-lg text-center text-xs text-zinc-500 font-mono">
          No metrics state initialized for this memory.
        </div>
      )}

      {/* 2. Access Log Sheet */}
      <div className="flex flex-col gap-3">
        <h3 className="text-xs font-mono uppercase tracking-wider text-zinc-550 flex items-center gap-1.5">
          <FileText className="h-3.5 w-3.5 text-zinc-600" />
          <span>Access Logs ({access_logs.length})</span>
        </h3>

        {access_logs.length > 0 ? (
          <div className="border border-zinc-900 rounded-lg overflow-x-auto bg-zinc-950/20">
            <table className="w-full text-left text-xs font-mono border-collapse min-w-[500px]">
              <thead>
                <tr className="border-b border-zinc-900 bg-zinc-950 text-zinc-500 text-[10px] uppercase">
                  <th className="px-4 py-2.5">Timestamp</th>
                  <th className="px-4 py-2.5">Similarity</th>
                  <th className="px-4 py-2.5">Ranking Score</th>
                  <th className="px-4 py-2.5">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-900/60">
                {access_logs.map((log) => (
                  <tr key={log.id} className="hover:bg-zinc-900/10 text-zinc-300">
                    <td className="px-4 py-2 flex items-center gap-1.5 text-zinc-400">
                      <Clock className="h-3 w-3 text-zinc-600" />
                      <span>{formatTime(log.timestamp)}</span>
                    </td>
                    <td className="px-4 py-2 font-semibold">
                      {log.similarity_score.toFixed(4)}
                    </td>
                    <td className="px-4 py-2">
                      {log.ranking_score.toFixed(4)}
                    </td>
                    <td className="px-4 py-2">
                      <span className={`inline-flex px-1.5 py-0.5 rounded text-[10px] ${log.retrieval_success ? 'bg-emerald-950/30 text-emerald-400 border border-emerald-900/30' : 'bg-red-950/30 text-red-400 border border-red-900/30'}`}>
                        {log.retrieval_success ? "Success" : "Failed"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8 border border-zinc-900 rounded-lg text-center text-xs text-zinc-500 font-mono">
            No retrieval access logs recorded.
          </div>
        )}
      </div>
    </div>
  );
}
