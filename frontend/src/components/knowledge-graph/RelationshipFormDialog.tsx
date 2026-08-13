import { useState, useEffect } from "react";
import { Entity, RelationshipType } from "@/types";
import { CreateRelationshipPayload } from "@/lib/api/knowledgeGraph";
import { AlertCircle, HelpCircle } from "lucide-react";

interface RelationshipFormDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (payload: CreateRelationshipPayload) => Promise<void>;
  entities: Entity[];
  isSubmitting: boolean;
}

const RELATIONSHIP_TYPES: RelationshipType[] = [
  "USES",
  "DEPENDS_ON",
  "IMPLEMENTS",
  "REFERENCES",
  "RELATED_TO",
  "PART_OF",
  "CREATED_BY",
  "LOCATED_IN",
  "INDEXED_BY",
  "CUSTOM",
];

export default function RelationshipFormDialog({
  isOpen,
  onClose,
  onSubmit,
  entities,
  isSubmitting,
}: RelationshipFormDialogProps) {
  const [sourceId, setSourceId] = useState("");
  const [targetId, setTargetId] = useState("");
  const [relationshipType, setRelationshipType] = useState<RelationshipType>("RELATED_TO");
  const [confidence, setConfidence] = useState(1.0);
  const [metadataStr, setMetadataStr] = useState("{}");
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    if (entities.length >= 2) {
      Promise.resolve().then(() => {
        setSourceId(entities[0].id);
        setTargetId(entities[1].id);
      });
    } else {
      Promise.resolve().then(() => {
        setSourceId("");
        setTargetId("");
      });
    }
    Promise.resolve().then(() => {
      setRelationshipType("RELATED_TO");
      setConfidence(1.0);
      setMetadataStr("{}");
      setValidationError(null);
    });
  }, [isOpen, entities]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    if (!sourceId || !targetId) {
      setValidationError("Please select both source and target entities.");
      return;
    }

    if (sourceId === targetId) {
      setValidationError("Self-referential loops are not allowed. Source and Target must differ.");
      return;
    }

    try {
      const parsedMetadata = JSON.parse(metadataStr);
      onSubmit({
        source_entity_id: sourceId,
        target_entity_id: targetId,
        relationship_type: relationshipType,
        confidence: Number(confidence),
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
          Connect Entity Nodes
        </h3>

        {validationError && (
          <div className="mb-4 flex items-center gap-2 p-2.5 rounded bg-red-950/20 border border-red-900/30 text-xs font-mono text-red-400">
            <AlertCircle className="h-4 w-4 text-red-500 shrink-0" />
            <span>{validationError}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          
          {/* Source Select */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="rel-source" className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider">Source Entity Node</label>
            <select
              id="rel-source"
              value={sourceId}
              onChange={(e) => setSourceId(e.target.value)}
              className="w-full rounded-lg border border-zinc-800 bg-zinc-900/40 px-3 py-2 text-xs text-zinc-200 outline-none focus:border-zinc-700 transition-colors cursor-pointer font-sans"
              disabled={isSubmitting}
            >
              {entities.map((ent) => (
                <option key={ent.id} value={ent.id} className="bg-zinc-950">
                  {ent.name} ({ent.entity_type})
                </option>
              ))}
            </select>
          </div>

          {/* Target Select */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="rel-target" className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider">Target Entity Node</label>
            <select
              id="rel-target"
              value={targetId}
              onChange={(e) => setTargetId(e.target.value)}
              className="w-full rounded-lg border border-zinc-800 bg-zinc-900/40 px-3 py-2 text-xs text-zinc-200 outline-none focus:border-zinc-700 transition-colors cursor-pointer font-sans"
              disabled={isSubmitting}
            >
              {entities.map((ent) => (
                <option key={ent.id} value={ent.id} className="bg-zinc-950">
                  {ent.name} ({ent.entity_type})
                </option>
              ))}
            </select>
          </div>

          {/* Relationship Type */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="rel-type" className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider">Edge Predicate Type</label>
            <select
              id="rel-type"
              value={relationshipType}
              onChange={(e) => setRelationshipType(e.target.value as RelationshipType)}
              className="w-full rounded-lg border border-zinc-800 bg-zinc-900/40 px-3 py-2 text-xs text-zinc-200 outline-none focus:border-zinc-700 transition-colors cursor-pointer"
              disabled={isSubmitting}
            >
              {RELATIONSHIP_TYPES.map((type) => (
                <option key={type} value={type} className="bg-zinc-950">{type}</option>
              ))}
            </select>
          </div>

          {/* Confidence Slider */}
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between text-[10px] font-mono text-zinc-500 uppercase tracking-wider">
              <span>Confidence weight</span>
              <span className="text-zinc-300 font-semibold">{Math.round(confidence * 100)}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={confidence}
              onChange={(e) => setConfidence(Number(e.target.value))}
              className="w-full h-1 bg-zinc-900 rounded-lg appearance-none cursor-pointer accent-zinc-100"
              disabled={isSubmitting}
            />
          </div>

          {/* Metadata JSON */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="rel-metadata" className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider flex items-center gap-1">
              <span>Metadata JSON</span>
              <span title="Valid JSON metadata properties">
                <HelpCircle className="h-3.5 w-3.5 text-zinc-700 cursor-help" />
              </span>
            </label>
            <textarea
              id="rel-metadata"
              value={metadataStr}
              onChange={(e) => setMetadataStr(e.target.value)}
              placeholder="{}"
              rows={3}
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
              {isSubmitting ? "Connecting..." : "Connect Nodes"}
            </button>
          </div>

        </form>
      </div>
    </div>
  );
}
