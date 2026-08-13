"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { memoriesApi, UpdateMemoryPayload, CreateMemoryPayload } from "@/lib/api/memories";
import { Memory, MemoryAnalytics } from "@/types";
import MemoryStatusBadge from "@/components/memory/MemoryStatusBadge";
import MemoryForm from "@/components/memory/MemoryForm";
import DeleteMemoryDialog from "@/components/memory/DeleteMemoryDialog";
import MemoryAnalyticsView from "@/components/memory/MemoryAnalytics";
import { ApiError } from "@/lib/api/client";
import { 
  ChevronLeft, 
  Edit3, 
  Trash2, 
  Sparkles, 
  Calendar, 
  Clock, 
  Database,
  CheckCircle,
  AlertTriangle
} from "lucide-react";

export default function MemoryDetailPage() {
  const params = useParams();
  const router = useRouter();
  const memoryId = params.memory_id as string;

  // Data states
  const [memory, setMemory] = useState<Memory | null>(null);
  const [analytics, setAnalytics] = useState<MemoryAnalytics | null>(null);

  // UI States
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  
  const [isEditing, setIsEditing] = useState(false);
  const [editSubmitting, setEditSubmitting] = useState(false);
  
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [deleteSubmitting, setDeleteSubmitting] = useState(false);

  const [reinforceLoading, setReinforceLoading] = useState(false);
  const [actionSuccessMsg, setActionSuccessMsg] = useState<string | null>(null);

  // Fetch full memory state
  const loadData = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [memData, analData] = await Promise.all([
        memoriesApi.getMemory(memoryId),
        memoriesApi.getMemoryAnalytics(memoryId),
      ]);
      setMemory(memData);
      setAnalytics(analData);
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMsg(err.message);
      } else {
        setErrorMsg("Failed to retrieve memory details.");
      }
    } finally {
      setLoading(false);
    }
  }, [memoryId]);

  useEffect(() => {
    if (memoryId) {
      const timer = setTimeout(() => {
        loadData();
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [memoryId, loadData]);

  // Actions
  const handleEditSubmit = async (data: UpdateMemoryPayload | CreateMemoryPayload) => {
    const payload = data as UpdateMemoryPayload;
    setEditSubmitting(true);
    try {
      const updated = await memoriesApi.updateMemory(memoryId, payload);
      setMemory(updated);
      setIsEditing(false);
      // Reload analytics to update last_accessed/updated timestamps
      const analData = await memoriesApi.getMemoryAnalytics(memoryId);
      setAnalytics(analData);
      showActionSuccess("Memory updated successfully.");
    } catch (err) {
      if (err instanceof ApiError) {
        alert(`API Error: ${err.message}`);
      } else {
        alert("Failed to save changes.");
      }
    } finally {
      setEditSubmitting(false);
    }
  };

  const handleDeleteConfirm = async () => {
    setDeleteSubmitting(true);
    try {
      await memoriesApi.deleteMemory(memoryId);
      setIsDeleteOpen(false);
      router.push("/memories");
    } catch (err) {
      if (err instanceof ApiError) {
        alert(`Delete failed: ${err.message}`);
      } else {
        alert("Delete failed.");
      }
    } finally {
      setDeleteSubmitting(false);
    }
  };

  const handleReinforce = async () => {
    setReinforceLoading(true);
    try {
      await memoriesApi.reinforceMemory(memoryId);
      // Refresh analytics
      const analData = await memoriesApi.getMemoryAnalytics(memoryId);
      setAnalytics(analData);
      showActionSuccess("Memory reinforced successfully.");
    } catch {
      alert("Failed to reinforce memory.");
    } finally {
      setReinforceLoading(false);
    }
  };

  const showActionSuccess = (msg: string) => {
    setActionSuccessMsg(msg);
    setTimeout(() => setActionSuccessMsg(null), 4000);
  };

  if (loading) {
    return (
      <div className="flex-grow flex flex-col items-center justify-center p-6 text-zinc-400">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-zinc-900 border border-zinc-800 text-zinc-100 animate-pulse">
          <Database className="h-5 w-5 animate-spin text-zinc-400" />
        </div>
        <div className="mt-4 text-xs font-mono tracking-widest text-zinc-500 uppercase animate-pulse">
          Loading Memory Details...
        </div>
      </div>
    );
  }

  if (errorMsg || !memory) {
    return (
      <div className="p-6 max-w-lg mx-auto my-12 flex flex-col items-center text-center">
        <AlertTriangle className="h-10 w-10 text-red-500 mb-3" />
        <h2 className="text-sm font-semibold text-zinc-300">Workspace Error</h2>
        <p className="text-xs text-zinc-500 mt-1 leading-normal font-mono">{errorMsg || "Memory not found."}</p>
        <button
          onClick={() => router.push("/memories")}
          className="mt-5 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-850 hover:bg-zinc-800 text-xs font-semibold text-zinc-300 transition-colors cursor-pointer outline-none"
        >
          <ChevronLeft className="h-4 w-4" />
          <span>Back to Workspace</span>
        </button>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-zinc-950 p-4 md:p-6">
      {/* Top Header Deck */}
      <div className="flex items-center justify-between gap-4 flex-wrap border-b border-zinc-900 pb-4 mb-6">
        <button
          onClick={() => router.push("/memories")}
          className="flex items-center gap-1 text-xs font-mono text-zinc-500 hover:text-zinc-350 transition-colors cursor-pointer outline-none"
        >
          <ChevronLeft className="h-4 w-4" />
          <span>Back to workspace</span>
        </button>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          {actionSuccessMsg && (
            <div className="mr-2 flex items-center gap-1.5 px-3 py-1 rounded bg-zinc-900 border border-zinc-850 text-[10px] font-mono text-zinc-400 shadow-md">
              <CheckCircle className="h-3.5 w-3.5 text-emerald-500" />
              <span>{actionSuccessMsg}</span>
            </div>
          )}

          <button
            onClick={() => setIsEditing(!isEditing)}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded border border-zinc-800 bg-zinc-900/40 hover:bg-zinc-900 text-zinc-400 hover:text-zinc-200 transition-colors text-xs font-medium cursor-pointer outline-none"
          >
            <Edit3 className="h-3.5 w-3.5" />
            <span>{isEditing ? "View Details" : "Edit"}</span>
          </button>
          
          <button
            onClick={handleReinforce}
            disabled={reinforceLoading}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded border border-zinc-800 bg-zinc-900/40 hover:bg-zinc-900 text-zinc-400 hover:text-zinc-200 transition-colors text-xs font-medium cursor-pointer disabled:opacity-50 outline-none"
            title="Increase reinforcement state counters"
          >
            <Sparkles className="h-3.5 w-3.5" />
            <span>{reinforceLoading ? "Reinforcing..." : "Reinforce"}</span>
          </button>

          {memory.status !== "DELETED" && (
            <button
              onClick={() => setIsDeleteOpen(true)}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded border border-red-900/40 bg-red-950/10 hover:bg-red-950/20 text-red-400 transition-colors text-xs font-medium cursor-pointer outline-none"
            >
              <Trash2 className="h-3.5 w-3.5" />
              <span>Soft Delete</span>
            </button>
          )}
        </div>
      </div>

      {/* Main split dashboard view */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-0 overflow-y-auto pr-1">
        {/* Left Column: Form or Content Description */}
        <div className="lg:col-span-7 flex flex-col gap-6">
          {isEditing ? (
            <div className="border border-zinc-900 bg-zinc-950/40 rounded-xl p-5 md:p-6 shadow-sm">
              <h2 className="text-xs font-semibold text-zinc-200 tracking-tight uppercase tracking-wider font-mono border-b border-zinc-900 pb-3 mb-4">
                Modify Memory Parameters
              </h2>
              <MemoryForm
                initialData={memory}
                onSubmit={handleEditSubmit}
                onCancel={() => setIsEditing(false)}
                isSubmitting={editSubmitting}
              />
            </div>
          ) : (
            <div className="flex flex-col gap-6">
              {/* Detailed quote content card */}
              <div className="border border-zinc-900 bg-zinc-950 rounded-xl p-5 md:p-6 shadow-sm">
                <div className="flex items-center justify-between gap-4 flex-wrap border-b border-zinc-900 pb-3 mb-4 text-xs font-mono text-zinc-500">
                  <div className="flex items-center gap-2">
                    <MemoryStatusBadge value={memory.memory_system} type="system" />
                    <MemoryStatusBadge value={memory.memory_type} type="type" />
                  </div>
                  <MemoryStatusBadge value={memory.status} type="status" />
                </div>
                
                <h3 className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest mb-2.5">Factual Content</h3>
                <p className="text-sm md:text-base text-zinc-200 leading-relaxed font-sans whitespace-pre-wrap">
                  {memory.content}
                </p>
              </div>

              {/* Timing Metadata stats */}
              <div className="border border-zinc-900 bg-zinc-950 rounded-xl p-5 md:p-6 shadow-sm flex flex-col gap-3.5 text-xs font-mono text-zinc-400">
                <h4 className="text-[10px] uppercase tracking-widest text-zinc-500 font-mono flex items-center gap-1.5">
                  <Calendar className="h-3.5 w-3.5 text-zinc-650" />
                  <span>Relational Metadata</span>
                </h4>
                
                <div className="flex flex-col gap-2.5 mt-1">
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-500">Memory ID:</span>
                    <span className="text-zinc-300 font-mono text-[11px] truncate max-w-[200px] sm:max-w-none">{memory.id}</span>
                  </div>
                  {memory.conversation_id && (
                    <div className="flex items-center justify-between border-t border-zinc-900 pt-2">
                      <span className="text-zinc-500">Conversation context:</span>
                      <span className="text-zinc-350 font-mono text-[11px] truncate max-w-[200px] sm:max-w-none">{memory.conversation_id}</span>
                    </div>
                  )}
                  <div className="flex items-center justify-between border-t border-zinc-900 pt-2">
                    <span className="text-zinc-500">Importance Rating:</span>
                    <span className="text-zinc-200 font-semibold">{Math.round(memory.importance * 100)}%</span>
                  </div>
                  <div className="flex items-center justify-between border-t border-zinc-900 pt-2">
                    <span className="text-zinc-500">Confidence Score:</span>
                    <span className="text-zinc-200 font-semibold">{Math.round(memory.confidence * 100)}%</span>
                  </div>
                  <div className="flex items-center justify-between border-t border-zinc-900 pt-2">
                    <span className="text-zinc-500">Creation Timestamp:</span>
                    <span className="text-zinc-300">{new Date(memory.created_at).toLocaleString()}</span>
                  </div>
                  <div className="flex items-center justify-between border-t border-zinc-900 pt-2">
                    <span className="text-zinc-500">Last Modified:</span>
                    <span className="text-zinc-300">{new Date(memory.updated_at).toLocaleString()}</span>
                  </div>
                  {memory.occurred_at && (
                    <div className="flex items-center justify-between border-t border-zinc-900 pt-2">
                      <span className="text-zinc-500">Event Occurred At:</span>
                      <span className="text-zinc-300">{new Date(memory.occurred_at).toLocaleString()}</span>
                    </div>
                  )}
                  {memory.expires_at && (
                    <div className="flex items-center justify-between border-t border-zinc-900 pt-2">
                      <span className="text-zinc-500">Expiry (Working Memory):</span>
                      <span className="text-zinc-300 border border-rose-900/30 px-1 py-0.5 rounded bg-rose-950/20 text-rose-400">{new Date(memory.expires_at).toLocaleString()}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* raw json metadata */}
              <div className="border border-zinc-900 bg-zinc-950 rounded-xl p-5 md:p-6 shadow-sm flex flex-col gap-2.5">
                <h4 className="text-[10px] uppercase tracking-widest text-zinc-500 font-mono flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5 text-zinc-650" />
                  <span>Metadata JSON Payload</span>
                </h4>
                <pre className="mt-1 text-[11px] font-mono text-zinc-350 bg-zinc-900/20 border border-zinc-900/60 p-3 rounded-lg overflow-x-auto leading-normal">
                  {JSON.stringify(memory.metadata, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Access History & Analytics logs */}
        <div className="lg:col-span-5 flex flex-col gap-6">
          <div className="border border-zinc-900 bg-zinc-950/50 rounded-xl p-5 shadow-sm">
            {analytics ? (
              <MemoryAnalyticsView analytics={analytics} />
            ) : (
              <div className="py-12 text-center text-xs text-zinc-500 font-mono">
                Failed to load analytics dashboard.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Soft Delete Dialog confirmation overlay */}
      <DeleteMemoryDialog
        isOpen={isDeleteOpen}
        onClose={() => setIsDeleteOpen(false)}
        onConfirm={handleDeleteConfirm}
        isDeleting={deleteSubmitting}
      />
    </div>
  );
}
