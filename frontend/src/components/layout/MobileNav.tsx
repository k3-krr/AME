"use client";

import { useEffect } from "react";
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
  X,
  LogOut
} from "lucide-react";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import { useAuthStore } from "@/store/authStore";
import { authApi } from "@/lib/api/auth";

interface MobileNavProps {
  isOpen: boolean;
  onClose: () => void;
}

const PRIMARY_NAV = [
  { name: "Chat", href: "/", icon: MessageSquare },
  { name: "Memories", href: "/memories", icon: Brain },
  { name: "Knowledge Graph", href: "/knowledge-graph", icon: Network },
  { name: "Agents", href: "/agents", icon: Bot },
  { name: "Retrieval", href: "/retrieval", icon: Search },
];

export default function MobileNav({ isOpen, onClose }: MobileNavProps) {
  const pathname = usePathname();
  const { email, logout } = useAuthStore();

  // Close the mobile drawer automatically when the pathname changes
  useEffect(() => {
    onClose();
  }, [pathname, onClose]);

  // Handle escape keypress to close mobile nav
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } catch {
      // Clean client state even if backend fails
    } finally {
      logout();
      onClose();
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.5 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black"
            aria-hidden="true"
          />

          {/* Sliding drawer panel */}
          <motion.div
            initial={{ x: "-100%" }}
            animate={{ x: 0 }}
            exit={{ x: "-100%" }}
            transition={{ type: "tween", ease: "easeInOut", duration: 0.2 }}
            className="relative flex w-full max-w-xs flex-1 flex-col bg-zinc-950 border-r border-zinc-800/80 px-4 py-5 justify-between shadow-xl"
            role="dialog"
            aria-modal="true"
          >
            {/* Top Close Button & Branding */}
            <div className="flex flex-col gap-8">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3 px-2">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-100">
                    <Cpu className="h-5 w-5 text-zinc-300" />
                  </div>
                  <div>
                    <h1 className="font-semibold text-sm text-zinc-100 tracking-tight leading-none">AME</h1>
                    <p className="text-[10px] text-zinc-500 font-mono tracking-wider mt-0.5 uppercase">Adaptive Memory</p>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={onClose}
                  className="flex h-8 w-8 items-center justify-center rounded-lg border border-zinc-800 text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200 transition-colors outline-none focus-visible:ring-1 focus-visible:ring-zinc-700"
                  aria-label="Close navigation menu"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Primary Navigation */}
              <nav className="flex flex-col gap-1.5" aria-label="Mobile Primary Navigation">
                {PRIMARY_NAV.map((item) => {
                  const isActive = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
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
              <nav aria-label="Mobile Secondary Navigation">
                <Link
                  href="/settings"
                  className={cn(
                    "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 outline-none border",
                    pathname === "/settings"
                      ? "bg-zinc-900 text-zinc-50 border border-zinc-800/60 shadow-sm"
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
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-zinc-900 border border-zinc-805 text-zinc-300 font-medium text-xs uppercase">
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
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
