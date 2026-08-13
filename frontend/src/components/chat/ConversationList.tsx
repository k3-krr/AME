import { Conversation } from "@/types";
import { cn } from "@/lib/utils";
import { MessageSquare, Trash2 } from "lucide-react";

interface ConversationListProps {
  conversations: Conversation[];
  activeConversationId: string | null;
  onSelect: (id: string) => void;
  onDeleteClick: (id: string) => void;
}

export default function ConversationList({
  conversations,
  activeConversationId,
  onSelect,
  onDeleteClick,
}: ConversationListProps) {
  if (conversations.length === 0) {
    return (
      <div className="py-12 text-center text-xs text-zinc-600 font-mono">
        No active chat sessions
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1 w-full overflow-y-auto max-h-[60vh] pr-1.5">
      {conversations.map((c) => {
        const isActive = c.id === activeConversationId;
        return (
          <div
            key={c.id}
            className={cn(
              "flex items-center justify-between group rounded-lg px-2.5 py-2 text-xs transition-all duration-200 outline-none border",
              isActive
                ? "bg-zinc-900 border-zinc-800 text-zinc-100 shadow-sm"
                : "text-zinc-400 hover:bg-zinc-900/40 hover:text-zinc-200 border-transparent"
            )}
          >
            {/* Clickable Title trigger */}
            <button
              onClick={() => onSelect(c.id)}
              className="flex-grow flex items-center gap-2 text-left truncate cursor-pointer outline-none font-medium pr-2"
              title={c.title || "Conversation Session"}
            >
              <MessageSquare className={cn("h-3.5 w-3.5 shrink-0", isActive ? "text-zinc-200" : "text-zinc-550")} />
              <span className="truncate">{c.title || "Conversation Session"}</span>
            </button>

            {/* Delete button (displays on hover) */}
            <button
              onClick={() => onDeleteClick(c.id)}
              className="opacity-0 group-hover:opacity-100 focus:opacity-100 flex h-5 w-5 items-center justify-center rounded text-zinc-650 hover:bg-red-950/20 hover:text-red-400 transition-all outline-none cursor-pointer"
              title="Delete conversation session"
              aria-label={`Delete conversation ${c.title || c.id}`}
            >
              <Trash2 className="h-3 w-3" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
