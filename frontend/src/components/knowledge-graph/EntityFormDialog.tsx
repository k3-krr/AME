import { useState, useEffect } from "react";
import { Entity, EntityType } from "@/types";
import { CreateEntityPayload } from "@/lib/api/knowledgeGraph";
import { AlertCircle, HelpCircle } from "lucide-react";

interface EntityFormDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (payload: CreateEntityPayload) => Promise<void>;
  initialData?: Entity;
  isSubmitting: boolean;
}

const ENTITY_TYPES: EntityType[] = [
  "PERSON",
  "ORGANIZATION",
  "PROJECT",
  "TECHNOLOGY",
  "FRAMEWORK",
  "DATABASE",
  "API",
  "DOCUMENT",
  "CUSTOM",
];

export default function EntityFormDialog({
  isOpen,
  onClose,
  onSubmit,
  initialData,
  isSubmitting,
}: EntityFormDialogProps) {
  const [name, setName] = useState("");
  const [entityType, setEntityType] = useState<EntityType>("CUSTOM");
  const [metadataStr, setMetadataStr] = useState("{}");
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    if (initialData) {
      Promise.resolve().then(() => {
        setName(initialData.name);
        setEntityType(initialData.entity_type);
        setMetadataStr(JSON.stringify(initialData.metadata, null, 2));
      });
    } else {
      Promise.resolve().then(() => {
        setName("");
        setEntityType("CUSTOM");
        setMetadataStr("{}");
      });
    }
    Promise.resolve().then(() => {
      setValidationError(null);
    });
  }, [initialData, isOpen]);

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
      setValidationError("Entity name cannot be empty.");
      return;
    }

    try {
      const parsedMetadata = JSON.parse(metadataStr);
      onSubmit({
        name: name.trim(),
        entity_type: entityType,
        metadata: parsedMetadata,
      });
    } catch {
      setValidationError("Invalid JSON syntax in metadata field.");
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
          {initialData ? "Update Entity Node" : "Create Entity Node"}
        </h3>

        {validationError && (
          <div className="mb-4 flex items-center gap-2 p-2.5 rounded bg-red-950/20 border border-red-900/30 text-xs font-mono text-red-400">
            <AlertCircle className="h-4 w-4 text-red-500 shrink-0" />
            <span>{validationError}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          
          {/* Entity Name */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="ent-name" className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider">Entity Name</label>
            <input
              id="ent-name"
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Adaptive Memory Engine"
              className="w-full rounded-lg border border-zinc-800 bg-zinc-900/20 px-3 py-2 text-sm text-zinc-200 placeholder-zinc-650 outline-none focus:border-zinc-700 transition-colors"
              disabled={isSubmitting}
            />
          </div>

          {/* Classification type */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="ent-type" className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider">Entity Category</label>
            <select
              id="ent-type"
              value={entityType}
              onChange={(e) => setEntityType(e.target.value as EntityType)}
              className="w-full rounded-lg border border-zinc-800 bg-zinc-900/40 px-3 py-2 text-xs text-zinc-200 outline-none focus:border-zinc-700 transition-colors cursor-pointer"
              disabled={isSubmitting}
            >
              {ENTITY_TYPES.map((type) => (
                <option key={type} value={type} className="bg-zinc-950">{type}</option>
              ))}
            </select>
          </div>

          {/* Metadata JSON */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="ent-metadata" className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider flex items-center gap-1">
              <span>Metadata JSON</span>
              <span title="Valid JSON string metadata">
                <HelpCircle className="h-3.5 w-3.5 text-zinc-700 cursor-help" />
              </span>
            </label>
            <textarea
              id="ent-metadata"
              value={metadataStr}
              onChange={(e) => setMetadataStr(e.target.value)}
              placeholder="{}"
              rows={4}
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
              {isSubmitting ? "Saving..." : "Save Node"}
            </button>
          </div>

        </form>
      </div>
    </div>
  );
}
