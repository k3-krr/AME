"use client";

import { useEffect, useState } from "react";
import { authApi } from "@/lib/api/auth";
import { useAuthStore } from "@/store/authStore";
import { Cpu, Terminal, AlertTriangle } from "lucide-react";
import { ApiError } from "@/lib/api/client";

interface AuthGateProps {
  children: React.ReactNode;
}

export default function AuthGate({ children }: AuthGateProps) {
  const { isAuthenticated, isLoading, setContext, logout } = useAuthStore();
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // 1. Session verification on application initialization/refresh
  useEffect(() => {
    let active = true;
    async function verifySession() {
      try {
        const context = await authApi.getMeContext();
        if (active) {
          setContext(context);
        }
      } catch {
        if (active) {
          logout(); // Reset store state to unauthenticated
        }
      }
    }
    verifySession();
    return () => {
      active = false;
    };
  }, [setContext, logout]);

  // 2. Register generic API client session-expiry callback
  useEffect(() => {
    import("@/lib/api/client").then(({ setUnauthorizedHandler }) => {
      setUnauthorizedHandler(() => {
        logout();
      });
    });
    return () => {
      import("@/lib/api/client").then(({ setUnauthorizedHandler }) => {
        setUnauthorizedHandler(() => {});
      });
    };
  }, [logout]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password.trim()) {
      setErrorMsg("Please fill in all credentials.");
      return;
    }
    if (password.length < 8) {
      setErrorMsg("Password must be at least 8 characters.");
      return;
    }

    setErrorMsg(null);
    setSubmitting(true);

    try {
      if (isRegister) {
        // Register returns User Response
        const user = await authApi.register(email, password);
        // Registration automatically logs the user in (sets cookie)
        const context = await authApi.getMeContext();
        setContext(context, user.email);
      } else {
        const user = await authApi.login(email, password);
        const context = await authApi.getMeContext();
        setContext(context, user.email);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMsg(err.message);
      } else {
        setErrorMsg("Failed to connect to authentication services.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  // Full-screen loading skeleton for session check
  if (isLoading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center p-6 text-zinc-400">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-zinc-900 border border-zinc-800 text-zinc-100 animate-pulse">
          <Cpu className="h-6 w-6 text-zinc-400" />
        </div>
        <div className="mt-4 text-xs font-mono tracking-widest text-zinc-500 uppercase animate-pulse">
          Verifying Context Session...
        </div>
      </div>
    );
  }

  // Auth gate panel if unauthenticated
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-4">
        <div className="w-full max-w-md bg-zinc-950 border border-zinc-800/80 rounded-xl p-6 md:p-8 shadow-xl flex flex-col">
          {/* Logo Branding */}
          <div className="flex items-center gap-3 px-2 mb-6">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-100">
              <Cpu className="h-5 w-5 text-zinc-300" />
            </div>
            <div>
              <h1 className="font-semibold text-sm text-zinc-100 tracking-tight leading-none">AME</h1>
              <p className="text-[10px] text-zinc-500 font-mono tracking-wider mt-0.5 uppercase">Adaptive Memory</p>
            </div>
          </div>

          <div className="mb-6">
            <h2 className="text-lg font-semibold text-zinc-200 tracking-tight">
              {isRegister ? "Provision Account" : "Access Workspace"}
            </h2>
            <p className="text-xs text-zinc-500 mt-1 leading-relaxed">
              {isRegister 
                ? "Create a credentials profile to access your cognitive workspaces."
                : "Authenticate to load your private long-term memory engine."}
            </p>
          </div>

          {/* Validation Feedback */}
          {errorMsg && (
            <div className="mb-4 flex items-start gap-2.5 p-3 rounded-lg border border-red-900/60 bg-red-950/20 text-red-400 text-xs leading-normal font-mono">
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{errorMsg}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="auth-email" className="text-[11px] font-mono text-zinc-400 uppercase tracking-wider">Email Address</label>
              <input
                id="auth-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="developer@ame.ai"
                className="w-full rounded-lg border border-zinc-800 bg-zinc-900/40 px-3.5 py-2 text-sm text-zinc-200 placeholder-zinc-600 outline-none focus:border-zinc-700 transition-colors"
                disabled={submitting}
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="auth-password" className="text-[11px] font-mono text-zinc-400 uppercase tracking-wider">Password</label>
              <input
                id="auth-password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full rounded-lg border border-zinc-800 bg-zinc-900/40 px-3.5 py-2 text-sm text-zinc-200 placeholder-zinc-600 outline-none focus:border-zinc-700 transition-colors"
                disabled={submitting}
              />
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="mt-2 w-full flex items-center justify-center h-10 rounded-lg bg-zinc-100 hover:bg-zinc-200 text-zinc-950 font-medium text-sm transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? "Processing..." : isRegister ? "Register" : "Sign In"}
            </button>
          </form>

          <div className="mt-6 border-t border-zinc-900 pt-4 flex items-center justify-between text-xs font-mono">
            <button
              type="button"
              onClick={() => {
                setIsRegister(!isRegister);
                setErrorMsg(null);
              }}
              className="text-zinc-400 hover:text-zinc-200 transition-colors outline-none cursor-pointer"
            >
              {isRegister ? "Have an account? Login" : "Need credentials? Sign Up"}
            </button>
            
            <div className="flex items-center gap-1 text-[10px] text-zinc-600">
              <Terminal className="h-3 w-3" />
              <span>TLS / HttpOnly Secure</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Render application content if authenticated
  return <>{children}</>;
}
