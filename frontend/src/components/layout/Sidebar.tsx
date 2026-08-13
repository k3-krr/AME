"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  MessageSquare, 
  Brain, 
  Network, 
  Bot, 
  Search, 
  Settings, 
  Cpu,
  LogOut
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/authStore";
import { authApi } from "@/lib/api/auth";

interface NavigationItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
}

const PRIMARY_NAV: NavigationItem[] = [
  { name: "Chat", href: "/", icon: MessageSquare },
  { name: "Memories", href: "/memories", icon: Brain },
  { name: "Knowledge Graph", href: "/knowledge-graph", icon: Network },
  { name: "Agents", href: "/agents", icon: Bot },
  { name: "Retrieval", href: "/retrieval", icon: Search },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { email, logout } = useAuthStore();

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } catch {
      // Clean client state even if backend fails
    } finally {
      logout();
    }
  };

  return (
    <aside className="hidden md:flex md:w-64 md:flex-col md:fixed md:inset-y-0 bg-zinc-950 border-r border-zinc-800/80 px-4 py-5 justify-between">
      {/* Top Branding Section */}
      <div className="flex flex-col gap-8">
        <div className="flex items-center gap-3 px-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-100">
            <Cpu className="h-5 w-5 text-zinc-300" />
          </div>
          <div>
            <h1 className="font-semibold text-sm text-zinc-100 tracking-tight leading-tight">AME</h1>
            <p className="text-[10px] text-zinc-500 font-mono tracking-wider mt-0.5 uppercase">Adaptive Memory</p>
          </div>
        </div>

        {/* Primary Navigation */}
        <nav className="flex flex-col gap-1.5" aria-label="Primary Navigation">
          {PRIMARY_NAV.map((item) => {
            const isActive = pathname === item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 outline-none",
                  isActive 
                    ? "bg-zinc-900 text-zinc-50 border border-zinc-800/60 shadow-sm" 
                    : "text-zinc-400 hover:bg-zinc-900/40 hover:text-zinc-200 border border-transparent"
                )}
              >
                <Icon className={cn("h-4.5 w-4.5 transition-colors", isActive ? "text-zinc-200" : "text-zinc-500")} />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Bottom Profile / Utility Area */}
      <div className="flex flex-col gap-4">
        {/* Settings Navigation */}
        <nav aria-label="Secondary Navigation">
          <Link
            href="/settings"
            className={cn(
              "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 outline-none border",
              pathname === "/settings"
                ? "bg-zinc-900 text-zinc-50 border-zinc-800/60 shadow-sm"
                : "text-zinc-400 hover:bg-zinc-900/40 hover:text-zinc-200 border-transparent"
            )}
          >
            <Settings className={cn("h-4.5 w-4.5", pathname === "/settings" ? "text-zinc-200" : "text-zinc-500")} />
            <span>Settings</span>
          </Link>
        </nav>

        {/* User profile item */}
        <div className="flex items-center justify-between border-t border-zinc-805 pt-4 px-1.5 gap-2">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-zinc-900 border border-zinc-800 text-zinc-300 font-medium text-xs uppercase">
              {email ? email[0] : "U"}
            </div>
            <div className="flex flex-col overflow-hidden">
              <span className="text-xs font-semibold text-zinc-300 truncate leading-none">Account</span>
              <span className="text-[9px] text-zinc-500 font-mono truncate mt-1" title={email || "user@ame.ai"}>
                {email || "user@ame.ai"}
              </span>
            </div>
          </div>

          <button
            onClick={handleLogout}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-zinc-500 hover:bg-zinc-900 hover:text-zinc-300 transition-colors cursor-pointer outline-none shrink-0"
            title="Log Out Session"
            aria-label="Logout user session"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
