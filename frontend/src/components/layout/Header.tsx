"use client";

import { usePathname } from "next/navigation";
import { Menu, User } from "lucide-react";

interface HeaderProps {
  onMenuOpen: () => void;
}

export default function Header({ onMenuOpen }: HeaderProps) {
  const pathname = usePathname();

  // Route-to-title mapping
  const getPageTitle = (path: string) => {
    switch (path) {
      case "/":
        return "Conversational Workspace";
      case "/memories":
        return "Memory Explorer";
      case "/knowledge-graph":
        return "Knowledge Graph Traverser";
      case "/agents":
        return "Autonomous Agents Control";
      case "/retrieval":
        return "Retrieval & Grounding";
      case "/settings":
        return "Workspace Settings";
      default:
        return "Adaptive Memory Engine";
    }
  };

  return (
    <header className="sticky top-0 z-10 flex h-14 w-full items-center justify-between border-b border-zinc-800/80 bg-zinc-950/80 px-4 md:px-6 backdrop-blur-sm">
      {/* Left side: Mobile menu trigger & Context title */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onMenuOpen}
          className="flex h-9 w-9 items-center justify-center rounded-lg border border-zinc-800 text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200 md:hidden transition-colors outline-none focus-visible:ring-1 focus-visible:ring-zinc-700"
          aria-label="Open mobile navigation"
        >
          <Menu className="h-5 w-5" />
        </button>
        
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-zinc-500 hidden sm:inline">workspace /</span>
          <h2 className="text-sm font-semibold text-zinc-100 tracking-tight">
            {getPageTitle(pathname || "/")}
          </h2>
        </div>
      </div>

      {/* Right side: User control placeholder */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-zinc-900/50 border border-zinc-800/60">
          <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-[10px] text-zinc-400 font-mono">Frontend v0.1</span>
        </div>
        
        <div 
          className="flex h-8 w-8 items-center justify-center rounded-full bg-zinc-900 border border-zinc-800 text-zinc-300 cursor-not-allowed hover:bg-zinc-800 transition-colors"
          title="User Account"
        >
          <User className="h-4 w-4" />
        </div>
      </div>
    </header>
  );
}
