import { useState, useEffect } from "react";
import { Entity } from "@/types";
import { Loader2, Route, Trees, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface TraversalControlsProps {
  entities: Entity[];
  onFindPath: (sourceId: string, targetId: string) => Promise<void>;
  onTraverse: (startId: string, depth: number) => Promise<void>;
  onClear: () => void;
  activePath: boolean;
  activeTraversal: boolean;
  isLoading: boolean;
}

export default function TraversalControls({
  entities,
  onFindPath,
  onTraverse,
  onClear,
  activePath,
  activeTraversal,
  isLoading,
}: TraversalControlsProps) {
  // Path states
  const [pathSource, setPathSource] = useState("");
  const [pathTarget, setPathTarget] = useState("");

  // Traversal states
  const [traverseStart, setTraverseStart] = useState("");
  const [traverseDepth, setTraverseDepth] = useState(2);

  // Sync initial dropdown parameters when entities load
  useEffect(() => {
    if (entities.length >= 2) {
      Promise.resolve().then(() => {
        if (!pathSource) setPathSource(entities[0].id);
        if (!pathTarget) setPathTarget(entities[1].id);
        if (!traverseStart) setTraverseStart(entities[0].id);
      });
    } else if (entities.length === 1) {
      Promise.resolve().then(() => {
        if (!pathSource) setPathSource(entities[0].id);
        if (!traverseStart) setTraverseStart(entities[0].id);
      });
    }
  }, [entities, pathSource, pathTarget, traverseStart]);

  const handleFindPathSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!pathSource || !pathTarget) return;
    onFindPath(pathSource, pathTarget);
  };

  const handleTraverseSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!traverseStart) return;
    onTraverse(traverseStart, traverseDepth);
  };

  const isEnabled = entities.length > 0;

  return (
    <div className="border border-zinc-900 bg-zinc-950 p-4 rounded-xl flex flex-col gap-4 font-mono text-xs text-zinc-400">
      <div className="flex items-center justify-between border-b border-zinc-900 pb-2">
        <span className="text-[10px] uppercase tracking-wider text-zinc-550 font-bold">Graph Operations Deck</span>
        {(activePath || activeTraversal) && (
          <button
            onClick={onClear}
            className="flex items-center gap-1 text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors cursor-pointer outline-none"
            title="Reset highlight layers"
          >
            <X className="h-3.5 w-3.5" />
            <span>Clear Highlights</span>
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 1. Shortest Path Section */}
        <form onSubmit={handleFindPathSubmit} className="flex flex-col gap-3">
          <div className="flex items-center gap-1.5 text-zinc-300 font-semibold border-b border-transparent pb-0.5">
            <Route className="h-4 w-4 text-zinc-500" />
            <span>Find Shortest Path (Dijkstra)</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            <div className="flex flex-col gap-1">
              <label htmlFor="path-src" className="text-[9px] text-zinc-600 uppercase">Start Node</label>
              <select
                id="path-src"
                value={pathSource}
                onChange={(e) => setPathSource(e.target.value)}
                className="w-full rounded border border-zinc-850 bg-zinc-950 px-2 py-1 outline-none text-zinc-300 transition-colors cursor-pointer"
                disabled={!isEnabled || isLoading}
              >
                {entities.map((e) => (
                  <option key={e.id} value={e.id} className="bg-zinc-950">{e.name}</option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-1">
              <label htmlFor="path-tgt" className="text-[9px] text-zinc-600 uppercase">Target Node</label>
              <select
                id="path-tgt"
                value={pathTarget}
                onChange={(e) => setPathTarget(e.target.value)}
                className="w-full rounded border border-zinc-850 bg-zinc-950 px-2 py-1 outline-none text-zinc-300 transition-colors cursor-pointer"
                disabled={!isEnabled || isLoading}
              >
                {entities.map((e) => (
                  <option key={e.id} value={e.id} className="bg-zinc-950">{e.name}</option>
                ))}
              </select>
            </div>
          </div>

          <button
            type="submit"
            disabled={!isEnabled || isLoading || !pathSource || !pathTarget}
            className={cn(
              "mt-1 py-1.5 rounded font-semibold text-center transition-all duration-200 outline-none border cursor-pointer flex items-center justify-center gap-1.5",
              isEnabled && !isLoading
                ? "bg-zinc-900 border-zinc-800 text-zinc-300 hover:bg-zinc-850 hover:text-zinc-100"
                : "bg-zinc-950 border-zinc-900 text-zinc-600 cursor-not-allowed"
            )}
          >
            {isLoading && activePath && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            <span>Calculate Shortest Path</span>
          </button>
        </form>

        {/* 2. BFS Traversal Section */}
        <form onSubmit={handleTraverseSubmit} className="flex flex-col gap-3">
          <div className="flex items-center gap-1.5 text-zinc-300 font-semibold border-b border-transparent pb-0.5">
            <Trees className="h-4 w-4 text-zinc-500" />
            <span>Semantic Graph Traversal (BFS)</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
            <div className="flex flex-col gap-1 sm:col-span-2">
              <label htmlFor="trav-start" className="text-[9px] text-zinc-600 uppercase">Starting Node</label>
              <select
                id="trav-start"
                value={traverseStart}
                onChange={(e) => setTraverseStart(e.target.value)}
                className="w-full rounded border border-zinc-850 bg-zinc-950 px-2 py-1 outline-none text-zinc-300 transition-colors cursor-pointer"
                disabled={!isEnabled || isLoading}
              >
                {entities.map((e) => (
                  <option key={e.id} value={e.id} className="bg-zinc-950">{e.name}</option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-1">
              <label htmlFor="trav-depth" className="text-[9px] text-zinc-600 uppercase">Max Depth</label>
              <select
                id="trav-depth"
                value={traverseDepth}
                onChange={(e) => setTraverseDepth(Number(e.target.value))}
                className="w-full rounded border border-zinc-850 bg-zinc-950 px-2 py-1 outline-none text-zinc-300 transition-colors cursor-pointer"
                disabled={!isEnabled || isLoading}
              >
                <option value="1">1 Hop</option>
                <option value="2">2 Hops</option>
                <option value="3">3 Hops</option>
                <option value="4">4 Hops</option>
              </select>
            </div>
          </div>

          <button
            type="submit"
            disabled={!isEnabled || isLoading || !traverseStart}
            className={cn(
              "mt-1 py-1.5 rounded font-semibold text-center transition-all duration-200 outline-none border cursor-pointer flex items-center justify-center gap-1.5",
              isEnabled && !isLoading
                ? "bg-zinc-900 border-zinc-800 text-zinc-300 hover:bg-zinc-850 hover:text-zinc-100"
                : "bg-zinc-950 border-zinc-900 text-zinc-600 cursor-not-allowed"
            )}
          >
            {isLoading && activeTraversal && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            <span>Execute Traversal</span>
          </button>
        </form>
      </div>
    </div>
  );
}
