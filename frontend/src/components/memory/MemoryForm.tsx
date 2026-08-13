"use client";

import { useState } from "react";
import { Memory, MemoryType, MemorySystem } from "@/types";
import { CreateMemoryPayload, UpdateMemoryPayload } from "@/lib/api/memories";
import { AlertCircle, HelpCircle } from "lucide-react";

interface MemoryFormProps {
  initialData?: Memory;
  onSubmit: (data: CreateMemoryPayload | UpdateMemoryPayload) => Promise<void>;
  onCancel: () => void;
  isSubmitting: boolean;
}

const MEMORY_TYPES: MemoryType[] = [
  "Preference", "Fact", "Goal", "Task", "Profile", 
  "Relationship", "Skill", "Custom", "Education", 
  "Work", "Project", "Habit", "Event", "Correction", "Instruction"
];

const MEMORY_SYSTEMS: MemorySystem[] = [
  "Semantic", "Episodic", "Procedural", "Working"
];

export default function MemoryForm({ initialData, onSubmit, onCancel, isSubmitting }: MemoryFormProps) {
  const [content, setContent] = useState(initialData?.content || "");
  const [memoryType, setMemoryType] = useState<MemoryType>(initialData?.memory_type || "Fact");
  const [memorySystem, setMemorySystem] = useState<MemorySystem>(initialData?.memory_system || "Semantic");
  const [importance, setImportance] = useState(initialData?.importance !== undefined ? initialData.importance : 0.5);
  const [confidence, setConfidence] = useState(initialData?.confidence !== undefined ? initialData.confidence : 0.8);
  
  // UUID fields
  const [conversationId, setConversationId] = useState(initialData?.conversation_id || "");
  
  // Date-time fields (stored as YYYY-MM-DDTHH:MM strings)
  const [occurredAt, setOccurredAt] = useState(
    initialData?.occurred_at ? new Date(initialData.occurred_at).toISOString().slice(0, 16) : ""
  );
  const [expiresAt, setExpiresAt] = useState(
    initialData?.expires_at ? new Date(initialData.expires_at).toISOString().slice(0, 16) : ""
  );

  // Metadata JSON
  const [metadataStr, setMetadataStr] = useState(
    initialData?.metadata ? JSON.stringify(initialData.metadata, null, 2) : "{}"
  );

  const [validationError, setValidationError] = useState<string | null>(null);

  // Auto-switch memory system based on type selection if creating new memory
  const handleTypeChange = (newType: MemoryType) => {
    setMemoryType(newType);
    if (!initialData) {
      if (newType === "Event") {
        setMemorySystem("Episodic");
      } else if (["Instruction", "Skill", "Habit", "Task"].includes(newType)) {
        setMemorySystem("Procedural");
      } else {
        setMemorySystem("Semantic");
      }
    }
  };

  const validateForm = () => {
    if (!content.trim()) {
      return "Memory content cannot be empty.";
    }

    const uuidRegex = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;
    
    // Validate Episodic / Working requirements
    if ((memorySystem === "Episodic" || memorySystem === "Working") && !conversationId.trim()) {
      return `${memorySystem} memories require a valid Conversation ID (UUID).`;
    }

    if (conversationId.trim() && !uuidRegex.test(conversationId.trim())) {
      return "Conversation ID must be a valid UUID format.";
    }

    if (memorySystem === "Working" && !expiresAt) {
      return "Working memories require an expires_at timestamp.";
    }

    // Validate Metadata JSON
    try {
      if (metadataStr.trim()) {
        JSON.parse(metadataStr);
      }
    } catch {
      return "Invalid JSON syntax in metadata field.";
    }

    return null;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const error = validateForm();
    if (error) {
      setValidationError(error);
      return;
    }
    setValidationError(null);

    // Format metadata
    const parsedMetadata = metadataStr.trim() ? JSON.parse(metadataStr) : {};

    // Format dates
    const resolvedOccurredAt = occurredAt ? new Date(occurredAt).toISOString() : null;
    const resolvedExpiresAt = expiresAt && memorySystem === "Working" ? new Date(expiresAt).toISOString() : null;

    if (initialData) {
      // Update payload
      const payload: UpdateMemoryPayload = {
        content,
        memory_type: memoryType,
        importance,
        confidence,
        metadata: parsedMetadata,
        memory_system: memorySystem,
        occurred_at: resolvedOccurredAt,
        expires_at: resolvedExpiresAt,
      };
      onSubmit(payload);
    } else {
      // Create payload
      const payload: CreateMemoryPayload = {
        content,
        memory_type: memoryType,
        importance,
        confidence,
        metadata: parsedMetadata,
        memory_system: memorySystem,
        occurred_at: resolvedOccurredAt,
        expires_at: resolvedExpiresAt,
        conversation_id: conversationId.trim() ? conversationId.trim() : null,
      };
      onSubmit(payload);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5 bg-zinc-950 p-1">
      {validationError && (
        <div className="flex items-start gap-2.5 p-3 rounded-lg border border-red-900/60 bg-red-950/20 text-red-400 text-xs leading-normal font-mono">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
          <span>{validationError}</span>
        </div>
      )}

      {/* Content Textarea */}
      <div className="flex flex-col gap-1.5">
        <label htmlFor="form-content" className="text-[10px] font-mono text-zinc-400 uppercase tracking-wider">Memory Content</label>
        <textarea
          id="form-content"
          required
          rows={4}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Detailed memory factual context..."
          className="w-full rounded-lg border border-zinc-800 bg-zinc-900/20 px-3 py-2 text-sm text-zinc-200 placeholder-zinc-650 outline-none focus:border-zinc-700 transition-colors"
          disabled={isSubmitting}
        />
      </div>

      {/* Select Category Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="form-type" className="text-[10px] font-mono text-zinc-400 uppercase tracking-wider">Content Type</label>
          <select
            id="form-type"
            value={memoryType}
            onChange={(e) => handleTypeChange(e.target.value as MemoryType)}
            className="w-full rounded-lg border border-zinc-800 bg-zinc-900/40 px-3 py-2 text-xs text-zinc-200 outline-none focus:border-zinc-700 transition-colors"
            disabled={isSubmitting}
          >
            {MEMORY_TYPES.map((t) => (
              <option key={t} value={t} className="bg-zinc-950">{t}</option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="form-system" className="text-[10px] font-mono text-zinc-400 uppercase tracking-wider">Memory System Tier</label>
          <select
            id="form-system"
            value={memorySystem}
            onChange={(e) => setMemorySystem(e.target.value as MemorySystem)}
            className="w-full rounded-lg border border-zinc-800 bg-zinc-900/40 px-3 py-2 text-xs text-zinc-200 outline-none focus:border-zinc-700 transition-colors"
            disabled={isSubmitting}
          >
            {MEMORY_SYSTEMS.map((sys) => (
              <option key={sys} value={sys} className="bg-zinc-950">{sys}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Weight sliders */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 border-t border-zinc-900 pt-4">
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-zinc-400">
            <label htmlFor="form-importance">Importance Weight</label>
            <span>{Math.round(importance * 100)}%</span>
          </div>
          <input
            id="form-importance"
            type="range"
            min="0.0"
            max="1.0"
            step="0.05"
            value={importance}
            onChange={(e) => setImportance(parseFloat(e.target.value))}
            className="w-full accent-zinc-200 bg-zinc-905 h-1.5 rounded-lg appearance-none cursor-pointer"
            disabled={isSubmitting}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-zinc-400">
            <label htmlFor="form-confidence">Confidence Score</label>
            <span>{Math.round(confidence * 100)}%</span>
          </div>
          <input
            id="form-confidence"
            type="range"
            min="0.0"
            max="1.0"
            step="0.05"
            value={confidence}
            onChange={(e) => setConfidence(parseFloat(e.target.value))}
            className="w-full accent-zinc-200 bg-zinc-905 h-1.5 rounded-lg appearance-none cursor-pointer"
            disabled={isSubmitting}
          />
        </div>
      </div>

      {/* Conditional Fields (Conversation ID & Expiry Date) */}
      {(memorySystem === "Episodic" || memorySystem === "Working") && (
        <div className="flex flex-col gap-1.5 border-t border-zinc-900 pt-4">
          <label htmlFor="form-conv-id" className="text-[10px] font-mono text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
            <span>Conversation ID (UUID)</span>
            <span className="text-zinc-650 font-normal font-sans">(Required for {memorySystem})</span>
          </label>
          <input
            id="form-conv-id"
            type="text"
            required
            value={conversationId}
            onChange={(e) => setConversationId(e.target.value)}
            placeholder="e.g. d3b07384-d113-4ec6-a5d7-ec20606e1215"
            className="w-full rounded-lg border border-zinc-800 bg-zinc-900/40 px-3.5 py-2 text-xs font-mono text-zinc-200 placeholder-zinc-700 outline-none focus:border-zinc-700 transition-colors"
            disabled={isSubmitting}
          />
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 border-t border-zinc-900 pt-4">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="form-occurred" className="text-[10px] font-mono text-zinc-400 uppercase tracking-wider">Occurred At (Episodic Event)</label>
          <input
            id="form-occurred"
            type="datetime-local"
            value={occurredAt}
            onChange={(e) => setOccurredAt(e.target.value)}
            className="w-full rounded-lg border border-zinc-800 bg-zinc-900/40 px-3.5 py-2 text-xs text-zinc-300 outline-none focus:border-zinc-700 transition-colors font-mono"
            disabled={isSubmitting}
          />
        </div>

        {memorySystem === "Working" && (
          <div className="flex flex-col gap-1.5">
            <label htmlFor="form-expiry" className="text-[10px] font-mono text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
              <span>Expires At</span>
              <span className="text-zinc-650 font-normal font-sans">(Required)</span>
            </label>
            <input
              id="form-expiry"
              type="datetime-local"
              required
              value={expiresAt}
              onChange={(e) => setExpiresAt(e.target.value)}
              className="w-full rounded-lg border border-zinc-800 bg-zinc-900/40 px-3.5 py-2 text-xs text-zinc-350 outline-none focus:border-zinc-700 transition-colors font-mono border-rose-900/40"
              disabled={isSubmitting}
            />
          </div>
        )}
      </div>

      {/* Metadata JSON string field */}
      <div className="flex flex-col gap-1.5 border-t border-zinc-900 pt-4">
        <label htmlFor="form-metadata" className="text-[10px] font-mono text-zinc-400 uppercase tracking-wider flex items-center gap-1">
          <span>Custom Metadata (JSON)</span>
          <span title="Valid key-value JSON string">
            <HelpCircle className="h-3.5 w-3.5 text-zinc-700 cursor-help" />
          </span>
        </label>
        <textarea
          id="form-metadata"
          rows={3}
          value={metadataStr}
          onChange={(e) => setMetadataStr(e.target.value)}
          placeholder="{}"
          className="w-full rounded-lg border border-zinc-800 bg-zinc-900/20 px-3 py-2 text-xs font-mono text-zinc-300 placeholder-zinc-700 outline-none focus:border-zinc-700 transition-colors"
          disabled={isSubmitting}
        />
      </div>

      {/* Form Action Buttons */}
      <div className="flex items-center justify-end gap-3 border-t border-zinc-900 pt-5 mt-2">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 text-xs font-medium text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 rounded-lg transition-colors cursor-pointer"
          disabled={isSubmitting}
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className="px-4 py-2 text-xs font-medium bg-zinc-100 hover:bg-zinc-200 text-zinc-950 rounded-lg transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isSubmitting ? "Submitting..." : initialData ? "Save Changes" : "Create Memory"}
        </button>
      </div>
    </form>
  );
}
