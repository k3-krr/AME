import { AlertTriangle, Loader2 } from "lucide-react";

interface DeleteConversationDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  isDeleting: boolean;
}

export default function DeleteConversationDialog({
  isOpen,
  onClose,
  onConfirm,
  isDeleting,
}: DeleteConversationDialogProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop overlay */}
      <div 
        className="fixed inset-0 bg-black/60 backdrop-blur-xs" 
        onClick={onClose} 
        aria-hidden="true" 
      />

      {/* Modal Dialog Card */}
      <div className="relative w-full max-w-md bg-zinc-950 border border-zinc-805 rounded-xl p-5 md:p-6 shadow-2xl z-10 text-center">
        <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-lg bg-red-950/20 border border-red-900/40 text-red-400 mb-4">
          <AlertTriangle className="h-5 w-5" />
        </div>

        <h3 className="text-sm font-semibold text-zinc-200 tracking-tight uppercase tracking-wider font-mono">
          Delete Conversation Session
        </h3>
        
        <p className="text-xs text-zinc-500 mt-2 leading-relaxed">
          Are you sure you want to permanently delete this chat canvas and purge all of its historical logs? 
          <span className="block mt-1.5 font-semibold text-zinc-400">
            Note: Extracted memories already consolidated into the database will remain intact.
          </span>
        </p>

        {/* Buttons Deck */}
        <div className="flex gap-2 justify-center mt-5">
          <button
            type="button"
            onClick={onClose}
            disabled={isDeleting}
            className="px-3.5 py-1.5 rounded-lg border border-zinc-850 bg-zinc-900/40 hover:bg-zinc-900 text-zinc-400 hover:text-zinc-200 text-xs font-semibold transition-colors outline-none cursor-pointer disabled:opacity-50"
          >
            Cancel
          </button>
          
          <button
            type="button"
            onClick={onConfirm}
            disabled={isDeleting}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg border border-red-900/40 bg-red-950/10 hover:bg-red-950/25 text-red-400 text-xs font-semibold transition-colors outline-none cursor-pointer disabled:opacity-50"
          >
            {isDeleting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            <span>{isDeleting ? "Deleting..." : "Purge Chat"}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
