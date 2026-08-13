"use client";

import { useState } from "react";
import Sidebar from "./Sidebar";
import Header from "./Header";
import MobileNav from "./MobileNav";
import AuthGate from "./AuthGate";

interface AppShellProps {
  children: React.ReactNode;
}

export default function AppShell({ children }: AppShellProps) {
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);

  return (
    <AuthGate>
      <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-row">
        {/* Desktop Sidebar */}
        <Sidebar />

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col md:pl-64 min-h-screen min-w-0">
          {/* Sticky/Sticky-equivalent Header */}
          <Header onMenuOpen={() => setIsMobileNavOpen(true)} />

          {/* Page Content Viewport */}
          <main className="flex-grow flex flex-col min-w-0">
            {children}
          </main>
        </div>

        {/* Mobile Slider Sidebar Drawer */}
        <MobileNav isOpen={isMobileNavOpen} onClose={() => setIsMobileNavOpen(false)} />
      </div>
    </AuthGate>
  );
}
