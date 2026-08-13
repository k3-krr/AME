"use client";

import { useEffect, useState, useRef } from "react";
import { useChatStore } from "@/store/chatStore";
import ChatMessage from "@/components/chat/ChatMessage";
import MessageComposer from "@/components/chat/MessageComposer";
import ChatEmptyState from "@/components/chat/ChatEmptyState";
import ConversationList from "@/components/chat/ConversationList";
import DeleteConversationDialog from "@/components/chat/DeleteConversationDialog";
import { 
  Sparkles, 
  ChevronDown, 
  Cpu, 
  Brain, 
  MessageSquare,
  SlidersHorizontal,
  Plus,
  Loader2,
  AlertCircle,
  X
} from "lucide-react";
import { cn } from "@/lib/utils";

export default function Home() {
  // Zustand chat store hooks
  const {
    conversations,
    activeConversationId,
    messages,
    isStreaming,
    isLoadingConversations,
    isLoadingMessages,
    error,
    fetchConversations,
    createConversation,
    deleteConversation,
    selectConversation,
    sendMessageStream,
    clearError
  } = useChatStore();

  // local configuration triggers
  const [isConfiguringNewChat, setIsConfiguringNewChat] = useState(false);
  const [newChatTitle, setNewChatTitle] = useState("");
  const [newChatSystemPrompt, setNewChatSystemPrompt] = useState(
    "You are an assistant equipped with an Adaptive Memory Engine. Synthesize retrieved episodic context to deliver grounded responses."
  );
  
  // Collapsible panels
  const [systemPromptOpen, setSystemPromptOpen] = useState(false);

  // Deletion modals
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [deleteSubmitting, setDeleteSubmitting] = useState(false);

  // Viewport scroll targets
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const activeConversation = conversations.find((c) => c.id === activeConversationId);

  // 1. Initial list loading
  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  // 2. Auto scroll on message log updates
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  // Actions
  const handleNewChatCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const title = newChatTitle.trim() || "New Chat";
    const prompt = newChatSystemPrompt.trim() || null;
    
    const newId = await createConversation(title, prompt);
    if (newId) {
      setIsConfiguringNewChat(false);
      setNewChatTitle("");
      // Select it and load messages
      selectConversation(newId);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTargetId) return;
    setDeleteSubmitting(true);
    try {
      await deleteConversation(deleteTargetId);
      setDeleteTargetId(null);
    } finally {
      setDeleteSubmitting(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col md:flex-row min-h-0 bg-zinc-950">
      
      {/* 1. Left Secondary Sidebar: Conversation Session Manager */}
      <div className="w-full md:w-72 border-b md:border-b-0 md:border-r border-zinc-900 bg-zinc-950 flex flex-col p-4 gap-4 shrink-0">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-mono text-zinc-550 uppercase tracking-widest">Chat Contexts</span>
          {!isConfiguringNewChat && (
            <button
              onClick={() => setIsConfiguringNewChat(true)}
              className="flex items-center gap-1 px-2 py-1 rounded bg-zinc-900 border border-zinc-800 hover:bg-zinc-850 text-zinc-300 text-[10px] font-semibold transition-colors cursor-pointer outline-none"
            >
              <Plus className="h-3 w-3" />
              <span>New Chat</span>
            </button>
          )}
        </div>

        {/* Dynamic chat configuration card */}
        {isConfiguringNewChat && (
          <form onSubmit={handleNewChatCreate} className="border border-zinc-800 bg-zinc-900/10 rounded-xl p-3 flex flex-col gap-2.5">
            <h4 className="text-[10px] font-mono text-zinc-400 uppercase tracking-wider">Initialize Chat</h4>
            
            <div className="flex flex-col gap-1">
              <label htmlFor="chat-title" className="text-[9px] font-mono text-zinc-600 uppercase">Title</label>
              <input
                id="chat-title"
                type="text"
                value={newChatTitle}
                onChange={(e) => setNewChatTitle(e.target.value)}
                placeholder="Session Topic Name"
                className="w-full rounded border border-zinc-850 bg-zinc-950 px-2 py-1.5 text-xs text-zinc-200 placeholder-zinc-650 outline-none focus:border-zinc-750 font-sans"
                maxLength={40}
              />
            </div>

            <div className="flex flex-col gap-1">
              <label htmlFor="chat-prompt" className="text-[9px] font-mono text-zinc-600 uppercase">System Prompt Instructions</label>
              <textarea
                id="chat-prompt"
                value={newChatSystemPrompt}
                onChange={(e) => setNewChatSystemPrompt(e.target.value)}
                placeholder="Define assistant context constraints..."
                rows={3}
                className="w-full rounded border border-zinc-850 bg-zinc-950 px-2 py-1.5 text-xs text-zinc-300 placeholder-zinc-650 outline-none focus:border-zinc-750 font-mono h-14 resize-none"
              />
            </div>

            <div className="flex items-center justify-end gap-1.5 text-[10px] mt-1">
              <button
                type="button"
                onClick={() => setIsConfiguringNewChat(false)}
                className="px-2 py-1 rounded text-zinc-500 hover:text-zinc-300 transition-colors outline-none cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-2.5 py-1 rounded bg-zinc-100 hover:bg-zinc-200 text-zinc-950 font-semibold transition-colors outline-none cursor-pointer"
              >
                Initialize
              </button>
            </div>
          </form>
        )}

        {/* Conversations list container */}
        <div className="flex-1 flex flex-col min-h-0">
          {isLoadingConversations ? (
            <div className="flex items-center justify-center py-10 gap-2 text-xs font-mono text-zinc-650">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span>Loading sessions...</span>
            </div>
          ) : (
            <ConversationList
              conversations={conversations}
              activeConversationId={activeConversationId}
              onSelect={selectConversation}
              onDeleteClick={(id) => setDeleteTargetId(id)}
            />
          )}
        </div>
      </div>

      {/* 2. Right Column: Main Chat Playground */}
      <div className="flex-1 flex flex-col min-h-0">
        
        {/* Workspace Runtime Header */}
        <div className="flex items-center justify-between border-b border-zinc-900/60 bg-zinc-950 px-4 py-2 text-xs text-zinc-500 font-mono shrink-0">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5">
              <Cpu className="h-3.5 w-3.5 text-zinc-650" />
              <span>AME Runtime</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Brain className="h-3.5 w-3.5 text-zinc-650" />
              <span>Memory Architecture: <span className="text-zinc-400">Hybrid</span></span>
            </div>
          </div>
          <div className="hidden sm:flex items-center gap-2">
            <span>Retrieval: <span className="text-emerald-500">Active</span></span>
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 flex flex-col justify-between p-4 md:p-6 overflow-hidden min-h-0 max-w-4xl w-full mx-auto">
          
          {activeConversation ? (
            // Active message view logs
            <div className="flex-1 flex flex-col min-h-0 justify-between gap-4">
              
              {/* Read-Only System Prompt parameters box */}
              <div className="border border-zinc-900 bg-zinc-900/10 rounded-lg overflow-hidden shrink-0">
                <button
                  type="button"
                  onClick={() => setSystemPromptOpen(!systemPromptOpen)}
                  className="w-full flex items-center justify-between px-4 py-2.5 text-left hover:bg-zinc-900/20 transition-colors outline-none"
                >
                  <div className="flex items-center gap-2.5">
                    <SlidersHorizontal className="h-3.5 w-3.5 text-zinc-500" />
                    <span className="text-xs font-semibold text-zinc-400 tracking-tight">System Prompt Configuration (Active Session)</span>
                  </div>
                  <ChevronDown className={cn("h-4 w-4 text-zinc-600 transition-transform duration-200", systemPromptOpen && "transform rotate-180")} />
                </button>
                
                {systemPromptOpen && (
                  <div className="border-t border-zinc-900 p-3 bg-zinc-950/40">
                    <p className="text-[10px] text-zinc-600 leading-normal mb-2.5">
                      Instructions configured upon creation of this conversation canvas. This system definition is read-only.
                    </p>
                    <textarea
                      readOnly
                      value={activeConversation.system_prompt || "No custom prompt instruction registered."}
                      className="w-full rounded-md border border-zinc-900 bg-zinc-950/80 px-2.5 py-2 text-xs font-mono text-zinc-500 outline-none h-16 resize-none"
                    />
                  </div>
                )}
              </div>

              {/* Messages view logs */}
              <div className="flex-1 overflow-y-auto pr-1 flex flex-col gap-5 py-2 min-h-0 border-t border-zinc-900/10 mt-2">
                {isLoadingMessages ? (
                  <div className="flex-grow flex flex-col items-center justify-center text-zinc-600 font-mono text-xs gap-2">
                    <Loader2 className="h-4 w-4 animate-spin text-zinc-550" />
                    <span>Loading logs from memory database...</span>
                  </div>
                ) : messages.length > 0 ? (
                  <>
                    {messages.map((m) => (
                      <ChatMessage key={m.id} message={m} />
                    ))}
                    <div ref={messagesEndRef} />
                  </>
                ) : (
                  <div className="flex-grow flex flex-col items-center justify-center text-center max-w-sm mx-auto">
                    <MessageSquare className="h-8 w-8 text-zinc-800 mb-3" />
                    <h4 className="text-xs font-semibold text-zinc-400">Empty Conversation Canvas</h4>
                    <p className="text-[11px] text-zinc-650 mt-1">
                      No logs have been submitted to this conversation canvas yet. Send a prompt below to enrich memory states.
                    </p>
                  </div>
                )}
              </div>

            </div>
          ) : (
            // Welcoming empty state dashboard
            <ChatEmptyState onCreateNew={() => setIsConfiguringNewChat(true)} />
          )}

          {/* Bottom input area layout */}
          <div className="mt-4 shrink-0 w-full flex flex-col gap-2">
            
            {/* Global/Stream Error feedbacks */}
            {error && (
              <div className="flex items-center justify-between gap-3 p-3 bg-red-950/20 border border-red-900/35 rounded-lg text-xs font-mono text-red-400 shadow-md">
                <div className="flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 text-red-500 shrink-0" />
                  <span>{error}</span>
                </div>
                <button
                  onClick={clearError}
                  className="p-1 text-red-450 hover:bg-red-900/10 rounded transition-colors cursor-pointer outline-none"
                  title="Dismiss error alert"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            )}

            <MessageComposer
              onSend={sendMessageStream}
              disabled={!activeConversationId || isStreaming}
              isStreaming={isStreaming}
            />

            <div className="flex items-center justify-center gap-1.5 text-[9px] text-zinc-600 font-mono text-center">
              <Sparkles className="h-3 w-3 text-zinc-700 animate-pulse" />
              <span>Adaptive Memory Engine — Conversational Playground Workspace</span>
            </div>
          </div>

        </div>
      </div>

      {/* 3. Conversation delete overlay dialogue */}
      <DeleteConversationDialog
        isOpen={deleteTargetId !== null}
        onClose={() => setDeleteTargetId(null)}
        onConfirm={handleDeleteConfirm}
        isDeleting={deleteSubmitting}
      />
      
    </div>
  );
}
