"use client";

import { useEffect, useState, useCallback } from "react";
import { memoriesApi, ListMemoriesParams, CreateMemoryPayload, UpdateMemoryPayload } from "@/lib/api/memories";
import { Memory, MemoryType, MemoryStatus, MemorySearchResponse } from "@/types";
import MemoryCard from "@/components/memory/MemoryCard";
import MemoryForm from "@/components/memory/MemoryForm";
import { ApiError } from "@/lib/api/client";
import { 
  Search, 
  RotateCw, 
  Plus, 
  ChevronLeft, 
  ChevronRight, 
  Database, 
  Cpu, 
  Flame,
  Binary
} from "lucide-react";

export default function MemoriesPage() {
  // Navigation & Query States
  const [memories, setMemories] = useState<Memory[]>([]);
  const [searchResults, setSearchResults] = useState<MemorySearchResponse[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeSearch, setActiveSearch] = useState(false);

  // Filter params
  const [filterType, setFilterType] = useState<MemoryType | "">("");
  const [filterStatus, setFilterStatus] = useState<MemoryStatus | "">("ACTIVE");
  const [sortBy, setSortBy] = useState<ListMemoriesParams["sort_by"]>("created_at");
  const [sortOrder, setSortOrder] = useState<ListMemoriesParams["sort_order"]>("desc");
  const [page, setPage] = useState(1);
  const [limit] = useState(12); // Grid sizing fit

  // UI Status
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [diagnosticMsg, setDiagnosticMsg] = useState<string | null>(null);

  // Fetch standard memories
  const loadMemories = useCallback(async () => {
    await Promise.resolve(); // Defers state changes out of the synchronous render pathway
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await memoriesApi.listMemories({
        memory_type: filterType,
        status: filterStatus,
        page,
        limit,
        sort_by: sortBy,
        sort_order: sortOrder,
      });
      setMemories(data);
      setActiveSearch(false);
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMsg(err.message);
      } else {
        setErrorMsg("Failed to connect to the memory service.");
      }
    } finally {
      setLoading(false);
    }
  }, [filterType, filterStatus, page, limit, sortBy, sortOrder]);

  // Execute standard list loading
  useEffect(() => {
    if (!searchQuery.trim()) {
      const timer = setTimeout(() => {
        loadMemories();
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [loadMemories, searchQuery]);

  // Semantic search trigger
  const handleSearchSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) {
      loadMemories();
      return;
    }

    setLoading(true);
    setErrorMsg(null);
    try {
      const results = await memoriesApi.searchMemories(searchQuery, 10, filterType);
      setSearchResults(results);
      setActiveSearch(true);
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMsg(err.message);
      } else {
        setErrorMsg("Search operation failed on backend.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleClearSearch = () => {
    setSearchQuery("");
    setActiveSearch(false);
    setPage(1);
    loadMemories();
  };

  const handleCreateMemorySubmit = async (data: CreateMemoryPayload | UpdateMemoryPayload) => {
    const payload = data as CreateMemoryPayload;
    setCreateSubmitting(true);
    try {
      await memoriesApi.createMemory(payload);
      setIsCreateOpen(false);
      setPage(1);
      loadMemories();
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMsg(err.message);
      } else {
        setErrorMsg("Failed to submit memory to database.");
      }
    } finally {
      setCreateSubmitting(false);
    }
  };

  // Diagnostic actions
  const triggerDecayCycle = async () => {
    try {
      const res = await memoriesApi.triggerDecay();
      showDiagnosticToast(`Decay cycle complete. Updated ${res.updated_count} memories.`);
      loadMemories();
    } catch {
      showDiagnosticToast("Decay trigger failed.");
    }
  };

  const triggerVectorReindexing = async () => {
    try {
      const res = await memoriesApi.triggerReindex();
      showDiagnosticToast(`Reindexed ${res.reindexed_count} memories.`);
    } catch {
      showDiagnosticToast("Reindexing trigger failed.");
    }
  };

  const showDiagnosticToast = (msg: string) => {
    setDiagnosticMsg(msg);
    setTimeout(() => setDiagnosticMsg(null), 4000);
  };

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-zinc-950 p-4 md:p-6 justify-between">
      {/* Title & Create Controls Header */}
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between gap-4 flex-wrap border-b border-zinc-900 pb-4">
          <div>
            <h1 className="text-xl font-bold text-zinc-100 tracking-tight flex items-center gap-2">
              <Database className="h-5 w-5 text-zinc-400" />
              <span>Memory Workspace</span>
            </h1>
            <p className="text-xs text-zinc-500 mt-1">
              Explore and orchestrate cognitive records stored in your semantic memory graph.
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => setIsCreateOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-100 hover:bg-zinc-200 text-zinc-950 font-medium text-xs transition-colors cursor-pointer outline-none"
            >
              <Plus className="h-4 w-4" />
              <span>Create Memory</span>
            </button>
          </div>
        </div>

        {/* Diagnostics & Search filters row */}
        <div className="flex flex-col gap-4 bg-zinc-900/10 border border-zinc-900/60 p-4 rounded-xl">
          {/* Action Row 1: Search Form */}
          <form onSubmit={handleSearchSubmit} className="flex gap-2 w-full">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-zinc-650" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Enter query for semantic search... (Press enter or click search)"
                className="w-full rounded-lg border border-zinc-800 bg-zinc-950 pl-9 pr-3 py-2 text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-zinc-700 transition-colors font-mono"
              />
            </div>
            <button
              type="submit"
              className="px-3.5 py-2 text-xs font-semibold rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 hover:bg-zinc-850 transition-colors cursor-pointer outline-none"
            >
              Search
            </button>
            {activeSearch && (
              <button
                type="button"
                onClick={handleClearSearch}
                className="px-3 py-2 text-xs text-zinc-500 hover:text-zinc-350 transition-colors outline-none cursor-pointer"
              >
                Clear
              </button>
            )}
          </form>

          {/* Action Row 2: Sort, Filter, Settings */}
          <div className="flex items-center justify-between gap-4 flex-wrap text-xs text-zinc-400">
            <div className="flex items-center gap-3.5 flex-wrap">
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] font-mono text-zinc-550 uppercase">Type:</span>
                <select
                  value={filterType}
                  onChange={(e) => {
                    setFilterType(e.target.value as MemoryType | "");
                    setPage(1);
                  }}
                  className="rounded border border-zinc-805 bg-zinc-950 px-2 py-1 outline-none text-zinc-300 transition-colors cursor-pointer"
                >
                  <option value="">All Types</option>
                  <option value="Fact">Fact</option>
                  <option value="Preference">Preference</option>
                  <option value="Goal">Goal</option>
                  <option value="Task">Task</option>
                  <option value="Profile">Profile</option>
                  <option value="Relationship">Relationship</option>
                  <option value="Skill">Skill</option>
                  <option value="Instruction">Instruction</option>
                  <option value="Event">Event</option>
                </select>
              </div>

              {!activeSearch && (
                <>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] font-mono text-zinc-550 uppercase">Status:</span>
                    <select
                      value={filterStatus}
                      onChange={(e) => {
                        setFilterStatus(e.target.value as MemoryStatus | "");
                        setPage(1);
                      }}
                      className="rounded border border-zinc-805 bg-zinc-950 px-2 py-1 outline-none text-zinc-300 transition-colors cursor-pointer"
                    >
                      <option value="ACTIVE">ACTIVE</option>
                      <option value="ARCHIVED">ARCHIVED</option>
                      <option value="DELETED">DELETED</option>
                      <option value="">ALL STATES</option>
                    </select>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] font-mono text-zinc-555 uppercase">Sort By:</span>
                    <select
                      value={sortBy}
                      onChange={(e) => setSortBy(e.target.value as ListMemoriesParams["sort_by"])}
                      className="rounded border border-zinc-805 bg-zinc-950 px-2 py-1 outline-none text-zinc-300 transition-colors cursor-pointer"
                    >
                      <option value="created_at">Created Date</option>
                      <option value="updated_at">Updated Date</option>
                      <option value="importance">Importance</option>
                      <option value="confidence">Confidence</option>
                    </select>
                  </div>

                  <select
                    value={sortOrder}
                    onChange={(e) => setSortOrder(e.target.value as ListMemoriesParams["sort_order"])}
                    className="rounded border border-zinc-805 bg-zinc-950 px-2 py-1 outline-none text-zinc-300 transition-colors cursor-pointer"
                  >
                    <option value="desc">Descending</option>
                    <option value="asc">Ascending</option>
                  </select>
                </>
              )}
            </div>

            {/* Diagnostic system execution controls */}
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={triggerDecayCycle}
                className="flex items-center gap-1 px-2.5 py-1 rounded border border-zinc-800 bg-zinc-950 hover:bg-zinc-900 text-zinc-400 hover:text-zinc-200 transition-colors text-[10px] font-mono cursor-pointer outline-none"
                title="Manually trigger database decay rate reduction cycle"
              >
                <Flame className="h-3 w-3" />
                <span>Decay</span>
              </button>
              <button
                type="button"
                onClick={triggerVectorReindexing}
                className="flex items-center gap-1 px-2.5 py-1 rounded border border-zinc-800 bg-zinc-950 hover:bg-zinc-900 text-zinc-400 hover:text-zinc-200 transition-colors text-[10px] font-mono cursor-pointer outline-none"
                title="Regenerate missing embeddings"
              >
                <Binary className="h-3 w-3" />
                <span>Reindex</span>
              </button>
              <button
                type="button"
                onClick={loadMemories}
                className="p-1 rounded border border-zinc-800 bg-zinc-950 hover:bg-zinc-900 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer outline-none"
                title="Reload List"
              >
                <RotateCw className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>

          {/* Diagnostic feedback toast inside search box */}
          {diagnosticMsg && (
            <div className="text-[10px] font-mono text-zinc-400 bg-zinc-950 border border-zinc-850 px-3 py-1.5 rounded-lg flex items-center gap-2">
              <Cpu className="h-3.5 w-3.5 text-zinc-650 animate-pulse" />
              <span>{diagnosticMsg}</span>
            </div>
          )}
        </div>
      </div>

      {/* Main Grid Viewport */}
      <div className="flex-1 min-h-0 overflow-y-auto mt-6">
        {loading ? (
          // Loading skeleton cards
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="border border-zinc-900/60 bg-zinc-950/40 rounded-xl p-5 flex flex-col justify-between h-48 animate-pulse">
                <div className="flex flex-col gap-3">
                  <div className="h-4.5 bg-zinc-900 rounded w-1/3" />
                  <div className="space-y-2 mt-1">
                    <div className="h-3.5 bg-zinc-900 rounded w-full" />
                    <div className="h-3.5 bg-zinc-900 rounded w-5/6" />
                  </div>
                </div>
                <div className="h-3.5 bg-zinc-900 rounded w-2/3 border-t border-transparent pt-3" />
              </div>
            ))}
          </div>
        ) : errorMsg ? (
          // Custom error view
          <div className="p-8 border border-dashed border-red-900/40 bg-red-950/5 rounded-xl text-center flex flex-col items-center justify-center max-w-md mx-auto my-12">
            <span className="text-red-400 font-semibold text-sm">Memory Service Failure</span>
            <p className="text-xs text-zinc-550 mt-1 leading-normal font-mono">{errorMsg}</p>
            <button
              onClick={loadMemories}
              className="mt-4 px-3 py-1.5 rounded bg-red-900/20 border border-red-900/40 text-red-400 text-xs font-medium hover:bg-red-900/30 transition-colors cursor-pointer outline-none"
            >
              Retry Connection
            </button>
          </div>
        ) : activeSearch ? (
          // Search Results View
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-2 text-xs font-mono text-zinc-500">
              <span>Semantic Search Results for query: </span>
              <span className="text-zinc-350 italic">&quot;{searchQuery}&quot;</span>
              <span>({searchResults.length} matches)</span>
            </div>
            
            {searchResults.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {searchResults.map(({ memory, similarity }) => (
                  <div key={memory.id} className="relative group">
                    <MemoryCard memory={memory} />
                    <span className="absolute top-2.5 right-2.5 inline-flex px-1.5 py-0.5 rounded bg-zinc-900/90 border border-zinc-800 text-[9px] font-mono text-zinc-400" title={`Cosine Similarity Match`}>
                      sim: {similarity.toFixed(4)}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-16 text-center text-xs text-zinc-500 font-mono">
                No semantic matches found for this query.
              </div>
            )}
          </div>
        ) : memories.length > 0 ? (
          // Standard Paginated List Grid
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {memories.map((m) => (
              <MemoryCard key={m.id} memory={m} />
            ))}
          </div>
        ) : (
          // Empty State View
          <div className="py-20 text-center flex flex-col items-center justify-center max-w-md mx-auto">
            <div className="h-10 w-10 rounded-lg bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-500 mb-3">
              <Database className="h-5 w-5" />
            </div>
            <h3 className="text-sm font-semibold text-zinc-300">No memories found</h3>
            <p className="text-xs text-zinc-500 mt-1 max-w-xs leading-relaxed">
              No long-term memories belong to this query state. Create a memory to populate the canvas.
            </p>
            <button
              onClick={() => setIsCreateOpen(true)}
              className="mt-4 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 hover:bg-zinc-850 text-xs font-semibold transition-colors cursor-pointer outline-none"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Create Memory</span>
            </button>
          </div>
        )}
      </div>

      {/* Footer Pagination (Only when standard list is active) */}
      {!activeSearch && !loading && !errorMsg && memories.length > 0 && (
        <div className="flex items-center justify-between border-t border-zinc-900 pt-5 mt-6 text-xs text-zinc-500 font-mono">
          <span>Page {page}</span>
          
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-950 text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200 transition-colors disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer outline-none"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={memories.length < limit}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-950 text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200 transition-colors disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer outline-none"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* 4. Create Memory Modal Popup */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="fixed inset-0 bg-black/60 backdrop-blur-xs" onClick={() => setIsCreateOpen(false)} aria-hidden="true" />
          <div className="relative w-full max-w-xl bg-zinc-950 border border-zinc-800 rounded-xl p-5 md:p-6 shadow-2xl z-10 overflow-y-auto max-h-[90vh]">
            <h2 className="text-sm font-semibold text-zinc-200 tracking-tight uppercase tracking-wider font-mono border-b border-zinc-900 pb-3 mb-4">
              Add Cognitive Memory
            </h2>
            <MemoryForm
              onSubmit={handleCreateMemorySubmit}
              onCancel={() => setIsCreateOpen(false)}
              isSubmitting={createSubmitting}
            />
          </div>
        </div>
      )}
    </div>
  );
}
