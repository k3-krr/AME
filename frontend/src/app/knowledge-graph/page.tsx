"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useKnowledgeGraphStore } from "@/store/knowledgeGraphStore";
import GraphVisualizer from "@/components/knowledge-graph/GraphVisualizer";
import EntityFormDialog from "@/components/knowledge-graph/EntityFormDialog";
import RelationshipFormDialog from "@/components/knowledge-graph/RelationshipFormDialog";
import TraversalControls from "@/components/knowledge-graph/TraversalControls";
import { Entity } from "@/types";
import { CreateEntityPayload, CreateRelationshipPayload } from "@/lib/api/knowledgeGraph";
import { 
  Network, 
  Search, 
  Plus, 
  Trash2, 
  Edit, 
  ChevronRight, 
  HelpCircle, 
  Activity,
  Link2,
  X
} from "lucide-react";
import { cn } from "@/lib/utils";

export default function KnowledgeGraphPage() {
  const {
    entities,
    relationships,
    selectedEntityId,
    neighbors,
    connectedMemories,
    shortestPath,
    traversalResult,
    isLoading,
    error,
    fetchGraphData,
    selectEntity,
    createEntity,
    updateEntity,
    deleteEntity,
    createRelationship,
    deleteRelationship,
    fetchShortestPath,
    runTraversal,
    clearTraversalAndPaths
  } = useKnowledgeGraphStore();

  // Filter params
  const [searchQuery, setSearchQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("");

  // Modal open/close controls
  const [isEntityOpen, setIsEntityOpen] = useState(false);
  const [isRelOpen, setIsRelOpen] = useState(false);
  const [entityFormEditData, setEntityFormEditData] = useState<Entity | undefined>(undefined);
  const [submittingEntity, setSubmittingEntity] = useState(false);
  const [submittingRel, setSubmittingRel] = useState(false);

  // Initial load
  useEffect(() => {
    fetchGraphData();
  }, [fetchGraphData]);

  const activeEntity = entities.find((e) => e.id === selectedEntityId);

  // Computes filtered list for left column
  const filteredEntities = entities.filter((e) => {
    const matchesSearch = e.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          e.canonical_name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesType = !typeFilter || e.entity_type === typeFilter;
    return matchesSearch && matchesType;
  });

  const handleCreateEntityClick = () => {
    setEntityFormEditData(undefined);
    setIsEntityOpen(true);
  };

  const handleEditEntityClick = () => {
    if (!activeEntity) return;
    setEntityFormEditData(activeEntity);
    setIsEntityOpen(true);
  };

  const handleEntitySubmit = async (payload: CreateEntityPayload) => {
    setSubmittingEntity(true);
    try {
      if (entityFormEditData) {
        // Update
        const ok = await updateEntity(entityFormEditData.id, payload);
        if (ok) setIsEntityOpen(false);
      } else {
        // Create
        const entity = await createEntity(payload);
        if (entity) setIsEntityOpen(false);
      }
    } finally {
      setSubmittingEntity(false);
    }
  };

  const handleRelationshipSubmit = async (payload: CreateRelationshipPayload) => {
    setSubmittingRel(true);
    try {
      const rel = await createRelationship(payload);
      if (rel) setIsRelOpen(false);
    } finally {
      setSubmittingRel(false);
    }
  };

  const handleDeleteEntity = async () => {
    if (!activeEntity) return;
    if (confirm(`Are you sure you want to permanently delete entity "${activeEntity.name}" and delete all relationships connected to it?`)) {
      await deleteEntity(activeEntity.id);
    }
  };

  const handleDeleteRelationship = async (relId: string) => {
    if (confirm("Are you sure you want to delete this relationship edge?")) {
      await deleteRelationship(relId);
      // Refresh current node details
      if (selectedEntityId) {
        selectEntity(selectedEntityId);
      }
    }
  };

  return (
    <div className="flex-1 flex flex-col md:flex-row min-h-0 bg-zinc-950">
      
      {/* 1. Left Panel: Search & Listing Browser */}
      <div className="w-full md:w-80 border-b md:border-b-0 md:border-r border-zinc-900 bg-zinc-950 flex flex-col p-4 gap-4 shrink-0">
        
        {/* Title Deck */}
        <div className="flex items-center justify-between border-b border-zinc-900 pb-3">
          <div>
            <h1 className="text-sm font-semibold text-zinc-200 tracking-tight flex items-center gap-2">
              <Network className="h-4.5 w-4.5 text-zinc-400" />
              <span>Semantic Nodes</span>
            </h1>
            <p className="text-[10px] text-zinc-550 font-mono mt-0.5">({entities.length} Nodes registered)</p>
          </div>
          <button
            onClick={handleCreateEntityClick}
            className="flex h-7 w-7 items-center justify-center rounded-lg bg-zinc-100 hover:bg-zinc-200 text-zinc-950 transition-colors cursor-pointer outline-none"
            title="Create Entity Node"
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>

        {/* Filter Input controls */}
        <div className="flex flex-col gap-2">
          <div className="relative w-full">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-zinc-650" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search entities..."
              className="w-full rounded-lg border border-zinc-800 bg-zinc-950 pl-8.5 pr-3 py-2 text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-zinc-700 transition-colors font-mono"
            />
          </div>

          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="w-full rounded-lg border border-zinc-800 bg-zinc-950 px-2.5 py-1.5 text-xs text-zinc-400 outline-none focus:border-zinc-750 transition-colors cursor-pointer"
          >
            <option value="">All Categories</option>
            <option value="PERSON">PERSON</option>
            <option value="ORGANIZATION">ORGANIZATION</option>
            <option value="PROJECT">PROJECT</option>
            <option value="TECHNOLOGY">TECHNOLOGY</option>
            <option value="FRAMEWORK">FRAMEWORK</option>
            <option value="DATABASE">DATABASE</option>
            <option value="API">API</option>
            <option value="DOCUMENT">DOCUMENT</option>
            <option value="CUSTOM">CUSTOM</option>
          </select>
        </div>

        {/* Entity List scrollbox */}
        <div className="flex-1 overflow-y-auto pr-1">
          {filteredEntities.length > 0 ? (
            <div className="flex flex-col gap-1">
              {filteredEntities.map((e) => {
                const isActive = e.id === selectedEntityId;
                return (
                  <button
                    key={e.id}
                    onClick={() => selectEntity(isActive ? null : e.id)}
                    className={cn(
                      "w-full text-left rounded-lg px-3 py-2 border text-xs font-mono transition-all duration-200 outline-none flex items-center justify-between gap-2 cursor-pointer",
                      isActive
                        ? "bg-zinc-900 border-zinc-800 text-zinc-100 shadow-sm"
                        : "text-zinc-400 hover:bg-zinc-900/40 hover:text-zinc-200 border-transparent"
                    )}
                  >
                    <span className="truncate">{e.name}</span>
                    <span className="text-[9px] uppercase tracking-wider text-zinc-600 px-1 py-0.5 rounded bg-zinc-900/20 border border-zinc-900/50 shrink-0">
                      {e.entity_type}
                    </span>
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="py-16 text-center text-xs text-zinc-650 font-mono">
              No matching nodes found.
            </div>
          )}
        </div>

        {/* Create Relationship Shortcut */}
        {entities.length >= 2 && (
          <button
            onClick={() => setIsRelOpen(true)}
            className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg border border-zinc-800 bg-zinc-950 hover:bg-zinc-900 text-zinc-300 hover:text-zinc-100 text-xs font-semibold tracking-tight transition-colors cursor-pointer outline-none mt-2"
          >
            <Link2 className="h-3.5 w-3.5" />
            <span>Connect Nodes</span>
          </button>
        )}
      </div>

      {/* 2. Center Panel: Visualizer & Traversal Controls */}
      <div className="flex-1 flex flex-col p-4 md:p-6 gap-6 min-h-0 border-b md:border-b-0 md:border-r border-zinc-900">
        
        {/* SVG Graph Visualizer container */}
        <div className="flex-1 min-h-0 flex flex-col">
          <GraphVisualizer
            entities={entities}
            relationships={relationships}
            selectedEntityId={selectedEntityId}
            onSelectEntity={selectEntity}
            shortestPath={shortestPath}
            traversalResult={traversalResult}
          />
        </div>

        {/* Path calculation controls */}
        <div className="shrink-0">
          <TraversalControls
            entities={entities}
            onFindPath={fetchShortestPath}
            onTraverse={runTraversal}
            onClear={clearTraversalAndPaths}
            activePath={shortestPath !== null}
            activeTraversal={traversalResult !== null}
            isLoading={isLoading}
          />
        </div>
      </div>

      {/* 3. Right Panel: Node Details & Relational Logs */}
      <div className="w-full md:w-80 bg-zinc-950 flex flex-col p-4 gap-4 shrink-0 overflow-y-auto">
        {activeEntity ? (
          <div className="flex flex-col gap-5">
            
            {/* Detail Card Header */}
            <div className="border-b border-zinc-900 pb-3 flex flex-col gap-2">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[9px] uppercase tracking-widest font-mono text-zinc-550">Node Details</span>
                <div className="flex gap-1">
                  <button
                    onClick={handleEditEntityClick}
                    className="p-1 rounded bg-zinc-900 border border-zinc-800 hover:bg-zinc-850 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer outline-none"
                    title="Edit Entity Node"
                  >
                    <Edit className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={handleDeleteEntity}
                    className="p-1 rounded bg-red-950/10 border border-red-900/40 hover:bg-red-950/20 text-red-400 transition-colors cursor-pointer outline-none"
                    title="Delete Entity"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
              <h2 className="text-base font-bold text-zinc-100 tracking-tight leading-tight">{activeEntity.name}</h2>
              <span className="inline-flex max-w-fit px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-850 text-[9px] font-mono text-zinc-400 uppercase tracking-widest">
                {activeEntity.entity_type}
              </span>
            </div>

            {/* Timing Stats */}
            <div className="flex flex-col gap-2.5 text-[10px] font-mono text-zinc-450 border border-zinc-900/80 bg-zinc-950/40 p-3 rounded-lg">
              <div className="flex items-center justify-between">
                <span className="text-zinc-600">Canonical:</span>
                <span className="text-zinc-300 font-semibold">{activeEntity.canonical_name || "N/A"}</span>
              </div>
              <div className="flex items-center justify-between border-t border-zinc-900 pt-2 mt-1">
                <span className="text-zinc-600">Registered:</span>
                <span>{new Date(activeEntity.created_at).toLocaleDateString()}</span>
              </div>
              <div className="flex items-center justify-between border-t border-zinc-900 pt-2 mt-1">
                <span className="text-zinc-600">Last Synced:</span>
                <span>{new Date(activeEntity.updated_at).toLocaleDateString()}</span>
              </div>
            </div>

            {/* Neighbors Connections */}
            <div className="flex flex-col gap-2 border-t border-zinc-900 pt-4">
              <span className="text-[9px] font-mono text-zinc-550 uppercase tracking-wider">Local Edges ({neighbors.length})</span>
              
              {neighbors.length > 0 ? (
                <div className="flex flex-col gap-1.5 max-h-[160px] overflow-y-auto pr-1">
                  {neighbors.map((n) => {
                    const isOutgoing = n.direction === "outgoing";
                    return (
                      <div
                        key={n.relationship.id}
                        className="flex flex-col gap-1 px-2.5 py-1.5 rounded-lg border border-zinc-900 bg-zinc-950/20 text-[10px] font-mono"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-zinc-650 text-[9px] uppercase tracking-wider">{n.relationship.relationship_type}</span>
                          <button
                            onClick={() => handleDeleteRelationship(n.relationship.id)}
                            className="text-zinc-600 hover:text-red-400 transition-colors cursor-pointer outline-none"
                            title="Delete connection edge"
                          >
                            <X className="h-3 w-3" />
                          </button>
                        </div>
                        <div className="flex items-center gap-1">
                          <span className="text-zinc-500">{isOutgoing ? "To:" : "From:"}</span>
                          <button
                            onClick={() => selectEntity(n.node.id)}
                            className="text-zinc-300 hover:text-zinc-100 hover:underline text-left truncate font-medium outline-none cursor-pointer"
                          >
                            {n.node.name}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <span className="text-[10px] text-zinc-650 font-mono italic">No local relationship links found.</span>
              )}
            </div>

            {/* Connected Memory logs */}
            <div className="flex flex-col gap-2 border-t border-zinc-900 pt-4">
              <span className="text-[9px] font-mono text-zinc-550 uppercase tracking-wider">Connected Memories ({connectedMemories.length})</span>
              
              {connectedMemories.length > 0 ? (
                <div className="flex flex-col gap-2 max-h-[180px] overflow-y-auto pr-1">
                  {connectedMemories.map((m) => (
                    <Link
                      key={m.id}
                      href={`/memories/${m.id}`}
                      className="flex flex-col gap-1 p-2 rounded-lg border border-zinc-900 bg-zinc-950/10 hover:bg-zinc-900/40 text-[10px] font-mono transition-colors group"
                      title="Inspect full memory details"
                    >
                      <div className="flex items-center justify-between text-[9px] text-zinc-600">
                        <span>{new Date(m.created_at).toLocaleDateString()}</span>
                        <ChevronRight className="h-3.5 w-3.5 text-zinc-750 group-hover:text-zinc-400 transition-colors" />
                      </div>
                      <p className="text-zinc-400 group-hover:text-zinc-300 transition-colors truncate font-sans text-xs leading-normal">
                        {m.content}
                      </p>
                    </Link>
                  ))}
                </div>
              ) : (
                <span className="text-[10px] text-zinc-650 font-mono italic">No memory context mappings.</span>
              )}
            </div>

            {/* Raw Metadata Payload */}
            {Object.keys(activeEntity.metadata).length > 0 && (
              <div className="flex flex-col gap-2 border-t border-zinc-900 pt-4">
                <span className="text-[9px] font-mono text-zinc-550 uppercase tracking-wider">Metadata Payload</span>
                <pre className="text-[10px] font-mono text-zinc-350 bg-zinc-900/10 border border-zinc-900/60 p-2.5 rounded-lg overflow-x-auto max-h-[140px] leading-normal">
                  {JSON.stringify(activeEntity.metadata, null, 2)}
                </pre>
              </div>
            )}

          </div>
        ) : (
          <div className="flex-grow flex flex-col items-center justify-center text-center p-6 my-auto text-zinc-600 font-mono text-xs">
            <HelpCircle className="h-6 w-6 text-zinc-800 mb-2" />
            <span>Select a node on the visualization window to browse details, connected memories, and neighbor paths.</span>
          </div>
        )}
      </div>

      {/* 4. Global Error alert box inside center panel */}
      {error && (
        <div className="fixed bottom-4 right-4 z-50 p-3 bg-red-950/20 border border-red-900/35 rounded-lg text-xs font-mono text-red-400 shadow-xl max-w-sm flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-red-500 shrink-0" />
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* Entity Modal Dialog */}
      <EntityFormDialog
        isOpen={isEntityOpen}
        onClose={() => setIsEntityOpen(false)}
        onSubmit={handleEntitySubmit}
        initialData={entityFormEditData}
        isSubmitting={submittingEntity}
      />

      {/* Relationship Modal Dialog */}
      <RelationshipFormDialog
        isOpen={isRelOpen}
        onClose={() => setIsRelOpen(false)}
        onSubmit={handleRelationshipSubmit}
        entities={entities}
        isSubmitting={submittingRel}
      />

    </div>
  );
}
