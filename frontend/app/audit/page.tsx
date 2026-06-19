"use client";

import { useState, useEffect, useCallback } from "react";
import { authHeaders } from "@/lib/auth";
import AdminGuard from "@/components/AdminGuard";
import {
  ClipboardList, RefreshCw, ChevronLeft, ChevronRight,
  Search, Filter, Download, LogIn, LogOut, Plus, Trash2,
  AlertTriangle, Shield, MessageSquare, Mic, BookOpen, Settings,
  User, ExternalLink,
} from "lucide-react";

interface AuditEntry {
  id: string;
  user_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  ip_address: string | null;
  details: Record<string, unknown>;
  created_at: string;
}

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
const PAGE_SIZE = 50;

const ACTION_STYLES: Record<string, { cls: string; icon: React.ElementType }> = {
  login:      { cls: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20", icon: LogIn },
  logout:     { cls: "bg-slate-500/10 text-slate-400 border-slate-500/20",       icon: LogOut },
  create:     { cls: "bg-blue-500/10 text-blue-400 border-blue-500/20",           icon: Plus },
  delete:     { cls: "bg-red-500/10 text-red-400 border-red-500/20",             icon: Trash2 },
  escalation: { cls: "bg-orange-500/10 text-orange-400 border-orange-500/20",    icon: AlertTriangle },
  chat:       { cls: "bg-violet-500/10 text-violet-400 border-violet-500/20",    icon: MessageSquare },
  voice:      { cls: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",          icon: Mic },
  knowledge:  { cls: "bg-amber-500/10 text-amber-400 border-amber-500/20",       icon: BookOpen },
  settings:   { cls: "bg-purple-500/10 text-purple-400 border-purple-500/20",    icon: Settings },
  user:       { cls: "bg-indigo-500/10 text-indigo-400 border-indigo-500/20",    icon: User },
  security:   { cls: "bg-rose-500/10 text-rose-400 border-rose-500/20",          icon: Shield },
};

function getActionStyle(action: string) {
  const key = Object.keys(ACTION_STYLES).find((k) => action.toLowerCase().includes(k));
  return key ? ACTION_STYLES[key] : { cls: "bg-slate-500/10 text-slate-400 border-slate-500/20", icon: ExternalLink };
}

function AuditLogContent() {
  const [logs, setLogs] = useState<AuditEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [page, setPage] = useState(0);
  const [filterAction, setFilterAction] = useState("");
  const [filterUser, setFilterUser] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    setError("");
    const params = new URLSearchParams({
      skip: String(page * PAGE_SIZE),
      limit: String(PAGE_SIZE),
    });
    if (filterAction.trim()) params.set("action", filterAction.trim());
    if (filterUser.trim()) params.set("user_id", filterUser.trim());

    try {
      const res = await fetch(`${API}/api/v1/audit?${params}`, { headers: authHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setLogs(data.logs ?? []);
      setTotal(data.total ?? 0);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load audit logs");
    } finally {
      setLoading(false);
    }
  }, [page, filterAction, filterUser]);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  const exportCSV = () => {
    const header = "Time,Action,User,Resource Type,Resource ID,IP\n";
    const rows = logs.map((l) =>
      [new Date(l.created_at).toISOString(), l.action, l.user_id ?? "", l.resource_type ?? "", l.resource_id ?? "", l.ip_address ?? ""].join(",")
    ).join("\n");
    const blob = new Blob([header + rows], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url;
    a.download = `audit-log-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click(); URL.revokeObjectURL(url);
  };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const inputCls = "rounded-xl border border-[#1f2937] bg-[#0c111d] px-3 py-2 text-xs text-slate-300 placeholder-slate-600 focus:border-amber-500/50 focus:outline-none";

  return (
    <div className="flex h-screen flex-col bg-[#030712] text-slate-300">
      {/* Header */}
      <div className="flex flex-shrink-0 items-center justify-between border-b border-[#1f2937] px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500/10 border border-amber-500/20">
            <ClipboardList className="h-4 w-4 text-amber-400" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-slate-200">Audit Log</h1>
            <p className="text-[11px] text-slate-500">Platform-wide activity trail · Admin only</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-full border border-[#1f2937] bg-[#0c111d] px-3 py-1 text-[11px] text-slate-500">
            {total.toLocaleString()} total events
          </span>
          <button onClick={exportCSV} className="flex items-center gap-1.5 rounded-xl border border-[#1f2937] bg-[#0c111d] px-3 py-1.5 text-xs text-slate-400 hover:border-amber-500/30 hover:text-amber-400 transition-all">
            <Download className="h-3.5 w-3.5" /> Export CSV
          </button>
          <button onClick={fetchLogs} disabled={loading} className="flex items-center gap-1.5 rounded-xl border border-amber-500/20 bg-amber-500/10 px-3 py-1.5 text-xs text-amber-400 hover:bg-amber-500/20 transition-all disabled:opacity-50">
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> Refresh
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-shrink-0 items-center gap-3 border-b border-[#1f2937] bg-[#060d1a] px-6 py-3">
        <Filter className="h-3.5 w-3.5 text-slate-600 flex-shrink-0" />
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3 w-3 text-slate-600" />
          <input value={filterAction} onChange={(e) => { setFilterAction(e.target.value); setPage(0); }} placeholder="Filter by action (chat, login, delete…)" className={`${inputCls} pl-7 w-full`} />
        </div>
        <div className="relative max-w-xs">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3 w-3 text-slate-600" />
          <input value={filterUser} onChange={(e) => { setFilterUser(e.target.value); setPage(0); }} placeholder="Filter by user ID" className={`${inputCls} pl-7`} />
        </div>
        {(filterAction || filterUser) && (
          <button onClick={() => { setFilterAction(""); setFilterUser(""); setPage(0); }} className="text-xs text-slate-600 hover:text-amber-400 transition-colors">
            Clear
          </button>
        )}
      </div>

      {error && (
        <div className="mx-6 mt-3 flex items-center gap-2 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-2.5 text-xs text-red-400">
          <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" /> {error}
        </div>
      )}

      {/* Table */}
      <div className="flex-1 overflow-auto px-6 py-4">
        <div className="rounded-2xl border border-[#1f2937] overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-[#1f2937] bg-[#0c111d]">
                {["Timestamp", "Action", "User", "Resource", "IP Address", "Details"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left font-mono text-[10px] uppercase tracking-wider text-slate-600">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1f2937]">
              {loading ? (
                Array.from({ length: 10 }).map((_, i) => (
                  <tr key={i} className="bg-[#070d1a]">
                    {Array.from({ length: 6 }).map((_, j) => (
                      <td key={j} className="px-4 py-3"><div className="h-3 rounded bg-[#1f2937] animate-pulse" style={{ width: `${40 + j * 10}%` }} /></td>
                    ))}
                  </tr>
                ))
              ) : logs.length === 0 ? (
                <tr><td colSpan={6} className="px-4 py-16 text-center text-slate-600 bg-[#070d1a]">
                  <ClipboardList className="h-8 w-8 mx-auto mb-2 opacity-30" />No audit entries found
                </td></tr>
              ) : (
                logs.flatMap((log) => {
                  const style = getActionStyle(log.action);
                  const Icon = style.icon;
                  const isExpanded = expandedId === log.id;
                  const hasDetails = Object.keys(log.details ?? {}).length > 0;
                  const rows = [
                    <tr key={log.id} className={`bg-[#070d1a] transition-colors ${hasDetails ? "cursor-pointer hover:bg-[#0c111d]" : ""}`} onClick={() => hasDetails && setExpandedId(isExpanded ? null : log.id)}>
                      <td className="px-4 py-3 font-mono text-[11px] text-slate-500 whitespace-nowrap">{new Date(log.created_at).toLocaleString()}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium ${style.cls}`}>
                          <Icon className="h-3 w-3" />{log.action}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-[11px] text-slate-400">{log.user_id ? log.user_id.slice(0, 12) + "…" : <span className="text-slate-700">—</span>}</td>
                      <td className="px-4 py-3 text-[11px] text-slate-500">
                        {log.resource_type ? <span className="font-medium text-slate-400">{log.resource_type}</span> : <span className="text-slate-700">—</span>}
                        {log.resource_id && <span className="ml-1 text-slate-700">/{log.resource_id.slice(0, 8)}…</span>}
                      </td>
                      <td className="px-4 py-3 font-mono text-[11px] text-slate-600">{log.ip_address ?? <span className="text-slate-700">—</span>}</td>
                      <td className="px-4 py-3">{hasDetails ? <span className="text-[11px] text-amber-500/60 hover:text-amber-400">{isExpanded ? "▲ Hide" : "▼ Show"}</span> : <span className="text-slate-700">—</span>}</td>
                    </tr>,
                  ];
                  if (isExpanded && hasDetails) {
                    rows.push(
                      <tr key={`${log.id}-d`} className="bg-[#0c111d]">
                        <td colSpan={6} className="px-8 py-3">
                          <pre className="rounded-lg border border-[#1f2937] bg-[#070d1a] p-3 text-[11px] text-slate-400 overflow-x-auto whitespace-pre-wrap">{JSON.stringify(log.details, null, 2)}</pre>
                        </td>
                      </tr>
                    );
                  }
                  return rows;
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="mt-4 flex items-center justify-between text-xs text-slate-600">
          <span>Showing {Math.min(page * PAGE_SIZE + 1, total)}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total} events</span>
          <div className="flex items-center gap-2">
            <button disabled={page === 0} onClick={() => setPage((p) => p - 1)} className="flex items-center gap-1 rounded-lg border border-[#1f2937] px-3 py-1.5 hover:border-amber-500/30 hover:text-amber-400 disabled:opacity-40 disabled:cursor-not-allowed">
              <ChevronLeft className="h-3.5 w-3.5" /> Prev
            </button>
            <span className="px-2">Page {page + 1} / {totalPages}</span>
            <button disabled={(page + 1) * PAGE_SIZE >= total} onClick={() => setPage((p) => p + 1)} className="flex items-center gap-1 rounded-lg border border-[#1f2937] px-3 py-1.5 hover:border-amber-500/30 hover:text-amber-400 disabled:opacity-40 disabled:cursor-not-allowed">
              Next <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AuditLogPage() {
  return <AdminGuard><AuditLogContent /></AdminGuard>;
}
