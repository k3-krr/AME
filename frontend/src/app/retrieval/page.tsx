"use client";

import { useState } from "react";
import { useRetrievalStore } from "@/store/retrievalStore";
import RetrievalQueryPanel from "@/components/retrieval/RetrievalQueryPanel";
import RetrievalControls from "@/components/retrieval/RetrievalControls";
import RetrievalResults from "@/components/retrieval/RetrievalResults";
import GroundingPanel from "@/components/retrieval/GroundingPanel";
import QueryAnalysisPanel from "@/components/retrieval/QueryAnalysisPanel";
import QueryRewritePanel from "@/components/retrieval/QueryRewritePanel";
import { 
  Compass, 
  Layers, 
  Sparkles, 
  Quote, 
  Activity, 
  HelpCircle,
  Clock,
  Terminal,
  AlignLeft,
  Loader2
} from "lucide-react";
import { cn } from "@/lib/utils";

type ActiveTabType = "fused" | "prompt" | "citations" | "analyze" | "rewrite";

export default function RetrievalPlaygroundPage() {
  const {
    query,
    contextPackage,
    promptPackage,
    analysisResult,
    rewriteResult,
    isLoading,
    error,
    setQuery,
    executeRetrieve,
    executeGround,
    executeAnalyze,
    executeRewrite,
  } = useRetrievalStore();

  // Settings states
  const [conversationId, setConversationId] = useState("");
  const [topK, setTopK] = useState(5);
  const [maxChars, setMaxChars] = useState(4000);
  const [basePrompt, setBasePrompt] = useState("");

  // Tab control
  const [activeTab, setActiveTab] = useState<ActiveTabType>("fused");

  const handleRetrieve = async () => {
    setActiveTab("fused");
    await executeRetrieve(conversationId || null, {
      top_k: topK,
      max_context_chars: maxChars,
      base_system_prompt: basePrompt || undefined,
    });
  };

  const handleGround = async () => {
    setActiveTab("prompt");
    await executeGround(conversationId || null, {
      top_k: topK,
      max_context_chars: maxChars,
      base_system_prompt: basePrompt || undefined,
    });
  };

  const handleAnalyze = async () => {
    setActiveTab("analyze");
    await executeAnalyze();
  };

  const handleRewrite = async () => {
    setActiveTab("rewrite");
    await executeRewrite();
  };

  // Compile active execution details (telemetry)
  const activePackage = activeTab === "fused" ? contextPackage : promptPackage;
  const requestId = activePackage?.request_id || null;
  const compiledAt = activePackage?.compiled_at ? new Date(activePackage.compiled_at).toLocaleString() : null;
  const executionStatus = activePackage?.status || null;

  return (
    <div className="flex-1 flex flex-col md:flex-row min-h-0 bg-zinc-950">
      
      {/* 1. Left Panel: Query Input & Settings */}
      <div className="w-full md:w-80 border-b md:border-b-0 md:border-r border-zinc-900 bg-zinc-955/20 flex flex-col p-4 gap-4 shrink-0 overflow-y-auto">
        
        {/* Title Block */}
        <div className="border-b border-zinc-900 pb-3">
          <h1 className="text-sm font-semibold text-zinc-200 tracking-tight flex items-center gap-2">
            <Compass className="h-4.5 w-4.5 text-zinc-400" />
            <span>Retrieval Playground</span>
          </h1>
          <p className="text-[10px] text-zinc-650 font-mono mt-0.5">Diagnose and ground context prompts</p>
        </div>

        {/* Text Input Panel */}
        <RetrievalQueryPanel
          query={query}
          onChangeQuery={setQuery}
          onRetrieve={handleRetrieve}
          onGround={handleGround}
          onAnalyze={handleAnalyze}
          onRewrite={handleRewrite}
          isLoading={isLoading}
        />

        {/* Options Configurations */}
        <div className="mt-2 shrink-0">
          <RetrievalControls
            conversationId={conversationId}
            onChangeConversationId={setConversationId}
            topK={topK}
            onChangeTopK={setTopK}
            maxChars={maxChars}
            onChangeMaxChars={setMaxChars}
            basePrompt={basePrompt}
            onChangeBasePrompt={setBasePrompt}
          />
        </div>
      </div>

      {/* 2. Center Panel: Output Viewer Tabbed deck */}
      <div className="flex-1 flex flex-col p-4 md:p-6 gap-5 min-h-0 border-b md:border-b-0 md:border-r border-zinc-900">
        
        {/* Tabs Control Header */}
        <div className="flex border-b border-zinc-900 gap-1.5 overflow-x-auto pb-px scrollbar-none shrink-0 font-mono text-[10px] uppercase font-semibold">
          
          {/* Tab 1: Fused Elements */}
          <button
            onClick={() => setActiveTab("fused")}
            className={cn(
              "px-3.5 py-2 border-b-2 -mb-px transition-colors cursor-pointer outline-none flex items-center gap-1.5 shrink-0 whitespace-nowrap",
              activeTab === "fused"
                ? "border-zinc-200 text-zinc-100"
                : "border-transparent text-zinc-550 hover:text-zinc-350"
            )}
          >
            <Layers className="h-3.5 w-3.5" />
            <span>Fused Elements</span>
            {contextPackage?.fused_elements && (
              <span className="text-[9px] font-bold text-zinc-600 px-1 py-0.25 bg-zinc-900 rounded border border-zinc-850 shrink-0">
                {contextPackage.fused_elements.length}
              </span>
            )}
          </button>

          {/* Tab 2: Grounded Prompt */}
          <button
            onClick={() => setActiveTab("prompt")}
            className={cn(
              "px-3.5 py-2 border-b-2 -mb-px transition-colors cursor-pointer outline-none flex items-center gap-1.5 shrink-0 whitespace-nowrap",
              activeTab === "prompt"
                ? "border-zinc-200 text-zinc-100"
                : "border-transparent text-zinc-550 hover:text-zinc-350"
            )}
          >
            <Sparkles className="h-3.5 w-3.5" />
            <span>Grounded Prompt</span>
          </button>

          {/* Tab 3: Citations */}
          <button
            onClick={() => setActiveTab("citations")}
            className={cn(
              "px-3.5 py-2 border-b-2 -mb-px transition-colors cursor-pointer outline-none flex items-center gap-1.5 shrink-0 whitespace-nowrap",
              activeTab === "citations"
                ? "border-zinc-200 text-zinc-100"
                : "border-transparent text-zinc-550 hover:text-zinc-350"
            )}
          >
            <Quote className="h-3.5 w-3.5" />
            <span>Citations</span>
            {promptPackage?.citations && (
              <span className="text-[9px] font-bold text-zinc-600 px-1 py-0.25 bg-zinc-900 rounded border border-zinc-850 shrink-0">
                {promptPackage.citations.length}
              </span>
            )}
          </button>

          {/* Tab 4: Query Analysis */}
          <button
            onClick={() => setActiveTab("analyze")}
            className={cn(
              "px-3.5 py-2 border-b-2 -mb-px transition-colors cursor-pointer outline-none flex items-center gap-1.5 shrink-0 whitespace-nowrap",
              activeTab === "analyze"
                ? "border-zinc-200 text-zinc-100"
                : "border-transparent text-zinc-550 hover:text-zinc-350"
            )}
          >
            <AlignLeft className="h-3.5 w-3.5" />
            <span>Query Analysis</span>
          </button>

          {/* Tab 5: Query Rewrite */}
          <button
            onClick={() => setActiveTab("rewrite")}
            className={cn(
              "px-3.5 py-2 border-b-2 -mb-px transition-colors cursor-pointer outline-none flex items-center gap-1.5 shrink-0 whitespace-nowrap",
              activeTab === "rewrite"
                ? "border-zinc-200 text-zinc-100"
                : "border-transparent text-zinc-550 hover:text-zinc-350"
            )}
          >
            <Terminal className="h-3.5 w-3.5" />
            <span>Query Rewrite</span>
          </button>
        </div>

        {/* Tab content display viewport */}
        <div className="flex-1 overflow-y-auto pr-1">
          {isLoading ? (
            <div className="py-24 flex flex-col items-center justify-center gap-3">
              <Loader2 className="h-6 w-6 text-zinc-700 animate-spin" />
              <span className="font-mono text-xs text-zinc-550 animate-pulse">Retrieving context...</span>
            </div>
          ) : (
            <>
              {/* Tab 1: Fused Elements */}
              {activeTab === "fused" && (
                contextPackage ? (
                  <RetrievalResults elements={contextPackage.fused_elements} />
                ) : (
                  <div className="py-24 text-center font-mono text-xs text-zinc-650">
                    No retrieval executed yet. Run &quot;Retrieve Context&quot; to populate elements.
                  </div>
                )
              )}

              {/* Tab 2: Grounded Prompt */}
              {activeTab === "prompt" && (
                <GroundingPanel promptPackage={promptPackage} />
              )}

              {/* Tab 3: Citations */}
              {activeTab === "citations" && (
                promptPackage ? (
                  <GroundingPanel promptPackage={promptPackage} />
                ) : (
                  <div className="py-24 text-center font-mono text-xs text-zinc-650">
                    No citations computed. Run &quot;Ground Prompt&quot; to retrieve citations.
                  </div>
                )
              )}

              {/* Tab 4: Query Analysis */}
              {activeTab === "analyze" && (
                <QueryAnalysisPanel analysisResult={analysisResult} />
              )}

              {/* Tab 5: Query Rewrite */}
              {activeTab === "rewrite" && (
                <QueryRewritePanel rewriteResult={rewriteResult} />
              )}
            </>
          )}
        </div>
      </div>

      {/* 3. Right Panel: Execution Telemetry details */}
      <div className="w-full md:w-80 bg-zinc-950 flex flex-col p-4 gap-4 shrink-0 overflow-y-auto">
        <div className="flex flex-col gap-4 font-mono text-xs text-zinc-400">
          
          <div className="flex items-center gap-1.5 text-zinc-300 font-semibold border-b border-zinc-900 pb-2 shrink-0">
            <Clock className="h-4 w-4 text-zinc-550" />
            <span>Execution Telemetry</span>
          </div>

          {requestId ? (
            <div className="flex flex-col gap-4">
              
              {/* Timing & Stats logs */}
              <div className="flex flex-col gap-2.5 p-3 rounded-lg border border-zinc-900 bg-zinc-950/20">
                <div className="flex flex-col gap-0.5">
                  <span className="text-[9px] text-zinc-650 uppercase tracking-wider">Request ID</span>
                  <span className="text-zinc-350 text-[10px] break-all select-all">{requestId}</span>
                </div>
                
                <div className="flex items-center justify-between border-t border-zinc-900 pt-2 mt-1">
                  <span className="text-zinc-650">Execution Status:</span>
                  <span className="text-emerald-500 font-bold uppercase tracking-wider text-[10px]">
                    {executionStatus || "SUCCESS"}
                  </span>
                </div>

                <div className="flex items-center justify-between border-t border-zinc-900 pt-2 mt-1">
                  <span className="text-zinc-650">Compiled At:</span>
                  <span className="text-zinc-300 text-[10px]">{compiledAt}</span>
                </div>
              </div>

              {/* Mapped parameters options preview */}
              <div className="flex flex-col gap-2 border-t border-zinc-900 pt-4">
                <span className="text-[9px] text-zinc-550 uppercase tracking-widest">Options Payload</span>
                <pre className="p-3 rounded-lg border border-zinc-900 bg-zinc-950/20 text-[10px] text-zinc-450 leading-normal overflow-auto max-h-[165px]">
                  {JSON.stringify({
                    top_k: topK,
                    max_context_chars: maxChars,
                    conversation_id: conversationId || null,
                    base_system_prompt: basePrompt || null,
                  }, null, 2)}
                </pre>
              </div>

            </div>
          ) : (
            <div className="flex-grow flex flex-col items-center justify-center text-center p-6 my-auto text-zinc-650 font-mono text-xs">
              <HelpCircle className="h-6 w-6 text-zinc-850 mb-2" />
              <span>No execution metadata returned. Execute a query above to view telemetry metrics.</span>
            </div>
          )}

        </div>
      </div>

      {/* Global Error Banner */}
      {error && (
        <div className="fixed bottom-4 right-4 z-50 p-3 bg-red-950/20 border border-red-900/35 rounded-lg text-xs font-mono text-red-400 shadow-xl max-w-sm flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-red-500 shrink-0" />
            <span>{error}</span>
          </div>
        </div>
      )}

    </div>
  );
}
