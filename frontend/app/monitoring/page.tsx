"use client";

import { useEffect, useState, useCallback } from "react";
import { authHeaders } from "@/lib/auth";
import AdminGuard from "@/components/AdminGuard";
import {
  Activity, Server, Database, Cpu, RefreshCw,
  CheckCircle, AlertTriangle, XCircle, Clock, Users, MessageSquare,
  Mic, Zap, Shield, TrendingUp, HardDrive, Wifi, Bell, BellOff,
  Send, Settings2, Trash2, CheckCheck, ChevronDown, ChevronUp,
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

interface AlertRecord {
  id: string;
  level: "info" | "warning" | "critical";
  title: string;
  message: string;
  metric?: string;
  metric_value?: string;
  threshold?: string;
  email_sent: boolean;
  email_to?: string;
  resolved: boolean;
  resolved_at?: string;
  created_at: string;
}

interface AlertThresholds {
  error_rate_warning: number;
  error_rate_critical: number;
  high_escalations: number;
}

const STATUS_CONFIG = {
  healthy:  { cls: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20", icon: CheckCircle,   label: "Healthy" },
  degraded: { cls: "text-amber-400 bg-amber-500/10 border-amber-500/20",       icon: AlertTriangle, label: "Degraded" },
  down:     { cls: "text-red-400 bg-red-500/10 border-red-500/20",             icon: XCircle,       label: "Down" },
  unknown:  { cls: "text-slate-400 bg-slate-500/10 border-slate-500/20",       icon: Clock,         label: "Unknown" },
};

const LEVEL_CONFIG = {
  info:     { cls: "text-blue-400 bg-blue-500/10 border-blue-500/20",         dot: "bg-blue-400"    },
  warning:  { cls: "text-amber-400 bg-amber-500/10 border-amber-500/20",      dot: "bg-amber-400"   },
  critical: { cls: "text-red-400 bg-red-500/10 border-red-500/20",            dot: "bg-red-400 animate-pulse" },
};

const SERVICE_ICONS: Record<string, React.ElementType> = {
  api: Server, database: Database, postgres: Database,
  redis: Zap, chroma: HardDrive, openai: Cpu, frontend: Wifi, celery: Activity,
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

function AlertRow({ alert, onResolve, onDelete }: {
  alert: AlertRecord;
  onResolve: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const cfg = LEVEL_CONFIG[alert.level] ?? LEVEL_CONFIG.info;
  const ts = new Date(alert.created_at).toLocaleString();

  return (
    <div className={`rounded-xl border ${alert.resolved ? "border-[#1a2030] opacity-50" : "border-[#1f2937]"} bg-[#0c111d] p-3`}>
      <div className="flex items-start gap-3">
        <span className={`mt-1.5 h-2 w-2 flex-shrink-0 rounded-full ${cfg.dot}`} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${cfg.cls}`}>
                {alert.level}
              </span>
              <p className="text-xs font-medium text-slate-200 truncate">{alert.title}</p>
            </div>
            <div className="flex items-center gap-1 flex-shrink-0">
              {alert.email_sent
                ? <span title="Email sent" className="text-emerald-400"><Bell className="h-3 w-3" /></span>
                : <span title="Email not sent" className="text-slate-600"><BellOff className="h-3 w-3" /></span>}
              {!alert.resolved && (
                <button onClick={() => onResolve(alert.id)} title="Mark resolved"
                  className="rounded p-1 text-slate-500 hover:text-emerald-400 hover:bg-emerald-500/10 transition-all">
                  <CheckCheck className="h-3 w-3" />
                </button>
              )}
              <button onClick={() => onDelete(alert.id)} title="Delete"
                className="rounded p-1 text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-all">
                <Trash2 className="h-3 w-3" />
              </button>
              <button onClick={() => setExpanded(v => !v)}
                className="rounded p-1 text-slate-500 hover:text-slate-300 transition-all">
                {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              </button>
            </div>
          </div>
          <p className="mt-0.5 text-[11px] text-slate-500">{ts}</p>
          {expanded && (
            <div className="mt-2 rounded-lg border border-[#1f2937] bg-[#060c16] p-3 text-[11px] space-y-1">
              <p className="text-slate-400">{alert.message}</p>
              {alert.metric && (
                <p className="text-slate-500">Metric: <span className="text-slate-400">{alert.metric}</span>
                  {alert.metric_value && <> · Value: <span className="text-amber-400 font-semibold">{alert.metric_value}</span></>}
                  {alert.threshold && <> · Threshold: <span className="text-slate-400">{alert.threshold}</span></>}
                </p>
              )}
              {alert.email_to && (
                <p className="text-slate-500">Notified: <span className="text-slate-400">{alert.email_to}</span></p>
              )}
              {alert.resolved && alert.resolved_at && (
                <p className="text-emerald-400">Resolved: {new Date(alert.resolved_at).toLocaleString()}</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MonitoringContent() {
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [thresholds, setThresholds] = useState<AlertThresholds | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [testEmail, setTestEmail] = useState("");
  const [testSending, setTestSending] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [showConfig, setShowConfig] = useState(false);
  const [editThresholds, setEditThresholds] = useState<Partial<AlertThresholds>>({});
  const [savingThresholds, setSavingThresholds] = useState(false);
  const [alertLevelFilter, setAlertLevelFilter] = useState<string>("all");
  const [showResolved, setShowResolved] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [statsRes, alertsRes, threshRes] = await Promise.allSettled([
        fetch(`${API}/api/v1/system/stats`, { headers: authHeaders() }),
        fetch(`${API}/api/v1/alerts?limit=50`, { headers: authHeaders() }),
        fetch(`${API}/api/v1/alerts/config`, { headers: authHeaders() }),
      ]);
      if (statsRes.status === "fulfilled" && statsRes.value.ok)
        setStats(await statsRes.value.json());
      if (alertsRes.status === "fulfilled" && alertsRes.value.ok) {
        const d = await alertsRes.value.json();
        setAlerts(d.alerts ?? []);
      }
      if (threshRes.status === "fulfilled" && threshRes.value.ok) {
        const d = await threshRes.value.json();
        setThresholds(d.thresholds);
        setEditThresholds(d.thresholds);
      }
      setLastUpdated(new Date());
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);
  useEffect(() => {
    if (!autoRefresh) return;
    const t = setInterval(fetchAll, 30000);
    return () => clearInterval(t);
  }, [autoRefresh, fetchAll]);

  const handleSendTest = async () => {
    if (!testEmail.trim()) return;
    setTestSending(true); setTestResult(null);
    try {
      const r = await fetch(`${API}/api/v1/alerts/test`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ email_to: testEmail }),
      });
      const d = await r.json();
      setTestResult(d.email_sent
        ? `Test alert sent to ${testEmail}`
        : `Queued (no email provider configured) — alert saved in history`);
      fetchAll();
    } catch (e) {
      setTestResult("Error sending test alert");
    }
    setTestSending(false);
  };

  const handleSaveThresholds = async () => {
    setSavingThresholds(true);
    try {
      const r = await fetch(`${API}/api/v1/alerts/config`, {
        method: "PUT",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify(editThresholds),
      });
      if (r.ok) {
        const d = await r.json();
        setThresholds(d.thresholds);
      }
    } catch {}
    setSavingThresholds(false);
  };

  const handleResolve = async (id: string) => {
    await fetch(`${API}/api/v1/alerts/${id}/resolve`, { method: "PATCH", headers: authHeaders() });
    setAlerts(a => a.map(x => x.id === id ? { ...x, resolved: true, resolved_at: new Date().toISOString() } : x));
  };

  const handleDelete = async (id: string) => {
    await fetch(`${API}/api/v1/alerts/${id}`, { method: "DELETE", headers: authHeaders() });
    setAlerts(a => a.filter(x => x.id !== id));
  };

  const filteredAlerts = alerts.filter(a => {
    if (!showResolved && a.resolved) return false;
    if (alertLevelFilter !== "all" && a.level !== alertLevelFilter) return false;
    return true;
  });

  const criticalCount = alerts.filter(a => a.level === "critical" && !a.resolved).length;
  const warningCount  = alerts.filter(a => a.level === "warning"  && !a.resolved).length;
  const overallHealthy = stats?.services.every(s => s.status === "healthy") ?? false;

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
            <p className="text-[11px] text-slate-500">Real-time health · Email alerts · Admin only</p>
          </div>
          {criticalCount > 0 && (
            <span className="flex items-center gap-1 rounded-full border border-red-500/30 bg-red-500/10 px-2 py-0.5 text-[10px] font-semibold text-red-400">
              <span className="h-1.5 w-1.5 rounded-full bg-red-400 animate-pulse" />
              {criticalCount} CRITICAL
            </span>
          )}
          {warningCount > 0 && (
            <span className="flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-400">
              {warningCount} WARNING
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {lastUpdated && <span className="text-[11px] text-slate-600">Updated {lastUpdated.toLocaleTimeString()}</span>}
          <label className="flex items-center gap-2 cursor-pointer">
            <span className="text-[11px] text-slate-500">Auto-refresh</span>
            <button onClick={() => setAutoRefresh(v => !v)}
              className={`relative h-4 w-7 rounded-full transition-colors ${autoRefresh ? "bg-emerald-500/50" : "bg-[#1f2937]"}`}>
              <span className={`absolute top-0.5 h-3 w-3 rounded-full bg-white shadow transition-transform ${autoRefresh ? "translate-x-3.5" : "translate-x-0.5"}`} />
            </button>
          </label>
          <button onClick={fetchAll} disabled={loading}
            className="flex items-center gap-1.5 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-1.5 text-xs text-emerald-400 hover:bg-emerald-500/20 disabled:opacity-50 transition-all">
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> Refresh
          </button>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* Overall status banner */}
        <div className={`flex items-center gap-3 rounded-2xl border p-4 ${overallHealthy ? "border-emerald-500/20 bg-emerald-500/5" : "border-amber-500/20 bg-amber-500/5"}`}>
          {overallHealthy ? <CheckCircle className="h-5 w-5 text-emerald-400 flex-shrink-0" />
            : <AlertTriangle className="h-5 w-5 text-amber-400 flex-shrink-0" />}
          <div>
            <p className={`text-sm font-semibold ${overallHealthy ? "text-emerald-400" : "text-amber-400"}`}>
              {overallHealthy ? "All Systems Operational" : "Some Services Degraded"}
            </p>
            {stats && (
              <p className="text-[11px] text-slate-500">
                Uptime: {stats.uptime_hours.toFixed(1)}h · Error rate: {stats.error_rate_pct.toFixed(2)}% · Avg response: {stats.avg_response_ms}ms
              </p>
            )}
          </div>
        </div>

        {/* Stat cards */}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard icon={MessageSquare} label="Active Chat Sessions" value={stats?.active_chat_sessions ?? "—"} sub="right now" color="violet" />
          <StatCard icon={Mic}          label="Voice Sessions"       value={stats?.active_voice_sessions ?? "—"} sub="right now" color="cyan" />
          <StatCard icon={Users}        label="Active Users Today"   value={stats?.active_users_today ?? "—"} sub={`of ${stats?.total_users ?? "?"} total`} color="blue" />
          <StatCard icon={TrendingUp}   label="Messages Today"       value={stats?.messages_today?.toLocaleString() ?? "—"} color="emerald" />
        </div>

        {/* Services */}
        <div>
          <h2 className="mb-3 text-[11px] font-mono uppercase tracking-wider text-slate-600">Service Health</h2>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
            {(stats?.services ?? [
              { name: "API Server", status: "unknown" }, { name: "PostgreSQL", status: "unknown" },
              { name: "Redis", status: "unknown" }, { name: "ChromaDB", status: "unknown" },
              { name: "OpenAI", status: "unknown" }, { name: "Celery Worker", status: "unknown" },
            ] as ServiceStatus[]).map(svc => {
              const cfg = STATUS_CONFIG[svc.status] ?? STATUS_CONFIG.unknown;
              const StatusIcon = cfg.icon;
              const key = Object.keys(SERVICE_ICONS).find(k => svc.name.toLowerCase().includes(k));
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
                      {svc.latency_ms !== undefined && <span className="text-[10px] text-slate-600">{svc.latency_ms}ms</span>}
                    </div>
                    {svc.details && <p className="text-[10px] text-slate-600 truncate mt-0.5">{svc.details}</p>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* ── ALERTS PANEL ─────────────────────────────────────────────────── */}
        <div className="rounded-2xl border border-[#1f2937] bg-[#0c111d] p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Bell className="h-4 w-4 text-amber-400" />
              <h2 className="text-xs font-semibold text-slate-300">System Alerts</h2>
              {criticalCount > 0 && (
                <span className="rounded-full bg-red-500 px-1.5 py-0.5 text-[10px] font-bold text-white">{criticalCount}</span>
              )}
            </div>
            <button onClick={() => setShowConfig(v => !v)}
              className="flex items-center gap-1.5 rounded-lg border border-[#1f2937] px-2.5 py-1.5 text-[11px] text-slate-400 hover:text-slate-200 hover:border-slate-600 transition-all">
              <Settings2 className="h-3 w-3" /> Configure
            </button>
          </div>

          {/* Alert config panel */}
          {showConfig && (
            <div className="mb-4 rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 space-y-3">
              <p className="text-[11px] font-semibold text-amber-400 uppercase tracking-wider">Alert Thresholds & Email Test</p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] text-slate-500">Error Rate Warning (%)</label>
                  <input type="number" min="0" max="100" step="0.5"
                    value={editThresholds.error_rate_warning ?? ""}
                    onChange={e => setEditThresholds(t => ({ ...t, error_rate_warning: parseFloat(e.target.value) }))}
                    className="mt-1 w-full rounded-lg border border-[#1f2937] bg-[#060c16] px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-amber-500/50" />
                </div>
                <div>
                  <label className="text-[11px] text-slate-500">Error Rate Critical (%)</label>
                  <input type="number" min="0" max="100" step="0.5"
                    value={editThresholds.error_rate_critical ?? ""}
                    onChange={e => setEditThresholds(t => ({ ...t, error_rate_critical: parseFloat(e.target.value) }))}
                    className="mt-1 w-full rounded-lg border border-[#1f2937] bg-[#060c16] px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-amber-500/50" />
                </div>
              </div>
              <button onClick={handleSaveThresholds} disabled={savingThresholds}
                className="rounded-lg bg-amber-500/20 border border-amber-500/30 px-3 py-1.5 text-xs text-amber-400 hover:bg-amber-500/30 disabled:opacity-50 transition-all">
                {savingThresholds ? "Saving..." : "Save Thresholds"}
              </button>

              <div className="border-t border-[#1f2937] pt-3">
                <p className="mb-2 text-[11px] text-slate-500">Send a test alert email to verify your email provider is working:</p>
                <div className="flex gap-2">
                  <input type="email" placeholder="your@email.com" value={testEmail}
                    onChange={e => setTestEmail(e.target.value)}
                    className="flex-1 rounded-lg border border-[#1f2937] bg-[#060c16] px-3 py-1.5 text-xs text-slate-300 placeholder-slate-600 focus:outline-none focus:border-blue-500/50" />
                  <button onClick={handleSendTest} disabled={testSending || !testEmail}
                    className="flex items-center gap-1.5 rounded-lg border border-blue-500/20 bg-blue-500/10 px-3 py-1.5 text-xs text-blue-400 hover:bg-blue-500/20 disabled:opacity-50 transition-all">
                    <Send className="h-3 w-3" />
                    {testSending ? "Sending..." : "Send Test"}
                  </button>
                </div>
                {testResult && (
                  <p className={`mt-2 text-[11px] ${testResult.startsWith("Error") ? "text-red-400" : "text-emerald-400"}`}>
                    {testResult}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Filter bar */}
          <div className="flex items-center gap-2 mb-3">
            {(["all", "critical", "warning", "info"] as const).map(lvl => (
              <button key={lvl} onClick={() => setAlertLevelFilter(lvl)}
                className={`rounded-full px-2.5 py-1 text-[11px] font-medium transition-all ${
                  alertLevelFilter === lvl
                    ? "bg-amber-500/20 border border-amber-500/30 text-amber-400"
                    : "border border-[#1f2937] text-slate-500 hover:text-slate-300"}`}>
                {lvl === "all" ? "All" : lvl.charAt(0).toUpperCase() + lvl.slice(1)}
              </button>
            ))}
            <label className="ml-auto flex items-center gap-1.5 cursor-pointer text-[11px] text-slate-500">
              <input type="checkbox" checked={showResolved} onChange={e => setShowResolved(e.target.checked)}
                className="h-3 w-3 rounded" />
              Show resolved
            </label>
          </div>

          {/* Alert list */}
          <div className="space-y-2 max-h-[480px] overflow-y-auto pr-1">
            {filteredAlerts.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-10 text-slate-600">
                <CheckCircle className="h-8 w-8 mb-2 text-emerald-600" />
                <p className="text-xs">No alerts{alertLevelFilter !== "all" ? ` at ${alertLevelFilter} level` : ""}</p>
                <p className="text-[11px] mt-1">System is healthy. Alerts fire automatically when thresholds are breached.</p>
              </div>
            ) : (
              filteredAlerts.map(a => (
                <AlertRow key={a.id} alert={a} onResolve={handleResolve} onDelete={handleDelete} />
              ))
            )}
          </div>
        </div>

        {/* RBAC matrix */}
        <div className="rounded-2xl border border-[#1f2937] bg-[#0c111d] p-5">
          <div className="flex items-center gap-2 mb-3">
            <Shield className="h-4 w-4 text-amber-400" />
            <h2 className="text-xs font-semibold text-slate-300">Access Control Summary</h2>
          </div>
          <div className="grid grid-cols-2 gap-2 text-[11px]">
            {[
              { page: "Dashboard",         admin: true,  agent: true  },
              { page: "Chat Console",      admin: true,  agent: true  },
              { page: "Voice Console",     admin: true,  agent: true  },
              { page: "Agents",            admin: true,  agent: true  },
              { page: "Workflows",         admin: true,  agent: true  },
              { page: "Analytics",         admin: true,  agent: true  },
              { page: "Knowledge Base",    admin: true,  agent: true  },
              { page: "Integrations",      admin: true,  agent: false },
              { page: "Audit Log",         admin: true,  agent: false },
              { page: "User Management",   admin: true,  agent: false },
              { page: "System Monitoring", admin: true,  agent: false },
              { page: "API Keys",          admin: true,  agent: false },
              { page: "System Alerts",     admin: true,  agent: false },
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
