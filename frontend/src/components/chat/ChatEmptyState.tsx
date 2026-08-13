import { Brain, MessageSquare, Sparkles, Terminal } from "lucide-react";

interface ChatEmptyStateProps {
  onCreateNew: () => void;
}

export default function ChatEmptyState({ onCreateNew }: ChatEmptyStateProps) {
  return (
    <div className="flex-1 flex flex-col justify-center items-center p-6 text-center max-w-2xl mx-auto my-auto min-h-[50vh]">
      {/* Sparkles premium brand node */}
      <div className="h-12 w-12 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-300 shadow-md mb-6">
        <Sparkles className="h-6 w-6 text-zinc-400" />
      </div>

      <h2 className="text-lg font-bold text-zinc-100 tracking-tight">
        AME Conversational Playground
      </h2>
      <p className="text-xs text-zinc-500 mt-2 max-w-md leading-relaxed">
        Establish a conversation canvas to interact with the cognitive agent. Your messages trigger real-time semantic retrieval context enrichment.
      </p>

      {/* Action initialize trigger */}
      <button
        onClick={onCreateNew}
        className="mt-6 flex items-center gap-1.5 px-4 py-2 rounded-lg bg-zinc-100 hover:bg-zinc-200 text-zinc-950 text-xs font-semibold tracking-tight transition-colors cursor-pointer outline-none shadow-sm"
      >
        <MessageSquare className="h-4 w-4" />
        <span>Create Conversation</span>
      </button>

      {/* Feature explanations */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 border-t border-zinc-900 pt-8 mt-8 w-full text-left">
        <div className="flex gap-3 border border-zinc-900 bg-zinc-950/40 p-4 rounded-xl">
          <Terminal className="h-4.5 w-4.5 text-zinc-650 shrink-0 mt-0.5" />
          <div>
            <h4 className="text-xs font-semibold text-zinc-300">Context Enrichment</h4>
            <p className="text-[11px] text-zinc-500 mt-1 leading-normal font-sans">
              As you prompt, the `ContextBuilder` pipeline performs semantic lookups to retrieve relevant factual logs and past facts.
            </p>
          </div>
        </div>

        <div className="flex gap-3 border border-zinc-900 bg-zinc-950/40 p-4 rounded-xl">
          <Brain className="h-4.5 w-4.5 text-zinc-650 shrink-0 mt-0.5" />
          <div>
            <h4 className="text-xs font-semibold text-zinc-300">Continuous Ingestion</h4>
            <p className="text-[11px] text-zinc-500 mt-1 leading-normal font-sans">
              After messages are processed, extraction workers run asynchronous text extraction routines to discover and save new memories.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
