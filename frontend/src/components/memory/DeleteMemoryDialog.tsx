"use client";

import { useEffect } from "react";
import { ShieldAlert, Terminal } from "lucide-react";

interface DeleteMemoryDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  isDeleting: boolean;
}

export default function DeleteMemoryDialog({ isOpen, onClose, onConfirm, isDeleting }: DeleteMemoryDialogProps) {
  // Handle escape keypress
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/60 backdrop-blur-xs" onClick={onClose} aria-hidden="true" />

      {/* Modal Content */}
      <div className="relative w-full max-w-md bg-zinc-950 border border-zinc-800 rounded-xl p-5 md:p-6 shadow-2xl flex flex-col gap-4 z-10">
        <div className="flex items-start gap-3.5">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-red-950/20 border border-red-900/40 text-red-400">
            <ShieldAlert className="h-5.5 w-5.5" />
          </div>
          <div className="flex flex-col">
            <h3 className="text-sm font-semibold text-zinc-200 tracking-tight">Delete Memory</h3>
            <p className="text-xs text-zinc-500 mt-1 leading-relaxed">
              Are you sure you want to delete this memory? The database will perform a <span className="font-mono text-zinc-400 font-semibold bg-zinc-900/60 px-1 py-0.5 rounded">soft-delete</span> (flagging the status state to <span className="font-semibold text-red-400 font-mono">DELETED</span>).
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 p-2 rounded bg-zinc-900/40 border border-zinc-900/80 text-[10px] font-mono text-zinc-500 leading-normal">
          <Terminal className="h-3.5 w-3.5 text-zinc-650" />
          <span>Updates status parameter to DELETED (preserving references).</span>
        </div>

        <div className="flex items-center justify-end gap-3 mt-2 border-t border-zinc-900 pt-4">
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-1.5 text-xs font-medium text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 rounded-lg transition-colors cursor-pointer"
            disabled={isDeleting}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isDeleting}
            className="px-3.5 py-1.5 text-xs font-medium bg-red-900/20 border border-red-900/40 hover:bg-red-900/35 text-red-400 rounded-lg transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isDeleting ? "Deleting..." : "Soft Delete"}
          </button>
        </div>
      </div>
    </div>
  );
}
