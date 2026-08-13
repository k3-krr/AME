import { useState } from "react";
import { AgentCredential } from "@/types";
import { 
  Key, 
  Plus, 
  Trash2, 
  Copy, 
  Check, 
  AlertTriangle, 
  Calendar, 
  Clock, 
  ShieldCheck, 
  Loader2
} from "lucide-react";
import { cn } from "@/lib/utils";

interface AgentCredentialPanelProps {
  credentials: AgentCredential[];
  onIssueCredential: (payload: { description?: string | null; expires_in_days?: number | null }) => Promise<AgentCredential | null>;
  onRevokeCredential: (credentialId: string) => Promise<boolean>;
  agentName: string;
}

export default function AgentCredentialPanel({
  credentials,
  onIssueCredential,
  onRevokeCredential,
  agentName,
}: AgentCredentialPanelProps) {
  const [showIssue, setShowIssue] = useState(false);
  const [description, setDescription] = useState("");
  const [expiresInDays, setExpiresInDays] = useState("30");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // New credential container containing the raw_key
  const [newCred, setNewCred] = useState<AgentCredential | null>(null);
  const [copied, setCopied] = useState(false);
  const [now] = useState(() => Date.now());

  const handleIssueSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      const days = expiresInDays.trim() ? Number(expiresInDays) : null;
      const cred = await onIssueCredential({
        description: description.trim() || null,
        expires_in_days: days,
      });

      if (cred) {
        setNewCred(cred);
        setShowIssue(false);
        setDescription("");
        setExpiresInDays("30");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCopyKey = () => {
    if (!newCred?.raw_key) return;
    navigator.clipboard.writeText(newCred.raw_key);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCloseNewCred = () => {
    // Clear raw secret from memory instantly
    setNewCred(null);
  };

  const handleRevokeClick = (credId: string) => {
    if (confirm("Are you sure you want to permanently revoke this API credential key? It cannot be reactivated.")) {
      onRevokeCredential(credId);
    }
  };

  return (
    <div className="flex flex-col gap-4 font-mono text-xs text-zinc-400">
      
      {/* Header section */}
      <div className="flex items-center justify-between border-b border-zinc-900 pb-2">
        <div className="flex items-center gap-1.5 text-zinc-300 font-semibold">
          <Key className="h-4 w-4 text-zinc-550" />
          <span>API Credentials</span>
        </div>
        <button
          onClick={() => setShowIssue(true)}
          className="flex items-center gap-1 px-2 py-1 rounded bg-zinc-900 border border-zinc-800 hover:bg-zinc-850 text-zinc-400 hover:text-zinc-250 transition-colors cursor-pointer outline-none text-[10px]"
        >
          <Plus className="h-3.5 w-3.5" />
          <span>Issue Key</span>
        </button>
      </div>

      {/* Credentials scroll container */}
      <div className="flex flex-col gap-2 max-h-[300px] overflow-y-auto pr-1">
        {credentials.length > 0 ? (
          credentials.map((cred) => {
            const isRevoked = !!cred.revoked_at;
            const isExpired = cred.expires_at ? new Date(cred.expires_at).getTime() < now : false;
            const isActive = !isRevoked && !isExpired;

            return (
              <div
                key={cred.id}
                className={cn(
                  "p-3 rounded-lg border flex flex-col gap-2 transition-colors",
                  isActive
                    ? "bg-zinc-950/20 border-zinc-900 hover:border-zinc-850"
                    : "bg-zinc-950/45 border-zinc-900/50 opacity-70"
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex flex-col gap-1 truncate">
                    <span className="text-zinc-300 font-medium truncate">
                      {cred.description || "API Access Key"}
                    </span>
                    <span className="text-[9px] text-zinc-600 truncate">
                      ID: {cred.id}
                    </span>
                  </div>
                  
                  {/* Revoke button */}
                  {isActive && (
                    <button
                      onClick={() => handleRevokeClick(cred.id)}
                      className="p-1 rounded bg-red-950/10 hover:bg-red-950/20 border border-red-950/40 hover:border-red-900/50 text-red-400 transition-colors cursor-pointer outline-none shrink-0"
                      title="Revoke API key"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  )}
                </div>

                {/* Expiry & Usage status indicators */}
                <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-[9px] text-zinc-550 border-t border-zinc-900/80 pt-2 mt-0.5">
                  <div className="flex items-center gap-1">
                    <Clock className="h-3 w-3 text-zinc-650" />
                    <span>Created: {new Date(cred.created_at).toLocaleDateString()}</span>
                  </div>
                  
                  <div className="flex items-center gap-1">
                    <Calendar className="h-3 w-3 text-zinc-650" />
                    <span>
                      {cred.expires_at 
                        ? `Expires: ${new Date(cred.expires_at).toLocaleDateString()}` 
                        : "Expires: Never"}
                    </span>
                  </div>

                  <div className="flex items-center gap-1">
                    <ShieldCheck className="h-3 w-3 text-zinc-650" />
                    <span>
                      {cred.last_used_at 
                        ? `Used: ${new Date(cred.last_used_at).toLocaleDateString()}` 
                        : "Used: Never"}
                    </span>
                  </div>

                  <div className="flex items-center gap-1">
                    {isActive ? (
                      <span className="text-emerald-500 font-bold uppercase tracking-widest text-[8px]">Active</span>
                    ) : isRevoked ? (
                      <span className="text-red-500 font-bold uppercase tracking-widest text-[8px]">Revoked</span>
                    ) : (
                      <span className="text-amber-500 font-bold uppercase tracking-widest text-[8px]">Expired</span>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        ) : (
          <span className="text-[10px] text-zinc-650 font-mono italic py-4 text-center">
            No API credentials issued. Generate one to authenticate this agent.
          </span>
        )}
      </div>

      {/* Dialog: Create Key Form */}
      {showIssue && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="fixed inset-0 bg-black/60 backdrop-blur-xs" onClick={() => setShowIssue(false)} />
          <div className="relative w-full max-w-sm bg-zinc-950 border border-zinc-805 rounded-xl p-5 shadow-2xl z-10">
            <h4 className="text-sm font-semibold text-zinc-200 uppercase tracking-wider font-mono border-b border-zinc-900 pb-3 mb-4">
              Issue Key for {agentName}
            </h4>
            <form onSubmit={handleIssueSubmit} className="flex flex-col gap-4">
              
              <div className="flex flex-col gap-1">
                <label htmlFor="cred-desc" className="text-[9px] text-zinc-500 uppercase tracking-widest">Key Description</label>
                <input
                  id="cred-desc"
                  type="text"
                  required
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="e.g. Server Ingest CLI Token"
                  className="w-full rounded border border-zinc-850 bg-zinc-900/30 px-2 py-1.5 text-xs text-zinc-200 outline-none focus:border-zinc-700"
                  disabled={isSubmitting}
                />
              </div>

              <div className="flex flex-col gap-1">
                <label htmlFor="cred-expiry" className="text-[9px] text-zinc-500 uppercase tracking-widest">Expiration (Days)</label>
                <input
                  id="cred-expiry"
                  type="number"
                  min="1"
                  value={expiresInDays}
                  onChange={(e) => setExpiresInDays(e.target.value)}
                  placeholder="Leave empty for unlimited duration"
                  className="w-full rounded border border-zinc-850 bg-zinc-900/30 px-2 py-1.5 text-xs text-zinc-200 outline-none focus:border-zinc-700"
                  disabled={isSubmitting}
                />
              </div>

              <div className="flex justify-end gap-2 border-t border-zinc-900 pt-3 mt-1">
                <button
                  type="button"
                  onClick={() => setShowIssue(false)}
                  disabled={isSubmitting}
                  className="px-2.5 py-1.25 rounded border border-zinc-850 bg-zinc-900/40 hover:bg-zinc-900 text-zinc-400 text-[10px] font-semibold transition-colors cursor-pointer outline-none"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-3.5 py-1.25 rounded bg-zinc-100 hover:bg-zinc-200 text-zinc-950 text-[10px] font-semibold transition-colors cursor-pointer outline-none flex items-center gap-1"
                >
                  {isSubmitting && <Loader2 className="h-3 w-3 animate-spin" />}
                  <span>Generate Key</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Dialog: One-time raw secret visibility box */}
      {newCred && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="fixed inset-0 bg-black/75 backdrop-blur-xs" />
          <div className="relative w-full max-w-sm bg-zinc-950 border border-zinc-800 rounded-xl p-5 shadow-2xl z-10 flex flex-col gap-4">
            
            <div className="flex items-center gap-2 text-amber-500 border-b border-zinc-900 pb-3">
              <AlertTriangle className="h-5 w-5 shrink-0" />
              <h4 className="text-xs font-bold uppercase tracking-wider font-mono">
                Copy API Key Now
              </h4>
            </div>

            <p className="text-[10px] text-zinc-450 leading-relaxed font-sans">
              For security, this secret API key is only shown **once**. If you close this card, you cannot recover it and will have to generate a new key.
            </p>

            {/* Secret key viewport */}
            <div className="flex items-center justify-between gap-2 p-2.5 rounded border border-zinc-850 bg-zinc-900/40 font-mono text-zinc-100 font-semibold select-all text-xs truncate">
              <span className="truncate pr-1">{newCred.raw_key}</span>
              <button
                onClick={handleCopyKey}
                className="p-1 rounded bg-zinc-900 border border-zinc-800 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-all cursor-pointer outline-none shrink-0"
                title="Copy API key"
              >
                {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
              </button>
            </div>

            <button
              onClick={handleCloseNewCred}
              className="w-full py-1.5 rounded bg-zinc-100 hover:bg-zinc-200 text-zinc-950 font-semibold text-center cursor-pointer outline-none text-[10px]"
            >
              Done, I have saved the Key
            </button>
          </div>
        </div>
      )}

    </div>
  );
}
