"use client";

import { useEffect, useState, useCallback } from "react";
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
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

// ── Types ─────────────────────────────────────────────────────────────────────

interface VoiceSession {
  session_id: string;
  user_id: string;
  department: string;
  started_at: string;
  last_activity: string;
  escalation: string;
}

interface EscalationItem {
  id: string;
  type: "voice" | "chat";
  user_id: string;
  department: string;
  reason: string;
  severity: "low" | "medium" | "high" | "critical";
  status: "pending" | "assigned" | "resolved";
  created_at: string;
  session_id?: string;
}

// ── Mock escalation data (enriched from voice sessions) ───────────────────────

const MOCK_ESCALATIONS: EscalationItem[] = [
  { id: "esc-001", type: "voice",   user_id: "user_42",  department: "sales",        reason: "Customer demands human negotiator for $500K deal",  severity: "high",     status: "pending",  created_at: "2025-05-15T09:12:00Z" },
  { id: "esc-002", type: "chat",    user_id: "user_17",  department: "customer_care",reason: "Repeated billing dispute unresolved after 3 cycles",  severity: "medium",   status: "assigned", created_at: "2025-05-15T10:05:00Z" },
  { id: "esc-003", type: "voice",   user_id: "user_88",  department: "technology",   reason: "Production outage — requesting senior SRE",          severity: "critical", status: "pending",  created_at: "2025-05-15T11:30:00Z" },
  { id: "esc-004", type: "chat",    user_id: "user_03",  department: "hr",           reason: "Sensitive HR complaint requiring human HR manager",   severity: "high",     status: "resolved", created_at: "2025-05-14T14:22:00Z" },
  { id: "esc-005", type: "voice",   user_id: "user_55",  department: "finance",      reason: "Payroll discrepancy — employee frustrated",           severity: "medium",   status: "pending",  created_at: "2025-05-15T12:00:00Z" },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

const SEVERITY_CONFIG = {
  critical: { label: "Critical", cls: "bg-red-500/15 text-red-400 border-red-500/30"     },
  high:     { label: "High",     cls: "bg-orange-500/15 text-orange-400 border-orange-500/30" },
  medium:   { label: "Medium",   cls: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30" },
  low:      { label: "Low",      cls: "bg-blue-500/15 text-blue-400 border-blue-500/30"   },
};

const STATUS_CONFIG = {
  pending:  { label: "Pending",  icon: Clock,         cls: "text-yellow-400" },
  assigned: { label: "Assigned", icon: User,          cls: "text-blue-400"   },
  resolved: { label: "Resolved", icon: CheckCircle,   cls: "text-emerald-400"},
};

function timeSince(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 60)   return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24)   return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function EscalationsPage() {
  const router = useRouter();
  const [sessions,     setSessions]     = useState<VoiceSession[]>([]);
  const [escalations,  setEscalations]  = useState<EscalationItem[]>(MOCK_ESCALATIONS);
  const [loading,      setLoading]      = useState(true);
  const [filter,       setFilter]       = useState<"all" | "pending" | "assigned" | "resolved">("all");
  const [lastRefresh,  setLastRefresh]  = useState<Date | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const token = getToken();
      if (!token) { router.push("/login"); return; }
      const res = await fetch(`${API}/api/v1/voice/sessions`, { headers: authHeaders() });
      if (res.ok) setSessions(await res.json());
    } catch {
      /* swallow — show mock data */
    } finally {
      setLoading(false);
      setLastRefresh(new Date());
    }
  }, [router]);

  useEffect(() => {
    if (!getToken()) { router.push("/login"); return; }
    load();
    const id = setInterval(load, 20_000);
    return () => clearInterval(id);
  }, [load, router]);

  const filtered = escalations.filter((e) => filter === "all" || e.status === filter);
  const counts   = {
    pending:  escalations.filter((e) => e.status === "pending").length,
    assigned: escalations.filter((e) => e.status === "assigned").length,
    resolved: escalations.filter((e) => e.status === "resolved").length,
  };

  function markStatus(id: string, status: EscalationItem["status"]) {
    setEscalations((prev) => prev.map((e) => e.id === id ? { ...e, status } : e));
  }

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[#030712]">
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
        <div className="flex items-center gap-3">
          {lastRefresh && (
            <span className="font-mono text-[10px] text-slate-600">
              {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={load}
            className="flex items-center gap-1.5 rounded-lg border border-[#1f2937] px-3 py-1.5 text-xs text-slate-400 transition-colors hover:border-amber-500/30 hover:text-amber-400"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> Refresh
          </button>
        </div>
      </div>

      {/* KPI strip */}
      <div className="flex shrink-0 gap-px border-b border-[#1f2937]">
        {[
          { label: "Pending",  count: counts.pending,  color: "text-yellow-400", bg: "bg-yellow-500/5"  },
          { label: "Assigned", count: counts.assigned, color: "text-blue-400",   bg: "bg-blue-500/5"    },
          { label: "Resolved", count: counts.resolved, color: "text-emerald-400",bg: "bg-emerald-500/5" },
          { label: "Active Voice Sessions", count: sessions.length, color: "text-amber-400", bg: "bg-amber-500/5" },
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
        {(["all", "pending", "assigned", "resolved"] as const).map((f) => (
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
        {filtered.length === 0 && (
          <div className="flex h-40 items-center justify-center text-slate-600 text-sm">
            No escalations in this category.
          </div>
        )}

        {filtered.map((esc) => {
          const sev    = SEVERITY_CONFIG[esc.severity];
          const st     = STATUS_CONFIG[esc.status];
          const StIcon = st.icon;

          return (
            <div key={esc.id} className="rounded-xl border border-[#1f2937] bg-[#070d1a] p-4 space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2 min-w-0">
                  {esc.type === "voice"
                    ? <PhoneCall  className="h-4 w-4 shrink-0 text-violet-400" />
                    : <MessageSquare className="h-4 w-4 shrink-0 text-cyan-400" />}
                  <p className="truncate text-sm font-medium text-slate-200">{esc.reason}</p>
                </div>
                <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${sev.cls}`}>
                  {sev.label}
                </span>
              </div>

              <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-500">
                <span className="rounded bg-[#111827] px-2 py-0.5 font-mono">{esc.department.replace("_", " ")}</span>
                <span className="flex items-center gap-1">
                  <User className="h-3 w-3" /> {esc.user_id}
                </span>
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" /> {timeSince(esc.created_at)}
                </span>
                <span className={`flex items-center gap-1 font-medium ${st.cls}`}>
                  <StIcon className="h-3 w-3" /> {st.label}
                </span>
              </div>

              {esc.status !== "resolved" && (
                <div className="flex items-center gap-2 pt-1">
                  {esc.status === "pending" && (
                    <button
                      onClick={() => markStatus(esc.id, "assigned")}
                      className="flex items-center gap-1.5 rounded-lg bg-blue-500/10 px-3 py-1.5 text-xs font-medium text-blue-400 border border-blue-500/20 hover:bg-blue-500/20 transition-colors"
                    >
                      <ChevronRight className="h-3.5 w-3.5" /> Assign to me
                    </button>
                  )}
                  <button
                    onClick={() => markStatus(esc.id, "resolved")}
                    className="flex items-center gap-1.5 rounded-lg bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors"
                  >
                    <CheckCircle className="h-3.5 w-3.5" /> Mark Resolved
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Active voice sessions */}
      {sessions.length > 0 && (
        <div className="shrink-0 border-t border-[#1f2937] p-4">
          <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-slate-600">
            Active Voice Sessions ({sessions.length})
          </p>
          <div className="flex flex-wrap gap-2">
            {sessions.map((s) => (
              <div key={s.session_id} className="flex items-center gap-2 rounded-lg border border-[#1f2937] bg-[#111827] px-3 py-2 text-xs">
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
