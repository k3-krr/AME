"use client";

import { useEffect, useState, useRef } from "react";
import { Entity, Relationship, EntityType, PathResponse, TraversalResponse } from "@/types";
import { 
  ZoomIn, 
  ZoomOut, 
  Maximize2, 
  RefreshCw, 
  User, 
  Building, 
  FolderGit, 
  Cpu, 
  Database, 
  FileCode, 
  HelpCircle,
  Link2,
  Share2
} from "lucide-react";
import { cn } from "@/lib/utils";

interface GraphVisualizerProps {
  entities: Entity[];
  relationships: Relationship[];
  selectedEntityId: string | null;
  onSelectEntity: (id: string | null) => void;
  shortestPath: PathResponse | null;
  traversalResult: TraversalResponse | null;
}

interface RenderNode {
  id: string;
  name: string;
  type: EntityType;
  x: number;
  y: number;
  vx: number;
  vy: number;
}

export default function GraphVisualizer({
  entities,
  relationships,
  selectedEntityId,
  onSelectEntity,
  shortestPath,
  traversalResult
}: GraphVisualizerProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  
  // Layout and zoom states
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [renderNodes, setRenderNodes] = useState<RenderNode[]>([]);
  const [layoutTrigger, setLayoutTrigger] = useState(0);

  // Dragging states
  const isDraggingBackground = useRef(false);
  const lastMousePos = useRef({ x: 0, y: 0 });
  const draggedNodeId = useRef<string | null>(null);

  // Physics simulation references
  const nodePositions = useRef<{ [id: string]: RenderNode }>({});

  // Highlights state lookup maps
  const pathNodeIds = new Set(shortestPath?.nodes.map((n) => n.id) || []);
  const pathRelIds = new Set(shortestPath?.relationships.map((r) => r.id) || []);
  const traversalNodeIds = new Set(traversalResult?.nodes.map((n) => n.node.id) || []);



  const getEntityColor = (type: EntityType, active: boolean, dimmed: boolean) => {
    if (dimmed) return "stroke-zinc-800 fill-zinc-900 text-zinc-700";
    
    switch (type) {
      case "PERSON":
        return active ? "stroke-blue-400 fill-blue-950/80" : "stroke-blue-800 fill-blue-950/20";
      case "ORGANIZATION":
        return active ? "stroke-emerald-400 fill-emerald-950/80" : "stroke-emerald-800 fill-emerald-950/20";
      case "PROJECT":
        return active ? "stroke-amber-400 fill-amber-950/80" : "stroke-amber-800 fill-amber-950/20";
      case "TECHNOLOGY":
        return active ? "stroke-purple-400 fill-purple-950/80" : "stroke-purple-800 fill-purple-950/20";
      case "FRAMEWORK":
        return active ? "stroke-indigo-400 fill-indigo-950/80" : "stroke-indigo-800 fill-indigo-950/20";
      case "DATABASE":
        return active ? "stroke-rose-400 fill-rose-950/80" : "stroke-rose-800 fill-rose-950/20";
      case "API":
        return active ? "stroke-orange-400 fill-orange-950/80" : "stroke-orange-800 fill-orange-950/20";
      case "DOCUMENT":
        return active ? "stroke-teal-400 fill-teal-950/80" : "stroke-teal-800 fill-teal-950/20";
      default:
        return active ? "stroke-zinc-300 fill-zinc-900" : "stroke-zinc-700 fill-zinc-950";
    }
  };

  const getEntityTypeIcon = (type: EntityType) => {
    switch (type) {
      case "PERSON": return User;
      case "ORGANIZATION": return Building;
      case "PROJECT": return FolderGit;
      case "TECHNOLOGY": return Cpu;
      case "DATABASE": return Database;
      case "API": return Link2;
      case "FRAMEWORK": return FileCode;
      default: return HelpCircle;
    }
  };

  // 1. Core Force-Directed Relaxation Simulation Effect
  useEffect(() => {
    if (entities.length === 0) {
      Promise.resolve().then(() => setRenderNodes([]));
      return;
    }

    const currentPositions = { ...nodePositions.current };
    
    // Seed new nodes dynamically in concentric structures
    entities.forEach((ent) => {
      if (!currentPositions[ent.id]) {
        const angle = Math.random() * Math.PI * 2;
        const radius = 50 + Math.random() * 150;
        currentPositions[ent.id] = {
          id: ent.id,
          name: ent.name,
          type: ent.entity_type,
          x: 400 + Math.cos(angle) * radius,
          y: 300 + Math.sin(angle) * radius,
          vx: 0,
          vy: 0,
        };
      } else {
        // Sync name/type attributes in case of updates
        currentPositions[ent.id].name = ent.name;
        currentPositions[ent.id].type = ent.entity_type;
      }
    });

    // Clear deleted nodes
    const activeIds = new Set(entities.map((e) => e.id));
    Object.keys(currentPositions).forEach((id) => {
      if (!activeIds.has(id)) delete currentPositions[id];
    });

    nodePositions.current = currentPositions;

    let ticks = 0;
    const maxTicks = 180; // Hard settling limit to prevent battery/CPU leak
    let animationFrameId: number;

    const simulateStep = () => {
      if (ticks >= maxTicks) return;
      ticks++;

      const nodes = Object.values(nodePositions.current);
      const links = relationships.filter(
        (r) => currentPositions[r.source_entity_id] && currentPositions[r.target_entity_id]
      );

      const centerX = 400;
      const centerY = 300;

      // Force 1: Coulomb Repulsion (push nodes apart)
      for (let i = 0; i < nodes.length; i++) {
        const u = nodes[i];
        for (let j = i + 1; j < nodes.length; j++) {
          const v = nodes[j];
          const dx = v.x - u.x;
          const dy = v.y - u.y;
          const distSq = dx * dx + dy * dy || 1;
          const dist = Math.sqrt(distSq);

          if (dist < 180) {
            const force = (180 - dist) * 0.12;
            const forceX = (dx / dist) * force;
            const forceY = (dy / dist) * force;

            u.vx -= forceX;
            u.vy -= forceY;
            v.vx += forceX;
            v.vy += forceY;
          }
        }
      }

      // Force 2: Hooke's Attraction (pull connected edges together)
      links.forEach((link) => {
        const srcNode = currentPositions[link.source_entity_id];
        const tgtNode = currentPositions[link.target_entity_id];

        const dx = tgtNode.x - srcNode.x;
        const dy = tgtNode.y - srcNode.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;

        const desiredLength = 110;
        const stiffness = 0.055;
        const force = (dist - desiredLength) * stiffness;
        const forceX = (dx / dist) * force;
        const forceY = (dy / dist) * force;

        srcNode.vx += forceX;
        srcNode.vy += forceY;
        tgtNode.vx -= forceX;
        tgtNode.vy -= forceY;
      });

      // Force 3: Center Gravity Pull & Friction damping updates
      nodes.forEach((n) => {
        n.vx += (centerX - n.x) * 0.007;
        n.vy += (centerY - n.y) * 0.007;

        n.vx *= 0.72;
        n.vy *= 0.72;

        if (n.id !== draggedNodeId.current) {
          n.x += n.vx;
          n.y += n.vy;
        }
      });

      setRenderNodes(nodes.map((n) => ({ ...n })));
      animationFrameId = requestAnimationFrame(simulateStep);
    };

    animationFrameId = requestAnimationFrame(simulateStep);
    return () => cancelAnimationFrame(animationFrameId);
  }, [entities, relationships, layoutTrigger]);

  // Coordinate Translation from Screen cursor to SVG coordinates
  const getSvgCoordinates = (clientX: number, clientY: number) => {
    const svg = svgRef.current;
    if (!svg) return { x: 400, y: 300 };
    const rect = svg.getBoundingClientRect();
    return {
      x: (clientX - rect.left - pan.x) / zoom,
      y: (clientY - rect.top - pan.y) / zoom,
    };
  };

  // Mouse Handlers for zoom, drag & pan
  const handleMouseDown = (e: React.MouseEvent) => {
    const target = e.target as SVGElement;
    const nodeId = target.getAttribute("data-node-id");
    
    if (nodeId) {
      // Node dragging start
      draggedNodeId.current = nodeId;
      onSelectEntity(nodeId);
    } else {
      // Background panning start
      isDraggingBackground.current = true;
      lastMousePos.current = { x: e.clientX, y: e.clientY };
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (draggedNodeId.current) {
      // Update dragged node position
      const coords = getSvgCoordinates(e.clientX, e.clientY);
      const node = nodePositions.current[draggedNodeId.current];
      if (node) {
        node.x = coords.x;
        node.y = coords.y;
        setRenderNodes(Object.values(nodePositions.current).map((n) => ({ ...n })));
      }
    } else if (isDraggingBackground.current) {
      // Update background pan translate
      const dx = e.clientX - lastMousePos.current.x;
      const dy = e.clientY - lastMousePos.current.y;
      setPan((p) => ({ x: p.x + dx, y: p.y + dy }));
      lastMousePos.current = { x: e.clientX, y: e.clientY };
    }
  };

  const handleMouseUp = () => {
    draggedNodeId.current = null;
    isDraggingBackground.current = false;
  };

  const handleWheel = (e: React.WheelEvent<SVGSVGElement>) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.08 : 0.92;
    setZoom((z) => Math.max(0.15, Math.min(4, z * factor)));
  };

  const handleResetLayout = () => {
    setPan({ x: 0, y: 0 });
    setZoom(1);
    setLayoutTrigger((prev) => prev + 1); // Triggers recalculation ticks
  };

  // Map renderNodes list into a lookup dictionary to avoid accessing refs during render
  const nodesMap = renderNodes.reduce((acc, node) => {
    acc[node.id] = node;
    return acc;
  }, {} as { [id: string]: RenderNode });

  return (
    <div className="flex-1 min-h-[420px] bg-zinc-950 border border-zinc-900 rounded-xl relative overflow-hidden group">
      
      {/* Absolute floating control bar */}
      <div className="absolute top-3 left-3 flex gap-1.5 z-10">
        <button
          onClick={() => setZoom((z) => Math.min(4, z * 1.15))}
          className="p-1.5 rounded-lg border border-zinc-800 bg-zinc-900 hover:bg-zinc-850 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer outline-none"
          title="Zoom In"
        >
          <ZoomIn className="h-4 w-4" />
        </button>
        <button
          onClick={() => setZoom((z) => Math.max(0.15, z * 0.85))}
          className="p-1.5 rounded-lg border border-zinc-800 bg-zinc-900 hover:bg-zinc-850 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer outline-none"
          title="Zoom Out"
        >
          <ZoomOut className="h-4 w-4" />
        </button>
        <button
          onClick={handleResetLayout}
          className="p-1.5 rounded-lg border border-zinc-800 bg-zinc-900 hover:bg-zinc-850 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer outline-none"
          title="Center Fit View & Relax Layout"
        >
          <Maximize2 className="h-4 w-4" />
        </button>
        <button
          onClick={() => setLayoutTrigger((p) => p + 1)}
          className="p-1.5 rounded-lg border border-zinc-800 bg-zinc-900 hover:bg-zinc-850 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer outline-none"
          title="Re-run Simulation ticks"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {/* Main SVG workspace */}
      <svg
        ref={svgRef}
        className="w-full h-full cursor-grab active:cursor-grabbing selection:bg-transparent"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
        viewBox="0 0 800 600"
      >
        {/* Render Graph Objects inside transform group */}
        <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
          
          {/* 1. Draw Relationship Lines (Edges) */}
          {relationships.map((rel) => {
            const src = nodesMap[rel.source_entity_id];
            const tgt = nodesMap[rel.target_entity_id];

            if (!src || !tgt) return null;

            const isSelectedEdge = rel.source_entity_id === selectedEntityId || rel.target_entity_id === selectedEntityId;
            const isPathEdge = pathRelIds.has(rel.id);
            const isDimmed = !!(shortestPath || traversalResult) && !isPathEdge && (!traversalNodeIds.has(rel.source_entity_id) || !traversalNodeIds.has(rel.target_entity_id));

            return (
              <g key={rel.id}>
                {/* Arrow markers */}
                <defs>
                  <marker
                    id={`arrow-${rel.id}`}
                    viewBox="0 0 10 10"
                    refX="22" // offset to avoid overlapping node circle border radius (r=18)
                    refY="5"
                    markerWidth="6"
                    markerHeight="6"
                    orient="auto-start-reverse"
                  >
                    <path 
                      d="M 0 1 L 10 5 L 0 9 z" 
                      className={cn(
                        isPathEdge 
                          ? "fill-amber-500" 
                          : isSelectedEdge 
                            ? "fill-zinc-400" 
                            : isDimmed 
                              ? "fill-zinc-900" 
                              : "fill-zinc-800"
                      )} 
                    />
                  </marker>
                </defs>

                {/* The edge line */}
                <line
                  x1={src.x}
                  y1={src.y}
                  x2={tgt.x}
                  y2={tgt.y}
                  strokeWidth={isPathEdge ? 2.5 : isSelectedEdge ? 1.5 : 1}
                  markerEnd={`url(#arrow-${rel.id})`}
                  className={cn(
                    "transition-colors duration-200",
                    isPathEdge 
                      ? "stroke-amber-500 stroke-dasharray-[4,4] animate-pulse" 
                      : isSelectedEdge 
                        ? "stroke-zinc-550" 
                        : isDimmed 
                          ? "stroke-zinc-950" 
                          : "stroke-zinc-850"
                  )}
                />
              </g>
            );
          })}

          {/* 2. Draw Nodes */}
          {renderNodes.map((node) => {
            const isActive = node.id === selectedEntityId;
            const isPathNode = pathNodeIds.has(node.id);
            const isTraversalNode = traversalNodeIds.has(node.id);
            const isDimmed = !!(shortestPath || traversalResult) && !isPathNode && !isTraversalNode;
            
            const Icon = getEntityTypeIcon(node.type);
            const colorClass = getEntityColor(node.type, isActive || isPathNode || isTraversalNode, isDimmed);

            return (
              <g key={node.id} className="transition-transform duration-75">
                
                {/* Node Outer Selection Ring Glow */}
                {(isActive || isPathNode) && (
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r={22}
                    className={cn(
                      "fill-transparent stroke-2 animate-ping",
                      isPathNode ? "stroke-amber-500/40" : "stroke-zinc-400/40"
                    )}
                  />
                )}

                {/* Node Base Circle */}
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={18}
                  data-node-id={node.id}
                  className={cn(
                    "stroke-2 cursor-pointer transition-all duration-300",
                    colorClass,
                    isActive ? "stroke-white scale-110" : isPathNode ? "stroke-amber-500" : ""
                  )}
                />

                {/* Node Type Icon */}
                <g transform={`translate(${node.x - 7}, ${node.y - 7})`} className="pointer-events-none">
                  <Icon className={cn(
                    "h-3.5 w-3.5",
                    isDimmed ? "text-zinc-800" : isPathNode ? "text-amber-400" : "text-zinc-450"
                  )} />
                </g>

                {/* Node Text Label (rendered below) */}
                <text
                  x={node.x}
                  y={node.y + 30}
                  textAnchor="middle"
                  className={cn(
                    "text-[9px] font-mono select-none pointer-events-none transition-opacity duration-200",
                    isActive 
                      ? "fill-zinc-100 font-semibold" 
                      : isPathNode 
                        ? "fill-amber-400 font-semibold" 
                        : isDimmed 
                          ? "fill-zinc-800" 
                          : "fill-zinc-450"
                  )}
                >
                  {node.name}
                </text>

                {/* BFS Depth Badge Indicator if traversal is active */}
                {isTraversalNode && traversalResult && (
                  <g transform={`translate(${node.x + 9}, ${node.y - 18})`} className="pointer-events-none">
                    <circle r={7.5} className="fill-purple-950 stroke border border-purple-800 stroke-purple-700" />
                    <text
                      y={2.5}
                      textAnchor="middle"
                      className="text-[8px] fill-purple-300 font-bold font-mono"
                    >
                      {traversalResult.nodes.find((item) => item.node.id === node.id)?.depth}
                    </text>
                  </g>
                )}
              </g>
            );
          })}

        </g>
      </svg>

      {/* Bottom overlay statistics summary */}
      {renderNodes.length === 0 && (
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-6 bg-zinc-950/90">
          <Share2 className="h-8 w-8 text-zinc-800 mb-2.5 animate-pulse" />
          <span className="text-xs font-semibold text-zinc-550 font-mono">No nodes loaded. Populate graph elements.</span>
        </div>
      )}
    </div>
  );
}
