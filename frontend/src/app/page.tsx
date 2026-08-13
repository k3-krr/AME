"use client";

import { useState } from "react";
import { 
  Terminal, 
  Sparkles, 
  Send, 
  SlidersHorizontal,
  ChevronDown,
  Cpu,
  Brain,
  HelpCircle
} from "lucide-react";
import { cn } from "@/lib/utils";

export default function Home() {
  const [systemPromptOpen, setSystemPromptOpen] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    
    // Clearly communicate layout-only constraint without fake responses
    setStatusMessage("Conversational stream is disabled in Phase 1 (Presentation Shell Only).");
    setTimeout(() => setStatusMessage(null), 4000);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-zinc-950">
      {/* Workspace Subheader / System Settings Bar */}
      <div className="flex items-center justify-between border-b border-zinc-900/60 bg-zinc-950 px-4 py-2 text-xs text-zinc-500 font-mono">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <Cpu className="h-3.5 w-3.5 text-zinc-600" />
            <span>AME Runtime</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Brain className="h-3.5 w-3.5 text-zinc-600" />
            <span>Memory Architecture: <span className="text-zinc-400">Hybrid</span></span>
          </div>
        </div>
        <div className="hidden sm:flex items-center gap-2">
          <span>Retrieval: <span className="text-zinc-400">Ready for integration</span></span>
        </div>
      </div>

      {/* Main Workspace Frame */}
      <div className="flex-1 flex flex-col justify-between p-4 md:p-6 overflow-y-auto max-w-4xl w-full mx-auto min-h-0">
        
        {/* Top: Introduction Deck & System Configuration */}
        <div className="flex flex-col gap-6 w-full">
          {/* Collapsible System Prompt Configuration Card */}
          <div className="border border-zinc-900 bg-zinc-900/20 rounded-lg overflow-hidden transition-all duration-200">
            <button
              type="button"
              onClick={() => setSystemPromptOpen(!systemPromptOpen)}
              className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-zinc-900/30 transition-colors"
            >
              <div className="flex items-center gap-2.5">
                <SlidersHorizontal className="h-4 w-4 text-zinc-400" />
                <span className="text-xs font-semibold text-zinc-300 tracking-tight">System Prompt Configuration</span>
              </div>
              <ChevronDown className={cn("h-4 w-4 text-zinc-500 transition-transform duration-200", systemPromptOpen && "transform rotate-180")} />
            </button>
            
            {systemPromptOpen && (
              <div className="border-t border-zinc-900 p-4 bg-zinc-950/40">
                <p className="text-xs text-zinc-500 leading-relaxed mb-3">
                  This prompt controls the underlying context instruction sent to the LLM agent. It will be sent alongside retrieved memories in Phase 3.
                </p>
                <textarea
                  className="w-full rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs font-mono text-zinc-300 outline-none focus:border-zinc-700 h-16 resize-none"
                  defaultValue="You are an assistant equipped with an Adaptive Memory Engine. Synthesize retrieved episodic context to deliver grounded responses."
                  readOnly
                />
              </div>
            )}
          </div>

          {/* Onboarding Overview Panel */}
          <div className="border border-zinc-900 bg-zinc-950 rounded-xl p-5 md:p-6 flex flex-col gap-5 mt-4">
            <div className="flex items-start gap-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-200">
                <Sparkles className="h-5 w-5 text-zinc-400" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-zinc-200 tracking-tight">AME Conversational Workspace</h3>
                <p className="text-xs text-zinc-500 mt-1 leading-relaxed">
                  This workspace serves as the primary conversational playground. In Phase 3, it will stream completions and integrate the context builder loop.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 border-t border-zinc-900 pt-5">
              <div className="flex gap-3">
                <Terminal className="h-4 w-4 text-zinc-600 shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-xs font-semibold text-zinc-300">Context Enrichment</h4>
                  <p className="text-[11px] text-zinc-500 mt-1 leading-normal">
                    Queries are processed through the `ContextBuilder` which injects relevant past entities and memories before prompt inference.
                  </p>
                </div>
              </div>
              <div className="flex gap-3">
                <Brain className="h-4 w-4 text-zinc-600 shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-xs font-semibold text-zinc-300">Continuous Consolidation</h4>
                  <p className="text-[11px] text-zinc-500 mt-1 leading-normal">
                    Conversations trigger asynchronous extraction routines to log new episodic concepts and save memories dynamically.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom: Prompt Input Box & Controls */}
        <div className="mt-8 w-full flex flex-col gap-3">
          {/* Notification toast */}
          {statusMessage && (
            <div className="mx-auto px-3.5 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-[11px] font-mono text-zinc-400 shadow-lg text-center transition-all duration-200">
              {statusMessage}
            </div>
          )}

          <form onSubmit={handleSubmit} className="relative rounded-xl border border-zinc-800/80 bg-zinc-900/20 focus-within:border-zinc-700/80 transition-colors p-3">
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Enter your prompt here... (Conversational stream will be implemented in Phase 3)"
              className="w-full min-h-[80px] bg-transparent border-0 resize-none text-sm text-zinc-200 placeholder-zinc-500 outline-none focus:ring-0"
              maxLength={2000}
            />
            
            <div className="flex items-center justify-between border-t border-zinc-900/60 pt-2.5 mt-1.5">
              <div className="flex items-center gap-1">
                <span className="text-[10px] text-zinc-600 font-mono">Press Enter to send, Shift+Enter for new line</span>
              </div>

              <button
                type="submit"
                disabled={!prompt.trim()}
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-lg border transition-all duration-200 outline-none",
                  prompt.trim()
                    ? "bg-zinc-100 border-zinc-100 text-zinc-950 cursor-pointer hover:bg-zinc-200"
                    : "bg-transparent border-zinc-850 text-zinc-600 cursor-not-allowed"
                )}
                aria-label="Submit prompt"
              >
                <Send className="h-3.5 w-3.5" />
              </button>
            </div>
          </form>

          <div className="flex items-center justify-center gap-1.5 text-[10px] text-zinc-600 font-mono">
            <HelpCircle className="h-3.5 w-3.5 text-zinc-700" />
            <span>Adaptive Memory Engine Layout Preview (Phase 1)</span>
          </div>
        </div>

      </div>
    </div>
  );
}
