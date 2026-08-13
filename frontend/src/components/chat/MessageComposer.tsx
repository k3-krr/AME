import React, { useState, useRef, useEffect } from "react";
import { Send, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface MessageComposerProps {
  onSend: (content: string) => void;
  disabled: boolean;
  isStreaming: boolean;
}

export default function MessageComposer({ onSend, disabled, isStreaming }: MessageComposerProps) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea content bounds dynamically
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    
    // Reset height to compute scrollHeight accurately
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
  }, [text]);

  const handleSend = () => {
    if (!text.trim() || disabled) return;
    onSend(text.trim());
    setText("");
    
    // Reset height back to single line after submission
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="w-full flex flex-col gap-2 bg-zinc-950/40 p-1">
      <div 
        className={cn(
          "relative rounded-xl border transition-all duration-200 p-2.5 flex flex-col gap-2.5",
          disabled 
            ? "border-zinc-900 bg-zinc-950/20 cursor-not-allowed" 
            : "border-zinc-800 bg-zinc-900/10 focus-within:border-zinc-700/80 focus-within:bg-zinc-900/20"
        )}
      >
        <textarea
          ref={textareaRef}
          rows={2}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={
            isStreaming 
              ? "AME is generating response..." 
              : disabled 
                ? "Select a conversation session to start chatting..." 
                : "Type message... (Press Enter to send, Shift+Enter for new line)"
          }
          className="w-full bg-transparent border-0 resize-none text-sm text-zinc-200 placeholder-zinc-650 outline-none focus:ring-0 focus:outline-none min-h-[48px] max-h-[200px]"
          aria-label="Message prompt composer text"
        />

        <div className="flex items-center justify-between border-t border-zinc-900/60 pt-2.5">
          <div className="flex items-center gap-1.5 text-[10px] text-zinc-600 font-mono">
            {isStreaming ? (
              <span className="flex items-center gap-1 text-amber-500 animate-pulse">
                <Loader2 className="h-3 w-3 animate-spin" />
                <span>Generating cognitive response stream...</span>
              </span>
            ) : (
              <span>Adaptive ContextBuilder Active</span>
            )}
          </div>

          <button
            type="button"
            onClick={handleSend}
            disabled={disabled || !text.trim() || isStreaming}
            className={cn(
              "flex h-8 w-8 items-center justify-center rounded-lg border transition-all duration-200 outline-none shrink-0",
              text.trim() && !disabled && !isStreaming
                ? "bg-zinc-100 border-zinc-100 text-zinc-950 cursor-pointer hover:bg-zinc-200"
                : "bg-transparent border-zinc-850 text-zinc-600 cursor-not-allowed"
            )}
            title="Send prompt message"
            aria-label="Submit message prompt"
          >
            <Send className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
