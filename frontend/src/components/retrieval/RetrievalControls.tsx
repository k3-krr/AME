import { useEffect } from "react";
import { useChatStore } from "@/store/chatStore";
import { SlidersHorizontal, Settings, MessageSquare, Terminal } from "lucide-react";

interface RetrievalControlsProps {
  conversationId: string;
  onChangeConversationId: (id: string) => void;
  topK: number;
  onChangeTopK: (k: number) => void;
  maxChars: number;
  onChangeMaxChars: (chars: number) => void;
  basePrompt: string;
  onChangeBasePrompt: (prompt: string) => void;
}

export default function RetrievalControls({
  conversationId,
  onChangeConversationId,
  topK,
  onChangeTopK,
  maxChars,
  onChangeMaxChars,
  basePrompt,
  onChangeBasePrompt,
}: RetrievalControlsProps) {
  const { conversations, fetchConversations } = useChatStore();

  // Load chat conversations cache list on mount if empty
  useEffect(() => {
    if (conversations.length === 0) {
      fetchConversations();
    }
  }, [conversations.length, fetchConversations]);

  return (
    <div className="border border-zinc-900 bg-zinc-950 p-4 rounded-xl flex flex-col gap-4 font-mono text-xs text-zinc-400">
      
      {/* Header title */}
      <div className="flex items-center gap-1.5 text-zinc-300 font-semibold border-b border-zinc-900 pb-2">
        <SlidersHorizontal className="h-4 w-4 text-zinc-550" />
        <span>Retrieval Configurations</span>
      </div>

      <div className="flex flex-col gap-3.5">
        
        {/* Conversation ID select mapping */}
        <div className="flex flex-col gap-1.5">
          <label htmlFor="ret-conv-select" className="text-[9px] text-zinc-550 uppercase tracking-widest flex items-center gap-1">
            <MessageSquare className="h-3.5 w-3.5 text-zinc-650" />
            <span>Map to Conversation Session</span>
          </label>
          <select
            id="ret-conv-select"
            value={conversationId}
            onChange={(e) => onChangeConversationId(e.target.value)}
            className="w-full rounded border border-zinc-850 bg-zinc-950 px-2 py-1.5 outline-none text-zinc-350 transition-colors cursor-pointer"
          >
            <option value="">No Active Conversation Scopes</option>
            {conversations.map((c) => (
              <option key={c.id} value={c.id} className="bg-zinc-950">
                {c.title || `Conversation (${c.id.slice(0, 8)})`}
              </option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-3.5">
          {/* Top_k Limit */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="ret-topk-input" className="text-[9px] text-zinc-555 uppercase tracking-widest flex items-center gap-1">
              <Settings className="h-3.5 w-3.5 text-zinc-650" />
              <span>Limit Hit Count (top_k)</span>
            </label>
            <input
              id="ret-topk-input"
              type="number"
              min="1"
              max="50"
              value={topK}
              onChange={(e) => onChangeTopK(Math.max(1, Number(e.target.value)))}
              className="w-full rounded border border-zinc-850 bg-zinc-950 px-2 py-1 outline-none text-zinc-350 transition-colors font-sans text-xs"
            />
          </div>

          {/* Max Context Chars limit */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="ret-maxchars-input" className="text-[9px] text-zinc-555 uppercase tracking-widest flex items-center gap-1">
              <Terminal className="h-3.5 w-3.5 text-zinc-650" />
              <span>Max context length (chars)</span>
            </label>
            <input
              id="ret-maxchars-input"
              type="number"
              min="100"
              max="20000"
              step="500"
              value={maxChars}
              onChange={(e) => onChangeMaxChars(Math.max(100, Number(e.target.value)))}
              className="w-full rounded border border-zinc-850 bg-zinc-950 px-2 py-1 outline-none text-zinc-350 transition-colors font-sans text-xs"
            />
          </div>
        </div>

        {/* Base system prompt override */}
        <div className="flex flex-col gap-1.5">
          <label htmlFor="ret-sysprompt-input" className="text-[9px] text-zinc-555 uppercase tracking-widest">Base System Prompt Template</label>
          <textarea
            id="ret-sysprompt-input"
            value={basePrompt}
            onChange={(e) => onChangeBasePrompt(e.target.value)}
            placeholder="Define custom instruction template to embed retrieval values..."
            rows={3}
            className="w-full rounded border border-zinc-850 bg-zinc-950 px-2 py-1.5 outline-none text-zinc-350 transition-colors font-sans text-xs resize-none"
          />
        </div>

      </div>

    </div>
  );
}
