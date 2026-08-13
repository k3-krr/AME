import { useState, useEffect } from "react";
import { Agent } from "@/types";
import { CreateAgentPayload } from "@/lib/api/agents";
import { AlertCircle, HelpCircle } from "lucide-react";

interface AgentFormDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (payload: CreateAgentPayload) => Promise<void>;
  initialData?: Agent;
  isSubmitting: boolean;
}

export default function AgentFormDialog({
  isOpen,
  onClose,
  onSubmit,
  initialData,
  isSubmitting,
}: AgentFormDialogProps) {
  const [name, setName] = useState(initialData?.name || "");
  const [description, setDescription] = useState(initialData?.description || "");
  const [configStr, setConfigStr] = useState(
    initialData?.configuration ? JSON.stringify(initialData.configuration, null, 2) : "{}"
  );
  const [validationError, setValidationError] = useState<string | null>(null);

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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    if (!name.trim()) {
      setValidationError("Agent name is required.");
      return;
    }

    try {
      const parsedConfig = JSON.parse(configStr);
      onSubmit({
        name: name.trim(),
        description: description.trim() || null,
        configuration: parsedConfig,
      });
    } catch {
      setValidationError("Invalid JSON configuration structure.");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop overlay */}
      <div 
        className="fixed inset-0 bg-black/60 backdrop-blur-xs" 
        onClick={onClose} 
        aria-hidden="true" 
      />

      {/* Modal Card */}
      <div className="relative w-full max-w-md bg-zinc-950 border border-zinc-805 rounded-xl p-5 md:p-6 shadow-2xl z-10">
        <h3 className="text-sm font-semibold text-zinc-200 tracking-tight uppercase tracking-wider font-mono border-b border-zinc-900 pb-3 mb-4">
          {initialData ? "Configure Agent Profile" : "Register Agent Profile"}
        </h3>

        {validationError && (
          <div className="mb-4 flex items-center gap-2 p-2.5 rounded bg-red-950/20 border border-red-900/30 text-xs font-mono text-red-400">
            <AlertCircle className="h-4 w-4 text-red-500 shrink-0" />
            <span>{validationError}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          
          {/* Agent Name */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="agent-name" className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider">Agent Name</label>
            <input
              id="agent-name"
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Memory Consolidator Worker"
              className="w-full rounded-lg border border-zinc-800 bg-zinc-900/20 px-3 py-2 text-sm text-zinc-200 placeholder-zinc-650 outline-none focus:border-zinc-700 transition-colors"
              disabled={isSubmitting}
            />
          </div>

          {/* Description */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="agent-desc" className="text-[10px] font-mono text-zinc-555 uppercase tracking-wider">Description</label>
            <input
              id="agent-desc"
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional purpose description"
              className="w-full rounded-lg border border-zinc-800 bg-zinc-900/20 px-3 py-2 text-sm text-zinc-200 placeholder-zinc-650 outline-none focus:border-zinc-700 transition-colors"
              disabled={isSubmitting}
            />
          </div>

          {/* Configuration JSON */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="agent-config" className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider flex items-center gap-1">
              <span>Configuration JSON</span>
              <span title="Custom JSON settings">
                <HelpCircle className="h-3.5 w-3.5 text-zinc-700 cursor-help" />
              </span>
            </label>
            <textarea
              id="agent-config"
              value={configStr}
              onChange={(e) => setConfigStr(e.target.value)}
              placeholder="{}"
              rows={5}
              className="w-full rounded-lg border border-zinc-800 bg-zinc-900/20 px-3 py-2 text-xs text-zinc-350 placeholder-zinc-650 outline-none focus:border-zinc-700 transition-colors font-mono"
              disabled={isSubmitting}
            />
          </div>

          {/* Action buttons */}
          <div className="flex justify-end gap-2 border-t border-zinc-900 pt-4 mt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-3 py-1.5 rounded-lg border border-zinc-850 bg-zinc-900/40 hover:bg-zinc-900 text-zinc-400 hover:text-zinc-200 text-xs font-semibold transition-colors outline-none cursor-pointer disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-3.5 py-1.5 rounded-lg bg-zinc-100 hover:bg-zinc-200 text-zinc-950 text-xs font-semibold transition-colors outline-none cursor-pointer disabled:opacity-50"
            >
              {isSubmitting ? "Saving..." : "Save Profile"}
            </button>
          </div>

        </form>
      </div>
    </div>
  );
}
