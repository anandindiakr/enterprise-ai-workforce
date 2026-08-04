"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { getToken, authHeaders } from "@/lib/auth";
import {
  History,
  RefreshCw,
  MessageSquare,
  User,
  Bot,
  Clock,
  X,
  Download,
  Search,
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

interface SessionItem {
  id: string;
  department: string;
  title: string;
  status: string;
  created_at: string;
  updated_at: string;
}

interface MessageItem {
  id: string;
  role: string;
  content: string;
  department: string | null;
  agent_name: string | null;
  created_at: string;
}

interface SessionDetail extends SessionItem {
  summary: string | null;
  messages: MessageItem[];
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

const DEPT_COLORS: Record<string, string> = {
  reception: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  customer_care: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20",
  sales: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  hr: "text-violet-400 bg-violet-500/10 border-violet-500/20",
  finance: "text-rose-400 bg-rose-500/10 border-rose-500/20",
  technology: "text-blue-400 bg-blue-500/10 border-blue-500/20",
  marketing: "text-orange-400 bg-orange-500/10 border-orange-500/20",
};

function DetailDrawer({
  sessionId,
  onClose,
}: {
  sessionId: string;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    fetch(`${API}/api/v1/chat/sessions/${sessionId}`, { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (alive) setDetail(d); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [sessionId]);

  function exportSession(format: "json" | "csv") {
    const token = getToken();
    const url = `${API}/api/v1/chat/sessions/${sessionId}/export?format=${format}`;
    fetch(url, { headers: authHeaders() })
      .then((r) => r.blob())
      .then((blob) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `conversation-${sessionId.slice(0, 8)}.${format}`;
        a.click();
      });
    void token;
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm">
      <div className="flex h-full w-full max-w-lg flex-col border-l border-[#1f2937] bg-[#070d1a]">
        <div className="flex h-14 shrink-0 items-center justify-between border-b border-[#1f2937] px-4">
          <div className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-amber-400" />
            <span className="text-sm font-semibold text-slate-200">
              {detail?.title || "Conversation"}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => exportSession("json")} title="Export JSON"
              className="rounded-lg border border-[#1f2937] p-1.5 text-slate-500 hover:text-amber-400">
              <Download className="h-3.5 w-3.5" />
            </button>
            <button onClick={onClose} className="rounded-lg border border-[#1f2937] p-1.5 text-slate-500 hover:text-red-400">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {detail?.summary && (
          <div className="shrink-0 border-b border-[#1f2937] bg-[#0c111d] px-4 py-3">
            <p className="mb-1 text-[10px] uppercase tracking-widest text-slate-600">Summary</p>
            <p className="text-xs text-slate-400">{detail.summary}</p>
          </div>
        )}

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {loading ? (
            <div className="flex h-40 items-center justify-center">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-[#1f2937] border-t-amber-500" />
            </div>
          ) : !detail || detail.messages.length === 0 ? (
            <div className="flex h-40 items-center justify-center text-sm text-slate-600">
              No messages recorded for this session.
            </div>
          ) : (
            detail.messages.map((m) => (
              <div key={m.id} className={`flex gap-2 ${m.role === "user" ? "" : "flex-row"}`}>
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#111827]">
                  {m.role === "user" ? (
                    <User className="h-3 w-3 text-slate-400" />
                  ) : (
                    <Bot className="h-3 w-3 text-amber-400" />
                  )}
                </div>
                <div className="min-w-0 flex-1 rounded-lg border border-[#1f2937] bg-[#0c111d] p-3">
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <span className="text-[11px] font-medium text-slate-400">
                      {m.role === "user" ? "Caller / User" : m.agent_name || "Agent"}
                    </span>
                    <span className="text-[10px] text-slate-600">{timeAgo(m.created_at)}</span>
                  </div>
                  <p className="whitespace-pre-wrap text-xs text-slate-300">{m.content}</p>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

export default function ConversationsPage() {
  const router = useRouter();
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [deptFilter, setDeptFilter] = useState<string>("all");
  const [openId, setOpenId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const token = getToken();
      if (!token) { router.push("/login"); return; }
      const res = await fetch(`${API}/api/v1/chat/sessions?limit=100`, { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions ?? []);
      }
    } catch { /* swallow */ }
    finally { setLoading(false); }
  }, [router]);

  useEffect(() => {
    if (!getToken()) { router.push("/login"); return; }
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, [load, router]);

  const filtered = sessions.filter((s) => {
    if (deptFilter !== "all" && s.department !== deptFilter) return false;
    if (query && !s.title?.toLowerCase().includes(query.toLowerCase())) return false;
    return true;
  });

  const depts = Array.from(new Set(sessions.map((s) => s.department)));

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[#030712]">
      {openId && <DetailDrawer sessionId={openId} onClose={() => setOpenId(null)} />}

      <div className="flex h-14 shrink-0 items-center justify-between border-b border-[#1f2937] px-6">
        <div className="flex items-center gap-2">
          <History className="h-4 w-4 text-amber-400" />
          <span className="font-mono text-sm font-semibold uppercase tracking-widest text-slate-300">
            Conversation Logs
          </span>
          <span className="ml-1 rounded-full bg-[#111827] px-2 py-0.5 font-mono text-[10px] text-slate-500">
            {sessions.length} sessions
          </span>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-lg border border-[#1f2937] px-3 py-1.5 text-xs text-slate-400 hover:border-amber-500/30 hover:text-amber-400 transition-colors"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> Refresh
        </button>
      </div>

      <div className="flex shrink-0 items-center gap-2 border-b border-[#1f2937] px-4 py-2">
        <div className="relative flex-1 max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-600" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by title…"
            className="w-full rounded-lg border border-[#1f2937] bg-[#111827] py-1.5 pl-8 pr-3 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-amber-500/50"
          />
        </div>
        <select
          value={deptFilter}
          onChange={(e) => setDeptFilter(e.target.value)}
          className="rounded-lg border border-[#1f2937] bg-[#111827] px-2 py-1.5 text-xs text-slate-300 focus:outline-none focus:ring-2 focus:ring-amber-500/50"
        >
          <option value="all">All departments</option>
          {depts.map((d) => (
            <option key={d} value={d}>{d.replace("_", " ")}</option>
          ))}
        </select>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {loading && sessions.length === 0 ? (
          <div className="flex h-40 items-center justify-center">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-[#1f2937] border-t-amber-500" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex h-40 flex-col items-center justify-center gap-1 text-slate-600">
            <History className="h-6 w-6" />
            <p className="text-sm">No conversations recorded yet.</p>
            <p className="text-xs text-slate-700">Every chat and call is logged here automatically once it happens.</p>
          </div>
        ) : filtered.map((s) => {
          const deptCls = DEPT_COLORS[s.department] ?? "text-slate-400 bg-slate-500/10 border-slate-500/20";
          return (
            <button
              key={s.id}
              onClick={() => setOpenId(s.id)}
              className="flex w-full items-center justify-between gap-3 rounded-xl border border-[#1f2937] bg-[#070d1a] p-3 text-left transition-colors hover:border-amber-500/30"
            >
              <div className="flex min-w-0 items-center gap-3">
                <MessageSquare className="h-4 w-4 shrink-0 text-slate-500" />
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-slate-200">{s.title}</p>
                  <div className="mt-0.5 flex items-center gap-2 text-[11px] text-slate-500">
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] ${deptCls}`}>
                      {s.department.replace("_", " ")}
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" /> {timeAgo(s.updated_at)}
                    </span>
                    <span className={`${s.status === "active" ? "text-emerald-400" : "text-slate-600"}`}>
                      {s.status}
                    </span>
                  </div>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
