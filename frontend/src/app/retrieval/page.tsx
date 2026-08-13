import { Search, Settings2 } from "lucide-react";

export default function RetrievalPage() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 text-center max-w-2xl mx-auto">
      <div className="h-12 w-12 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-400 mb-4">
        <Search className="h-6 w-6" />
      </div>
      <h1 className="text-lg font-semibold text-zinc-200 tracking-tight">Retrieval & Grounding Playground</h1>
      <p className="text-sm text-zinc-500 mt-2 max-w-sm">
        Experiment with hybrid query routing, semantic weight sliders, context synthesis, and prompt grounding.
      </p>
      <div className="mt-6 flex items-center gap-2 px-3 py-1 rounded-full bg-zinc-900/50 border border-zinc-800/60 text-[11px] text-zinc-400 font-mono">
        <Settings2 className="h-3.5 w-3.5 text-zinc-500" />
        <span>Phase 6: Grounding Optimization & Weights</span>
      </div>
    </div>
  );
}
