"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { getToken, authHeaders } from "@/lib/auth";
import {
  BarChart3,
  TrendingUp,
  Users,
  MessageSquare,
  AlertTriangle,
  CheckCircle,
  Clock,
  Download,
  RefreshCw,
  Activity,
  DollarSign,
  Cpu,
  Globe,
  BookOpen,
  Mic,
  Zap,
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

// ── Types ─────────────────────────────────────────────────────────────────────

interface PlatformAnalytics {
  chat: {
    total_sessions: number;
    active_sessions: number;
    sessions_today: number;
    sessions_by_department: Record<string, number>;
    total_messages: number;
    messages_today: number;
    messages_this_week: number;
    total_tokens_used: number;
  };
  escalations: { total: number; open: number; today: number };
  knowledge_base: { total_documents: number };
  audit: { events_today: number };
  voice: { active_sessions: number };
  activity: { daily_messages: { date: string; messages: number }[] };
}

interface PipelineSummary {
  pipeline: Record<string, number>;
  total_pipeline_value: number;
  open_deals: number;
}

interface BudgetSummary {
  total_allocated: number;
  total_spent: number;
  total_remaining: number;
  utilisation_pct: number;
  period: string;
}

interface SystemHealth {
  overall_status: string;
  total_deployments: number;
  healthy_deployments: number;
  warning_deployments: number;
  open_incidents: number;
  open_tickets: number;
}

interface HRSummary {
  headcount_by_department: Record<string, number>;
  total_employees: number;
}

interface AgentStat {
  department: string;
  messages: number;
  sessions: number;
}

interface AgentActivity {
  days: number;
  agents: AgentStat[];
}

// ── Helpers ───────────────────────────────────────────────────────────────────

async function mcpCall(endpoint: string, method: string, args = {}) {
  const res = await fetch(`${API}/api/v1/mcp/${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/call", params: { name: method, arguments: args } }),
  });
  const data = await res.json();
  if (data.result?.isError) throw new Error(data.result.content[0].text);
  try { return JSON.parse(data.result?.content?.[0]?.text?.replace(/'/g, '"') ?? "{}"); }
  catch { return null; }
}

function fmt(n: number) {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n}`;
}

function num(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

// ── Stat card ─────────────────────────────────────────────────────────────────

function StatCard({ icon: Icon, label, value, sub, color = "text-amber-400", bg = "bg-amber-500/10" }: {
  icon: React.ElementType; label: string; value: string; sub?: string; color?: string; bg?: string;
}) {
  return (
    <div className="rounded-xl border border-[#1f2937] bg-[#070d1a] p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs uppercase tracking-widest text-slate-500">{label}</p>
          <p className="mt-1 text-2xl font-bold text-slate-100">{value}</p>
          {sub && <p className="mt-0.5 text-xs text-slate-500">{sub}</p>}
        </div>
        <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${bg}`}>
          <Icon className={`h-4 w-4 ${color}`} />
        </div>
      </div>
    </div>
  );
}

// ── Bar row ───────────────────────────────────────────────────────────────────

function BarRow({ label, value, max, color = "bg-amber-500", isMoney = false }: {
  label: string; value: number; max: number; color?: string; isMoney?: boolean;
}) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-3">
      <span className="w-28 shrink-0 text-xs text-slate-400 truncate capitalize">{label.replace(/_/g, " ")}</span>
      <div className="h-2 flex-1 rounded-full bg-[#1f2937]">
        <div className={`h-2 rounded-full ${color} transition-all duration-700`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-16 shrink-0 text-right font-mono text-xs text-slate-400">
        {isMoney ? fmt(value) : value}
      </span>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AnalyticsPage() {
  const router = useRouter();
  const [platform,    setPlatform]    = useState<PlatformAnalytics | null>(null);
  const [pipeline,    setPipeline]    = useState<PipelineSummary   | null>(null);
  const [budget,      setBudget]      = useState<BudgetSummary     | null>(null);
  const [health,      setHealth]      = useState<SystemHealth      | null>(null);
  const [hr,          setHr]          = useState<HRSummary         | null>(null);
  const [agentStats,  setAgentStats]  = useState<AgentActivity     | null>(null);
  const [loading,     setLoading]     = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const pRes = await fetch(`${API}/api/v1/analytics`, { headers: authHeaders() });
      if (pRes.ok) setPlatform(await pRes.json());

      // Agent activity — always available (no MCP required)
      const aRes = await fetch(`${API}/api/v1/analytics/agents?days=30`, { headers: authHeaders() });
      if (aRes.ok) setAgentStats(await aRes.json());

      await Promise.allSettled([
        mcpCall("crm",     "crm_pipeline_summary",  {}).then((d) => d && setPipeline(d)),
        mcpCall("finance", "finance_budget_summary", {}).then((d) => d && setBudget(d)),
        mcpCall("devops",  "devops_system_health",   {}).then((d) => d && setHealth(d)),
        mcpCall("hris",    "hris_headcount_summary", {}).then((d) => d && setHr(d)),
      ]);
    } catch (e) {
      console.error("Analytics load error", e);
    } finally {
      setLoading(false);
      setLastRefresh(new Date());
    }
  }, []);

  useEffect(() => {
    if (!getToken()) { router.push("/login"); return; }
    load();
  }, [load, router]);

  function exportCSV() {
    const rows = [
      ["Metric", "Value"],
      ["Total Chat Sessions",   platform?.chat?.total_sessions        ?? ""],
      ["Active Sessions",       platform?.chat?.active_sessions       ?? ""],
      ["Total Messages",        platform?.chat?.total_messages        ?? ""],
      ["Messages Today",        platform?.chat?.messages_today        ?? ""],
      ["Total Tokens Used",     platform?.chat?.total_tokens_used     ?? ""],
      ["Open Escalations",      platform?.escalations?.open           ?? ""],
      ["Knowledge Documents",   platform?.knowledge_base?.total_documents ?? ""],
      ["Active Voice Sessions", platform?.voice?.active_sessions      ?? ""],
      ["Pipeline Value",        pipeline?.total_pipeline_value       ?? ""],
      ["Open Deals",            pipeline?.open_deals                 ?? ""],
      ["Budget Utilisation %",  budget?.utilisation_pct              ?? ""],
      ["Total Employees",       hr?.total_employees                  ?? ""],
      ["System Status",         health?.overall_status               ?? ""],
    ];
    const csv  = rows.map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url; a.download = `analytics-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click(); URL.revokeObjectURL(url);
  }

  const maxPipeline = Math.max(...Object.values(pipeline?.pipeline                         ?? { x: 1 }));
  const maxDept     = Math.max(...Object.values(platform?.chat?.sessions_by_department      ?? { x: 1 }));
  const maxHC       = Math.max(...Object.values(hr?.headcount_by_department                ?? { x: 1 }));
  const maxDaily    = Math.max(...(platform?.activity?.daily_messages?.map((d) => d.messages) ?? [1]));

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[#030712]">
      {/* Header */}
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-[#1f2937] px-6">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-amber-400" />
          <span className="font-mono text-sm font-semibold uppercase tracking-widest text-slate-300">Analytics Dashboard</span>
        </div>
        <div className="flex items-center gap-3">
          {lastRefresh && (
            <span className="font-mono text-[10px] text-slate-600">Updated {lastRefresh.toLocaleTimeString()}</span>
          )}
          <button onClick={exportCSV} disabled={loading}
            className="flex items-center gap-1.5 rounded-lg border border-[#1f2937] px-3 py-1.5 text-xs text-slate-400 hover:border-emerald-500/30 hover:text-emerald-400 transition-colors">
            <Download className="h-3.5 w-3.5" /> Export CSV
          </button>
          <button onClick={load} disabled={loading}
            className="flex items-center gap-1.5 rounded-lg border border-[#1f2937] px-3 py-1.5 text-xs text-slate-400 hover:border-amber-500/30 hover:text-amber-400 transition-colors">
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> Refresh
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {loading ? (
          <div className="flex h-64 items-center justify-center text-slate-500 text-sm">Loading analytics…</div>
        ) : (
          <>
            {/* ── Platform Activity (live DB data) ── */}
            <div>
              <h2 className="mb-3 font-mono text-[10px] uppercase tracking-widest text-slate-600">Platform Activity</h2>
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                <StatCard icon={MessageSquare} label="Total Messages"  value={num(platform?.chat?.total_messages ?? 0)}          sub={`${platform?.chat?.messages_today ?? 0} today`}                    color="text-amber-400"   bg="bg-amber-500/10"  />
                <StatCard icon={Activity}      label="Chat Sessions"   value={num(platform?.chat?.total_sessions ?? 0)}          sub={`${platform?.chat?.active_sessions ?? 0} active`}                  color="text-cyan-400"    bg="bg-cyan-500/10"   />
                <StatCard icon={AlertTriangle} label="Escalations"     value={String(platform?.escalations?.open ?? 0)}         sub={`${platform?.escalations?.total ?? 0} total`}                      color="text-red-400"     bg="bg-red-500/10"    />
                <StatCard icon={BookOpen}      label="Knowledge Docs"  value={String(platform?.knowledge_base?.total_documents ?? 0)} sub={`${platform?.audit?.events_today ?? 0} audit events today`} color="text-violet-400"  bg="bg-violet-500/10" />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              {/* Sessions by department */}
              <div className="rounded-xl border border-[#1f2937] bg-[#070d1a] p-5">
                <h3 className="mb-4 flex items-center gap-2 font-mono text-xs font-semibold uppercase tracking-widest text-slate-400">
                  <Activity className="h-3.5 w-3.5 text-amber-400" /> Sessions by Department
                </h3>
                {Object.keys(platform?.chat?.sessions_by_department ?? {}).length === 0 ? (
                  <p className="text-xs text-slate-600">No sessions yet — start a chat to see data here.</p>
                ) : (
                  <div className="space-y-3">
                    {Object.entries(platform?.chat?.sessions_by_department ?? {}).map(([dept, cnt]) => (
                      <BarRow key={dept} label={dept} value={cnt} max={maxDept} color="bg-amber-500" />
                    ))}
                  </div>
                )}
              </div>

              {/* Daily messages — last 30 days */}
              <div className="rounded-xl border border-[#1f2937] bg-[#070d1a] p-5">
                <h3 className="mb-4 flex items-center gap-2 font-mono text-xs font-semibold uppercase tracking-widest text-slate-400">
                  <TrendingUp className="h-3.5 w-3.5 text-emerald-400" /> Daily Messages (30 days)
                </h3>
                {(platform?.activity?.daily_messages.length ?? 0) === 0 ? (
                  <p className="text-xs text-slate-600">No message data yet.</p>
                ) : (
                  <div className="space-y-1.5 max-h-64 overflow-y-auto pr-1">
                    {(platform?.activity?.daily_messages ?? []).map((d) => (
                      <BarRow key={d.date} label={d.date.slice(5)} value={d.messages} max={maxDaily} color="bg-emerald-500" />
                    ))}
                  </div>
                )}
              </div>

              {/* Agent Activity — 30-day per-department breakdown */}
              <div className="rounded-xl border border-[#1f2937] bg-[#070d1a] p-5">
                <h3 className="mb-4 flex items-center gap-2 font-mono text-xs font-semibold uppercase tracking-widest text-slate-400">
                  <Users className="h-3.5 w-3.5 text-cyan-400" /> Agent Activity (30 days)
                </h3>
                {(agentStats?.agents?.length ?? 0) === 0 ? (
                  <p className="text-xs text-slate-600">No agent conversations yet — start a chat to see data.</p>
                ) : (
                  <div className="space-y-3">
                    {(agentStats?.agents ?? []).map((a) => {
                      const maxMsgs = Math.max(...(agentStats?.agents ?? []).map(x => x.messages), 1);
                      return (
                        <div key={a.department} className="space-y-1">
                          <div className="flex items-center justify-between text-xs text-slate-400">
                            <span className="capitalize font-medium">{a.department.replace(/_/g, " ")}</span>
                            <span className="text-slate-500">{a.sessions} session{a.sessions !== 1 ? "s" : ""} · {a.messages} msg{a.messages !== 1 ? "s" : ""}</span>
                          </div>
                          <div className="h-1.5 rounded-full bg-[#1f2937]">
                            <div className="h-1.5 rounded-full bg-cyan-500 transition-all duration-700"
                                 style={{ width: `${Math.max(4, Math.round((a.messages / maxMsgs) * 100))}%` }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Usage summary */}
              <div className="rounded-xl border border-[#1f2937] bg-[#070d1a] p-5">
                <h3 className="mb-4 flex items-center gap-2 font-mono text-xs font-semibold uppercase tracking-widest text-slate-400">
                  <Zap className="h-3.5 w-3.5 text-amber-400" /> Usage Summary
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  {([
                    { label: "Total Tokens",   value: num(platform?.chat?.total_tokens_used ?? 0),    icon: Zap,           color: "text-amber-400"   },
                    { label: "Msgs This Week", value: num(platform?.chat?.messages_this_week ?? 0),   icon: MessageSquare, color: "text-cyan-400"    },
                    { label: "Voice Sessions", value: String(platform?.voice?.active_sessions ?? 0),  icon: Mic,           color: "text-violet-400"  },
                    { label: "Audit Events",   value: String(platform?.audit?.events_today ?? 0),     icon: Clock,         color: "text-slate-400"   },
                  ] as const).map(({ label, value, icon: Icon, color }) => (
                    <div key={label} className="rounded-lg bg-[#111827] p-3">
                      <div className="flex items-center gap-2">
                        <Icon className={`h-4 w-4 ${color}`} />
                        <span className="text-xs text-slate-500">{label}</span>
                      </div>
                      <p className="mt-1 text-xl font-bold text-slate-100">{value}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Escalation breakdown */}
              <div className="rounded-xl border border-[#1f2937] bg-[#070d1a] p-5">
                <h3 className="mb-4 flex items-center gap-2 font-mono text-xs font-semibold uppercase tracking-widest text-slate-400">
                  <AlertTriangle className="h-3.5 w-3.5 text-red-400" /> Escalation Summary
                </h3>
                <div className="grid grid-cols-3 gap-4">
                  {[
                    { label: "Total", value: platform?.escalations?.total ?? 0, color: "text-slate-300" },
                    { label: "Open",  value: platform?.escalations?.open  ?? 0, color: "text-red-400"   },
                    { label: "Today", value: platform?.escalations?.today ?? 0, color: "text-amber-400" },
                  ].map(({ label, value, color }) => (
                    <div key={label} className="rounded-lg bg-[#111827] p-3 text-center">
                      <p className="text-xs text-slate-500 mb-1">{label}</p>
                      <p className={`text-2xl font-bold ${color}`}>{value}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* ── Business Intelligence (MCP — best-effort) ── */}
            {(pipeline || budget || health || hr) && (
              <>
                <div>
                  <h2 className="mb-3 font-mono text-[10px] uppercase tracking-widest text-slate-600">
                    Business Intelligence (via MCP)
                  </h2>
                  <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                    {pipeline && <StatCard icon={DollarSign} label="Pipeline Value"  value={fmt(pipeline.total_pipeline_value)} sub={`${pipeline.open_deals} open deals`}       color="text-emerald-400" bg="bg-emerald-500/10" />}
                    {budget   && <StatCard icon={TrendingUp} label="Budget Utilised" value={`${budget.utilisation_pct}%`}        sub={`${fmt(budget.total_spent)} / ${fmt(budget.total_allocated)}`} color="text-amber-400" bg="bg-amber-500/10" />}
                    {hr       && <StatCard icon={Users}      label="Total Employees" value={String(hr.total_employees)}          sub="Active headcount"                         color="text-violet-400"  bg="bg-violet-500/10" />}
                    {health   && <StatCard icon={Activity}   label="System Status"   value={health.overall_status ?? "-"}       sub={`${health.open_incidents ?? 0} incidents`} color={health.overall_status === "Healthy" ? "text-emerald-400" : "text-red-400"} bg={health.overall_status === "Healthy" ? "bg-emerald-500/10" : "bg-red-500/10"} />}
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                  {pipeline && pipeline.pipeline && typeof pipeline.pipeline === "object" && (
                    <div className="rounded-xl border border-[#1f2937] bg-[#070d1a] p-5">
                      <h3 className="mb-4 flex items-center gap-2 font-mono text-xs font-semibold uppercase tracking-widest text-slate-400">
                        <DollarSign className="h-3.5 w-3.5 text-emerald-400" /> Sales Pipeline by Stage
                      </h3>
                      <div className="space-y-3">
                        {Object.entries(pipeline.pipeline).map(([stage, val]) => (
                          <BarRow key={stage} label={stage} value={val} max={maxPipeline} color="bg-emerald-500" isMoney />
                        ))}
                      </div>
                    </div>
                  )}

                  {hr && hr.headcount_by_department && typeof hr.headcount_by_department === "object" && (
                    <div className="rounded-xl border border-[#1f2937] bg-[#070d1a] p-5">
                      <h3 className="mb-4 flex items-center gap-2 font-mono text-xs font-semibold uppercase tracking-widest text-slate-400">
                        <Users className="h-3.5 w-3.5 text-violet-400" /> Headcount by Department
                      </h3>
                      <div className="space-y-3">
                        {Object.entries(hr.headcount_by_department).map(([dept, count]) => (
                          <BarRow key={dept} label={dept} value={count} max={maxHC || 1} color="bg-violet-500" />
                        ))}
                      </div>
                    </div>
                  )}

                  {budget && (
                    <div className="rounded-xl border border-[#1f2937] bg-[#070d1a] p-5">
                      <h3 className="mb-4 flex items-center gap-2 font-mono text-xs font-semibold uppercase tracking-widest text-slate-400">
                        <TrendingUp className="h-3.5 w-3.5 text-amber-400" /> Budget Overview — {budget.period}
                      </h3>
                      <div className="mb-1 flex justify-between text-xs text-slate-500">
                        <span>Spent</span>
                        <span>{fmt(budget.total_spent)} / {fmt(budget.total_allocated)}</span>
                      </div>
                      <div className="h-3 rounded-full bg-[#1f2937]">
                        <div className="h-3 rounded-full bg-amber-500 transition-all duration-700" style={{ width: `${budget.utilisation_pct}%` }} />
                      </div>
                      <p className="mt-1 text-xs text-slate-500">{fmt(budget.total_remaining)} remaining</p>
                    </div>
                  )}

                  {health && (
                    <div className="rounded-xl border border-[#1f2937] bg-[#070d1a] p-5">
                      <h3 className="mb-4 flex items-center gap-2 font-mono text-xs font-semibold uppercase tracking-widest text-slate-400">
                        <Cpu className="h-3.5 w-3.5 text-blue-400" /> DevOps Health
                      </h3>
                      <div className="grid grid-cols-2 gap-4">
                        {([
                          { label: "Deployments", value: health.total_deployments,   icon: Globe,         color: "text-blue-400"    },
                          { label: "Healthy",      value: health.healthy_deployments, icon: CheckCircle,   color: "text-emerald-400" },
                          { label: "Warnings",     value: health.warning_deployments, icon: AlertTriangle, color: "text-yellow-400"  },
                          { label: "Open Tickets", value: health.open_tickets,        icon: Clock,         color: "text-slate-400"   },
                        ] as const).map(({ label, value, icon: Icon, color }) => (
                          <div key={label} className="rounded-lg bg-[#111827] p-3">
                            <div className="flex items-center gap-2">
                              <Icon className={`h-4 w-4 ${color}`} />
                              <span className="text-xs text-slate-500">{label}</span>
                            </div>
                            <p className="mt-1 text-xl font-bold text-slate-100">{value ?? "-"}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
