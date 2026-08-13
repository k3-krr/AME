import { useState } from "react";
import { Search, Route, AlignLeft, Sparkles, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface RetrievalQueryPanelProps {
  query: string;
  onChangeQuery: (q: string) => void;
  onRetrieve: () => Promise<void>;
  onGround: () => Promise<void>;
  onAnalyze: () => Promise<void>;
  onRewrite: () => Promise<void>;
  isLoading: boolean;
}

export default function RetrievalQueryPanel({
  query,
  onChangeQuery,
  onRetrieve,
  onGround,
  onAnalyze,
  onRewrite,
  isLoading,
}: RetrievalQueryPanelProps) {
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleQueryChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    if (val.length > 5000) {
      setErrorMsg("Query length exceeds the maximum limit of 5000 characters.");
      onChangeQuery(val.slice(0, 5000));
    } else {
      setErrorMsg(null);
      onChangeQuery(val);
    }
  };

  const handleClear = () => {
    onChangeQuery("");
    setErrorMsg(null);
  };

  const isEnabled = query.trim().length > 0;

  return (
    <div className="flex flex-col gap-4 font-mono text-xs text-zinc-400">
      
      {/* Label and Clear buttons */}
      <div className="flex items-center justify-between border-b border-zinc-900 pb-2">
        <span className="text-[10px] uppercase tracking-wider text-zinc-550 font-bold">Query Composer</span>
        {query && (
          <button
            onClick={handleClear}
            className="flex items-center gap-1 text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors cursor-pointer outline-none"
            title="Clear prompt query text"
          >
            <X className="h-3.5 w-3.5" />
            <span>Clear Text</span>
          </button>
        )}
      </div>

      {/* Main Textarea */}
      <div className="relative">
        <textarea
          value={query}
          onChange={handleQueryChange}
          placeholder="Enter a test query to inspect AME retrieval logic, subqueries mapping, Dijkstra paths, or compile grounded context... (e.g. Find all Python frameworks used in the console project)"
          rows={5}
          maxLength={5100}
          className="w-full rounded-lg border border-zinc-800 bg-zinc-905/30 px-3.5 py-3 text-sm text-zinc-200 placeholder-zinc-600 outline-none focus:border-zinc-700 transition-colors resize-none font-sans leading-relaxed"
          disabled={isLoading}
        />
        <div className="absolute bottom-2.5 right-3 text-[9px] text-zinc-600 select-none">
          {query.length} / 5000
        </div>
      </div>

      {errorMsg && (
        <span className="text-[10px] text-red-400 font-mono leading-none">{errorMsg}</span>
      )}

      {/* Actions grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-1">
        
        {/* Context retrieve */}
        <button
          onClick={onRetrieve}
          disabled={!isEnabled || isLoading}
          className={cn(
            "py-2 px-3 rounded-lg border font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer outline-none text-[11px]",
            isEnabled && !isLoading
              ? "bg-zinc-900 border-zinc-800 text-zinc-300 hover:bg-zinc-850 hover:text-zinc-100"
              : "bg-zinc-950 border-zinc-900/60 text-zinc-650 cursor-not-allowed"
          )}
        >
          <Search className="h-3.5 w-3.5" />
          <span>Retrieve Context</span>
        </button>

        {/* E2E ground */}
        <button
          onClick={onGround}
          disabled={!isEnabled || isLoading}
          className={cn(
            "py-2 px-3 rounded-lg border font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer outline-none text-[11px]",
            isEnabled && !isLoading
              ? "bg-zinc-100 border-zinc-200 text-zinc-950 hover:bg-zinc-200"
              : "bg-zinc-950 border-zinc-900/60 text-zinc-650 cursor-not-allowed"
          )}
        >
          <Sparkles className="h-3.5 w-3.5" />
          <span>Ground Prompt</span>
        </button>

        {/* Analyze Query */}
        <button
          onClick={onAnalyze}
          disabled={!isEnabled || isLoading}
          className={cn(
            "py-2 px-3 rounded-lg border font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer outline-none text-[11px]",
            isEnabled && !isLoading
              ? "bg-zinc-900 border-zinc-800 text-zinc-400 hover:bg-zinc-850 hover:text-zinc-255"
              : "bg-zinc-950 border-zinc-900/60 text-zinc-650 cursor-not-allowed"
          )}
        >
          <AlignLeft className="h-3.5 w-3.5 text-zinc-550" />
          <span>Analyze Query</span>
        </button>

        {/* Rewrite Query */}
        <button
          onClick={onRewrite}
          disabled={!isEnabled || isLoading}
          className={cn(
            "py-2 px-3 rounded-lg border font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer outline-none text-[11px]",
            isEnabled && !isLoading
              ? "bg-zinc-900 border-zinc-800 text-zinc-400 hover:bg-zinc-850 hover:text-zinc-255"
              : "bg-zinc-950 border-zinc-900/60 text-zinc-650 cursor-not-allowed"
          )}
        >
          <Route className="h-3.5 w-3.5 text-zinc-550" />
          <span>Rewrite Query</span>
        </button>
      </div>

    </div>
  );
}
