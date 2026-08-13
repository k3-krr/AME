import { Message } from "@/types";
import { cn } from "@/lib/utils";
import { Brain, Clock, HelpCircle, User, Cpu } from "lucide-react";

interface ChatMessageProps {
  message: Message;
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.sender_role === "user";
  
  const formattedTime = new Date(message.created_at).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  const getMemoryStatusBadge = () => {
    switch (message.memory_status) {
      case "consolidated":
        return (
          <div 
            className="flex items-center gap-1 text-[9px] font-mono px-1.5 py-0.5 rounded bg-emerald-950/20 border border-emerald-900/30 text-emerald-400"
            title="Consolidated into AME Cognitive Long-Term memory"
          >
            <Brain className="h-3 w-3" />
            <span>Consolidated</span>
          </div>
        );
      case "pending":
        return (
          <div 
            className="flex items-center gap-1 text-[9px] font-mono px-1.5 py-0.5 rounded bg-amber-950/15 border border-amber-900/25 text-amber-500"
            title="Awaiting continuous extraction routine"
          >
            <Clock className="h-3 w-3 animate-pulse" />
            <span>Pending Ingest</span>
          </div>
        );
      case "ignored":
        return (
          <div 
            className="flex items-center gap-1 text-[9px] font-mono px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-850 text-zinc-550"
            title="Excluded from semantic extraction criteria"
          >
            <HelpCircle className="h-3 w-3" />
            <span>Ignored</span>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className={cn("flex flex-col gap-1.5 w-full", isUser ? "items-end" : "items-start")}>
      {/* Sender Header */}
      <div className="flex items-center gap-1.5 text-[10px] font-mono text-zinc-550 px-1">
        {isUser ? (
          <>
            <span>User</span>
            <User className="h-3 w-3 text-zinc-600" />
          </>
        ) : (
          <>
            <Cpu className="h-3 w-3 text-zinc-500" />
            <span>AME Engine</span>
          </>
        )}
      </div>

      {/* Bubble Container */}
      <div
        className={cn(
          "rounded-2xl px-4 py-3 shadow-xs border text-sm leading-relaxed max-w-[85%] md:max-w-[75%] whitespace-pre-wrap break-words font-sans selection:bg-zinc-800",
          isUser
            ? "bg-zinc-900 border-zinc-800 text-zinc-100 rounded-tr-none"
            : "bg-zinc-950/80 border-zinc-900/80 text-zinc-200 rounded-tl-none"
        )}
      >
        {message.content || (
          <span className="text-zinc-650 italic font-mono text-xs flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-zinc-650 animate-bounce [animation-delay:-0.3s]" />
            <span className="h-1.5 w-1.5 rounded-full bg-zinc-650 animate-bounce [animation-delay:-0.15s]" />
            <span className="h-1.5 w-1.5 rounded-full bg-zinc-650 animate-bounce" />
          </span>
        )}
      </div>

      {/* Timestamp & Memory Status row */}
      <div className="flex items-center gap-2.5 text-[9px] font-mono text-zinc-600 px-1">
        <span>{formattedTime}</span>
        {!isUser && getMemoryStatusBadge()}
      </div>
    </div>
  );
}
