"use client";

import { useEffect, useState, useCallback } from "react";
import { authHeaders } from "@/lib/auth";
import AdminGuard from "@/components/AdminGuard";
import {
  Activity, Server, Database, Cpu, MemoryStick, RefreshCw,
  CheckCircle, AlertTriangle, XCircle, Clock, Users, MessageSquare,
  Mic, Zap, Shield, TrendingUp, HardDrive, Wifi,
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

interface ServiceStatus {
  name: string;
  status: "healthy" | "degraded" | "down" | "unknown";
  latency_ms?: number;
  details?: string;
}

interface SystemStats {
  services: ServiceStatus[];
  active_chat_sessions: number;
  active_voice_sessions: number;
  total_users: number;
  active_users_today: number;
  messages_today: number;
  api_requests_today: number;
  error_rate_pct: number;
  avg_response_ms: number;
  uptime_hours: number;
}

const STATUS_CONFIG = {
  healthy: { cls: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20", icon: CheckCircle, label: "Healthy" },
  degraded: { cls: "text-amber-400 bg-amber-500/10 border-amber-500/20",     icon: AlertTriangle, label: "Degraded" },
  down:     { cls: "text-red-400 bg-red-500/10 border-red-500/20",           icon: XCircle, label: "Down" },
  unknown:  { cls: "text-slate-400 bg-slate-500/10 border-slate-500/20",     icon: Clock, label: "Unknown" },
};

const SERVICE_ICONS: Record<string, React.ElementType> = {
  api:        Server,
  database:   Database,
  redis:      Zap,
  chroma:     HardDrive,
  openai:     Cpu,
  frontend:   Wifi,
};

function StatCard({ icon: Icon, label, value, sub, color = "amber" }: {
  icon: React.ElementType; label: string; value: string | number; sub?: string; color?: string;
}) {
  const c = {
    amber:  "border-amber-500/20 bg-amber-500/10 text-amber-400",
    emerald:"border-emerald-500/20 bg-emerald-500/10 text-emerald-400",
    blue:   "border-blue-500/20 bg-blue-500/10 text-blue-400",
    violet: "border-violet-500/20 bg-violet-500/10 text-violet-400",
    cyan:   "border-cyan-500/20 bg-cyan-500/10 text-cyan-400",
    rose:   "border-rose-500/20 bg-rose-500/10 text-rose-400",
  }[color] ?? "border-amber-500/20 bg-amber-500/10 text-amber-400";

  return (
    <div className="rounded-2xl border border-[#1f2937] bg-[#0c111d] p-4">
      <div className="flex items-center justify-between mb-3">
        <p className="text-[11px] font-mono uppercase tracking-wider text-slate-600">{label}</p>
        <div className={`flex h-7 w-7 items-center justify-center rounded-lg border ${c}`}>
          <Icon className="h-3.5 w-3.5" />
        </div>
      </div>
      <p className="text-2xl font-bold text-slate-200">{value}</p>
      {sub && <p className="mt-0.5 text-[11px] text-slate-600">{sub}</p>}
    </div>
  );
}

function MonitoringContent() {
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [statsRes, healthRes] = await Promise.allSettled([
        fetch(`${API}/api/v1/system/stats`, { headers: authHeaders() }),
        fetch(`${API}/api/v1/health`, { headers: authHeaders() }),
      ]);

      if (statsRes.status === "fulfilled" && statsRes.value.ok) {
        setStats(await statsRes.value.json());
      }
      if (healthRes.status === "fulfilled" && healthRes.value.ok) {
        setHealth(await healthRes.value.json());
      }
      setLastUpdated(new Date());
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(fetchAll, 30000);
    return () => clearInterval(interval);
  }, [autoRefresh, fetchAll]);

  const overallHealthy = stats?.services.every((s) => s.status === "healthy") ?? false;

  return (
    <div className="min-h-screen bg-[#030712] text-slate-300">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#1f2937] px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10 border border-emerald-500/20">
            <Activity className="h-4 w-4 text-emerald-400" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-slate-200">System Monitoring</h1>
            <p className="text-[11px] text-slate-500">Real-time platform health · Admin only</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-[11px] text-slate-600">Updated {lastUpdated.toLocaleTimeString()}</span>
          )}
          <label className="flex items-center gap-2 cursor-pointer">
            <span className="text-[11px] text-slate-500">Auto-refresh</span>
            <button
              onClick={() => setAutoRefresh((v) => !v)}
              className={`relative h-4 w-7 rounded-full transition-colors ${autoRefresh ? "bg-emerald-500/50" : "bg-[#1f2937]"}`}
            >
              <span className={`absolute top-0.5 h-3 w-3 rounded-full bg-white shadow transition-transform ${autoRefresh ? "translate-x-3.5" : "translate-x-0.5"}`} />
            </button>
          </label>
          <button
            onClick={fetchAll}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-1.5 text-xs text-emerald-400 hover:bg-emerald-500/20 disabled:opacity-50 transition-all"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> Refresh
          </button>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* Overall status banner */}
        <div className={`flex items-center gap-3 rounded-2xl border p-4 ${overallHealthy ? "border-emerald-500/20 bg-emerald-500/5" : "border-amber-500/20 bg-amber-500/5"}`}>
          {overallHealthy
            ? <CheckCircle className="h-5 w-5 text-emerald-400 flex-shrink-0" />
            : <AlertTriangle className="h-5 w-5 text-amber-400 flex-shrink-0" />}
          <div>
            <p className={`text-sm font-semibold ${overallHealthy ? "text-emerald-400" : "text-amber-400"}`}>
              {overallHealthy ? "All Systems Operational" : "Some Services Degraded"}
            </p>
            {stats && <p className="text-[11px] text-slate-500">Uptime: {stats.uptime_hours.toFixed(1)}h · Error rate: {stats.error_rate_pct.toFixed(2)}% · Avg response: {stats.avg_response_ms}ms</p>}
          </div>
        </div>

        {/* Stat cards */}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard icon={MessageSquare} label="Chat Sessions Today" value={stats?.active_chat_sessions ?? "—"} sub="active right now" color="violet" />
          <StatCard icon={Mic} label="Voice Sessions"  value={stats?.active_voice_sessions ?? "—"} sub="active right now" color="cyan" />
          <StatCard icon={Users} label="Active Users Today" value={stats?.active_users_today ?? "—"} sub={`of ${stats?.total_users ?? "?"} total`} color="blue" />
          <StatCard icon={TrendingUp} label="Messages Today" value={stats?.messages_today?.toLocaleString() ?? "—"} color="emerald" />
        </div>

        {/* Services grid */}
        <div>
          <h2 className="mb-3 text-[11px] font-mono uppercase tracking-wider text-slate-600">Service Health</h2>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
            {(stats?.services ?? [
              { name: "API Server",   status: "unknown" },
              { name: "PostgreSQL",   status: "unknown" },
              { name: "Redis",        status: "unknown" },
              { name: "ChromaDB",     status: "unknown" },
              { name: "OpenAI",       status: "unknown" },
              { name: "Celery Worker",status: "unknown" },
            ] as ServiceStatus[]).map((svc) => {
              const cfg = STATUS_CONFIG[svc.status] ?? STATUS_CONFIG.unknown;
              const StatusIcon = cfg.icon;
              const key = Object.keys(SERVICE_ICONS).find((k) => svc.name.toLowerCase().includes(k));
              const SvcIcon = key ? SERVICE_ICONS[key] : Server;
              return (
                <div key={svc.name} className="flex items-center gap-3 rounded-xl border border-[#1f2937] bg-[#0c111d] px-4 py-3">
                  <div className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg border ${cfg.cls}`}>
                    <SvcIcon className="h-3.5 w-3.5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-slate-300 truncate">{svc.name}</p>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <StatusIcon className={`h-3 w-3 ${cfg.cls.split(" ")[0]}`} />
                      <span className={`text-[11px] ${cfg.cls.split(" ")[0]}`}>{cfg.label}</span>
                      {svc.latency_ms !== undefined && (
                        <span className="text-[10px] text-slate-600">{svc.latency_ms}ms</span>
                      )}
                    </div>
                    {svc.details && <p className="text-[10px] text-slate-600 truncate mt-0.5">{svc.details}</p>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* API Health raw JSON */}
        {health && (
          <div>
            <h2 className="mb-3 text-[11px] font-mono uppercase tracking-wider text-slate-600">Raw Health Check</h2>
            <pre className="rounded-2xl border border-[#1f2937] bg-[#0c111d] p-4 text-[11px] text-slate-400 overflow-x-auto">
              {JSON.stringify(health, null, 2)}
            </pre>
          </div>
        )}

        {/* RBAC test section - visible only to admins */}
        <div className="rounded-2xl border border-[#1f2937] bg-[#0c111d] p-5">
          <div className="flex items-center gap-2 mb-3">
            <Shield className="h-4 w-4 text-amber-400" />
            <h2 className="text-xs font-semibold text-slate-300">Access Control Summary</h2>
          </div>
          <div className="grid grid-cols-2 gap-3 text-[11px]">
            {[
              { page: "Dashboard",        admin: true,  agent: true  },
              { page: "Chat Console",     admin: true,  agent: true  },
              { page: "Voice Console",    admin: true,  agent: true  },
              { page: "Agents",           admin: true,  agent: true  },
              { page: "Workflows",        admin: true,  agent: true  },
              { page: "Analytics",        admin: true,  agent: true  },
              { page: "Knowledge Base",   admin: true,  agent: true  },
              { page: "Integrations",     admin: true,  agent: false },
              { page: "Audit Log",        admin: true,  agent: false },
              { page: "User Management",  admin: true,  agent: false },
              { page: "System Monitoring",admin: true,  agent: false },
              { page: "API Keys",         admin: true,  agent: false },
              { page: "System Settings",  admin: true,  agent: false },
            ].map(({ page, admin, agent }) => (
              <div key={page} className="flex items-center justify-between rounded-lg border border-[#1f2937] px-3 py-2">
                <span className="text-slate-400">{page}</span>
                <div className="flex items-center gap-2">
                  <span className={`flex items-center gap-1 rounded-full px-2 py-0.5 ${admin ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"}`}>
                    {admin ? <CheckCircle className="h-2.5 w-2.5" /> : <XCircle className="h-2.5 w-2.5" />} Admin
                  </span>
                  <span className={`flex items-center gap-1 rounded-full px-2 py-0.5 ${agent ? "bg-emerald-500/10 text-emerald-400" : "bg-slate-500/10 text-slate-500"}`}>
                    {agent ? <CheckCircle className="h-2.5 w-2.5" /> : <XCircle className="h-2.5 w-2.5" />} Agent
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function MonitoringPage() {
  return <AdminGuard><MonitoringContent /></AdminGuard>;
}
