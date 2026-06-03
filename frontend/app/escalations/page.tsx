"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { getToken, authHeaders } from "@/lib/auth";
import {
  AlertTriangle,
  CheckCircle,
  Clock,
  User,
  RefreshCw,
  PhoneCall,
  MessageSquare,
  ChevronRight,
  Filter,
  Plus,
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

// ── Types ──────────────────────────────────────────────────────────────────────

interface EscalationItem {
  id: string;
  type?: "voice" | "chat";
  user_id: string;
  department: string;
  reason: string;
  priority: "low" | "normal" | "high" | "urgent";
  status: "pending" | "assigned" | "resolved";
  assigned_to?: string | null;
  created_at: string;
  resolved_at?: string | null;
  session_id?: string | null;
}

interface VoiceSession {
  session_id: string;
  user_id: string;
  department: string;
  started_at: string;
  last_activity: string;
  escalation: string;
}

// ── Priority → severity mapping ───────────────────────────────────────────────

const PRIORITY_TO_SEVERITY: Record<string, "critical" | "high" | "medium" | "low"> = {
  urgent:  "critical",
  high:    "high",
  normal:  "medium",
  low:     "low",
};

const SEVERITY_CONFIG = {
  critical: { label: "Critical", cls: "bg-red-500/15 text-red-400 border-red-500/30"         },
  high:     { label: "High",     cls: "bg-orange-500/15 text-orange-400 border-orange-500/30" },
  medium:   { label: "Medium",   cls: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30" },
  low:      { label: "Low",      cls: "bg-blue-500/15 text-blue-400 border-blue-500/30"       },
};

const STATUS_CONFIG = {
  pending:  { label: "Pending",  icon: Clock,       cls: "text-yellow-400" },
  assigned: { label: "Assigned", icon: User,        cls: "text-blue-400"   },
  resolved: { label: "Resolved", icon: CheckCircle, cls: "text-emerald-400"},
};

function timeSince(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 60)  return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24)  return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

// ── Create escalation modal ────────────────────────────────────────────────────

function CreateModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [dept,     setDept]     = useState("reception");
  const [reason,   setReason]   = useState("");
  const [priority, setPriority] = useState("normal");
  const [saving,   setSaving]   = useState(false);
  const [err,      setErr]      = useState("");

  async function submit() {
    if (!reason.trim()) { setErr("Reason is required"); return; }
    setSaving(true); setErr("");
    try {
      const res = await fetch(`${API}/api/v1/escalations`, {
        method:  "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body:    JSON.stringify({ department: dept, reason, priority }),
      });
      if (!res.ok) throw new Error(`API ${res.status}`);
      onCreated();
      onClose();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to create");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-[#1f2937] bg-[#0c111d] p-6 shadow-2xl">
        <h2 className="mb-4 text-base font-semibold text-slate-100">New Escalation</h2>
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs text-slate-400">Department</label>
            <select
              value={dept}
              onChange={(e) => setDept(e.target.value)}
              className="w-full rounded-lg border border-[#1f2937] bg-[#111827] px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500/50"
            >
              {["reception","customer_care","sales","hr","finance","technology","marketing"].map((d) => (
                <option key={d} value={d}>{d.replace("_"," ")}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">Priority</label>
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
              className="w-full rounded-lg border border-[#1f2937] bg-[#111827] px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-amber-500/50"
            >
              {["low","normal","high","urgent"].map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">Reason</label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              placeholder="Describe why this needs human attention…"
              className="w-full rounded-lg border border-[#1f2937] bg-[#111827] px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-amber-500/50 resize-none"
            />
          </div>
          {err && <p className="text-xs text-red-400">{err}</p>}
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-lg border border-[#1f2937] px-4 py-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={saving}
            className="rounded-lg bg-amber-500/20 border border-amber-500/30 px-4 py-1.5 text-xs font-medium text-amber-400 hover:bg-amber-500/30 transition-colors disabled:opacity-50"
          >
            {saving ? "Creating…" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main ───────────────────────────────────────────────────────────────────────

export default function EscalationsPage() {
  const router = useRouter();
  const [escalations, setEscalations] = useState<EscalationItem[]>([]);
  const [sessions,    setSessions]    = useState<VoiceSession[]>([]);
  const [loading,     setLoading]     = useState(true);
  const [filter,      setFilter]      = useState<"all" | "pending" | "assigned" | "resolved">("all");
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [showCreate,  setShowCreate]  = useState(false);
  const [actionId,    setActionId]    = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const token = getToken();
      if (!token) { router.push("/login"); return; }

      const [escRes, sessRes] = await Promise.allSettled([
        fetch(`${API}/api/v1/escalations`, { headers: authHeaders() }),
        fetch(`${API}/api/v1/voice/sessions`, { headers: authHeaders() }),
      ]);

      if (escRes.status === "fulfilled" && escRes.value.ok) {
        const data = await escRes.value.json();
        setEscalations(data.escalations ?? []);
      }
      if (sessRes.status === "fulfilled" && sessRes.value.ok) {
        setSessions(await sessRes.value.json());
      }
    } catch {
      /* swallow */
    } finally {
      setLoading(false);
      setLastRefresh(new Date());
    }
  }, [router]);

  useEffect(() => {
    if (!getToken()) { router.push("/login"); return; }
    load();
    const pollId = setInterval(load, 20_000);

    // Real-time push via /ws/events
    const wsBase = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080")
      .replace(/^http/, "ws");
    const ws = new WebSocket(`${wsBase}/api/v1/ws/events`);
    wsRef.current = ws;
    ws.onopen = () => ws.send(JSON.stringify({ channels: ["escalations"] }));
    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.channel === "escalations" && msg.data?.type === "new_escalation") {
          setEscalations((prev) => {
            if (prev.some((e) => e.id === msg.data.id)) return prev;
            return [msg.data as EscalationItem, ...prev];
          });
        }
      } catch { /* ignore */ }
    };
    ws.onerror = () => { /* silent */ };

    return () => {
      clearInterval(pollId);
      ws.close();
    };
  }, [load, router]);

  async function assign(id: string) {
    setActionId(id);
    try {
      const res = await fetch(`${API}/api/v1/escalations/${id}/assign`, {
        method:  "PATCH",
        headers: authHeaders(),
      });
      if (res.ok) {
        const updated = await res.json();
        setEscalations((prev) => prev.map((e) => e.id === id ? { ...e, ...updated } : e));
      }
    } catch { /* swallow */ }
    finally { setActionId(null); }
  }

  async function resolve(id: string) {
    setActionId(id);
    try {
      const res = await fetch(`${API}/api/v1/escalations/${id}/resolve`, {
        method:  "PATCH",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body:    JSON.stringify({ resolution_notes: "Resolved by operator" }),
      });
      if (res.ok) {
        const updated = await res.json();
        setEscalations((prev) => prev.map((e) => e.id === id ? { ...e, ...updated } : e));
      }
    } catch { /* swallow */ }
    finally { setActionId(null); }
  }

  const filtered = escalations.filter((e) => filter === "all" || e.status === filter);
  const counts   = {
    pending:  escalations.filter((e) => e.status === "pending").length,
    assigned: escalations.filter((e) => e.status === "assigned").length,
    resolved: escalations.filter((e) => e.status === "resolved").length,
  };

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[#030712]">
      {showCreate && (
        <CreateModal onClose={() => setShowCreate(false)} onCreated={load} />
      )}

      {/* Header */}
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-[#1f2937] px-6">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-orange-400" />
          <span className="font-mono text-sm font-semibold uppercase tracking-widest text-slate-300">
            Human Escalations
          </span>
          {counts.pending > 0 && (
            <span className="ml-1 rounded-full bg-red-500/20 px-2 py-0.5 font-mono text-[10px] text-red-400">
              {counts.pending} pending
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {lastRefresh && (
            <span className="font-mono text-[10px] text-slate-600">
              {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-1.5 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs text-amber-400 hover:bg-amber-500/20 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" /> New
          </button>
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-lg border border-[#1f2937] px-3 py-1.5 text-xs text-slate-400 hover:border-amber-500/30 hover:text-amber-400 transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> Refresh
          </button>
        </div>
      </div>

      {/* KPI strip */}
      <div className="flex shrink-0 gap-px border-b border-[#1f2937]">
        {[
          { label: "Pending",              count: counts.pending,  color: "text-yellow-400",  bg: "bg-yellow-500/5"  },
          { label: "Assigned",             count: counts.assigned, color: "text-blue-400",    bg: "bg-blue-500/5"    },
          { label: "Resolved",             count: counts.resolved, color: "text-emerald-400", bg: "bg-emerald-500/5" },
          { label: "Active Voice Sessions",count: sessions.length, color: "text-amber-400",   bg: "bg-amber-500/5"   },
        ].map(({ label, count, color, bg }) => (
          <div key={label} className={`flex flex-1 flex-col items-center justify-center py-3 ${bg}`}>
            <span className={`text-lg font-bold ${color}`}>{count}</span>
            <span className="text-[10px] uppercase tracking-widest text-slate-600">{label}</span>
          </div>
        ))}
      </div>

      {/* Filter tabs */}
      <div className="flex shrink-0 items-center gap-1 border-b border-[#1f2937] px-4 py-2">
        <Filter className="h-3.5 w-3.5 text-slate-600" />
        {(["all","pending","assigned","resolved"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded-md px-3 py-1 text-xs capitalize transition-colors ${
              filter === f
                ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                : "text-slate-500 hover:text-slate-300"
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {/* Escalation list */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {loading && escalations.length === 0 ? (
          <div className="flex h-40 items-center justify-center">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-[#1f2937] border-t-amber-500" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex h-40 items-center justify-center text-slate-600 text-sm">
            No escalations in this category.
          </div>
        ) : filtered.map((esc) => {
          const sev    = SEVERITY_CONFIG[PRIORITY_TO_SEVERITY[esc.priority] ?? "medium"];
          const st     = STATUS_CONFIG[esc.status];
          const StIcon = st.icon;
          const busy   = actionId === esc.id;

          return (
            <div key={esc.id} className="rounded-xl border border-[#1f2937] bg-[#070d1a] p-4 space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2 min-w-0">
                  {esc.type === "voice"
                    ? <PhoneCall     className="h-4 w-4 shrink-0 text-violet-400" />
                    : <MessageSquare className="h-4 w-4 shrink-0 text-cyan-400"   />}
                  <p className="truncate text-sm font-medium text-slate-200">{esc.reason}</p>
                </div>
                <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${sev.cls}`}>
                  {sev.label}
                </span>
              </div>

              <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-500">
                <span className="rounded bg-[#111827] px-2 py-0.5 font-mono">
                  {esc.department.replace("_"," ")}
                </span>
                <span className="flex items-center gap-1">
                  <User  className="h-3 w-3" /> {esc.user_id}
                </span>
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" /> {timeSince(esc.created_at)}
                </span>
                <span className={`flex items-center gap-1 font-medium ${st.cls}`}>
                  <StIcon className="h-3 w-3" /> {st.label}
                </span>
                {esc.assigned_to && (
                  <span className="flex items-center gap-1 text-blue-400">
                    <User className="h-3 w-3" /> {esc.assigned_to}
                  </span>
                )}
              </div>

              {esc.status !== "resolved" && (
                <div className="flex items-center gap-2 pt-1">
                  {esc.status === "pending" && (
                    <button
                      onClick={() => assign(esc.id)}
                      disabled={busy}
                      className="flex items-center gap-1.5 rounded-lg bg-blue-500/10 px-3 py-1.5 text-xs font-medium text-blue-400 border border-blue-500/20 hover:bg-blue-500/20 transition-colors disabled:opacity-50"
                    >
                      <ChevronRight className="h-3.5 w-3.5" />
                      {busy ? "Assigning…" : "Assign to me"}
                    </button>
                  )}
                  <button
                    onClick={() => resolve(esc.id)}
                    disabled={busy}
                    className="flex items-center gap-1.5 rounded-lg bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors disabled:opacity-50"
                  >
                    <CheckCircle className="h-3.5 w-3.5" />
                    {busy ? "Resolving…" : "Mark Resolved"}
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Active voice sessions panel */}
      {sessions.length > 0 && (
        <div className="shrink-0 border-t border-[#1f2937] p-4">
          <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-slate-600">
            Active Voice Sessions ({sessions.length})
          </p>
          <div className="flex flex-wrap gap-2">
            {sessions.map((s) => (
              <div
                key={s.session_id}
                className="flex items-center gap-2 rounded-lg border border-[#1f2937] bg-[#111827] px-3 py-2 text-xs"
              >
                <PhoneCall className="h-3 w-3 text-violet-400" />
                <span className="text-slate-400">{s.department}</span>
                <span className="font-mono text-slate-600">{s.session_id.slice(-8)}</span>
                {s.escalation !== "none" && (
                  <span className="rounded-full bg-orange-500/20 px-1.5 text-orange-400">{s.escalation}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
