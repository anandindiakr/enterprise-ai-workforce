"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { getToken } from "@/lib/auth";
import {
  BarChart3,
  TrendingUp,
  Users,
  MessageSquare,
  Mic,
  AlertTriangle,
  CheckCircle,
  Clock,
  Download,
  RefreshCw,
  Activity,
  DollarSign,
  Cpu,
  Globe,
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

// ── Types ─────────────────────────────────────────────────────────────────────

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

// ── Helpers ───────────────────────────────────────────────────────────────────

async function mcpCall(endpoint: string, method: string, args = {}) {
  const res = await fetch(`${API}/mcp/${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/call", params: { name: method, arguments: args } }),
  });
  const data = await res.json();
  if (data.result?.isError) throw new Error(data.result.content[0].text);
  try { return JSON.parse(data.result?.content?.[0]?.text?.replace(/'/g, '"') ?? "{}"); }
  catch { return eval("(" + (data.result?.content?.[0]?.text ?? "{}") + ")"); }
}

function fmt(n: number) {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n}`;
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

// ── Bar segment ───────────────────────────────────────────────────────────────

function BarRow({ label, value, max, color = "bg-amber-500" }: {
  label: string; value: number; max: number; color?: string;
}) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-3">
      <span className="w-28 shrink-0 text-xs text-slate-400 truncate">{label}</span>
      <div className="h-2 flex-1 rounded-full bg-[#1f2937]">
        <div className={`h-2 rounded-full ${color} transition-all duration-700`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-16 shrink-0 text-right font-mono text-xs text-slate-400">{fmt(value)}</span>
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function AnalyticsPage() {
  const router = useRouter();
  const [pipeline,  setPipeline]  = useState<PipelineSummary  | null>(null);
  const [budget,    setBudget]    = useState<BudgetSummary     | null>(null);
  const [health,    setHealth]    = useState<SystemHealth      | null>(null);
  const [hr,        setHr]        = useState<HRSummary         | null>(null);
  const [loading,   setLoading]   = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [p, b, sys, h] = await Promise.all([
        mcpCall("crm",     "crm_pipeline_summary",   {}),
        mcpCall("finance", "finance_budget_summary",  {}),
        mcpCall("devops",  "devops_system_health",    {}),
        mcpCall("hris",    "hris_headcount_summary",  {}),
      ]);
      setPipeline(p);
      setBudget(b);
      setHealth(sys);
      setHr(h);
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
      ["Total Pipeline Value", pipeline?.total_pipeline_value ?? ""],
      ["Open Deals", pipeline?.open_deals ?? ""],
      ["Budget Allocated", budget?.total_allocated ?? ""],
      ["Budget Spent", budget?.total_spent ?? ""],
      ["Budget Utilisation %", budget?.utilisation_pct ?? ""],
      ["Total Employees", hr?.total_employees ?? ""],
      ["Open Incidents", health?.open_incidents ?? ""],
      ["Open Tickets", health?.open_tickets ?? ""],
      ["System Status", health?.overall_status ?? ""],
    ];
    const csv = rows.map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = `analytics-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const maxPipeline = Math.max(...Object.values(pipeline?.pipeline ?? { x: 1 }));
  const maxBudget   = Math.max(...Object.values(hr?.headcount_by_department ?? { x: 1 }));

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[#030712]">
      {/* Header */}
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-[#1f2937] px-6">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-amber-400" />
          <span className="font-mono text-sm font-semibold uppercase tracking-widest text-slate-300">
            Analytics Dashboard
          </span>
        </div>
        <div className="flex items-center gap-3">
          {lastRefresh && (
            <span className="font-mono text-[10px] text-slate-600">
              Updated {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={exportCSV}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-lg border border-[#1f2937] px-3 py-1.5 text-xs text-slate-400 transition-colors hover:border-emerald-500/30 hover:text-emerald-400"
          >
            <Download className="h-3.5 w-3.5" /> Export CSV
          </button>
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-lg border border-[#1f2937] px-3 py-1.5 text-xs text-slate-400 transition-colors hover:border-amber-500/30 hover:text-amber-400"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> Refresh
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {loading ? (
          <div className="flex h-64 items-center justify-center text-slate-500 text-sm">
            Loading analytics…
          </div>
        ) : (
          <>
            {/* KPI row */}
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <StatCard icon={DollarSign}     label="Pipeline Value"  value={fmt(pipeline?.total_pipeline_value ?? 0)}  sub={`${pipeline?.open_deals ?? 0} open deals`}        color="text-emerald-400" bg="bg-emerald-500/10" />
              <StatCard icon={TrendingUp}     label="Budget Utilised" value={`${budget?.utilisation_pct ?? 0}%`}         sub={`${fmt(budget?.total_spent ?? 0)} of ${fmt(budget?.total_allocated ?? 0)}`} color="text-amber-400"   bg="bg-amber-500/10"  />
              <StatCard icon={Users}          label="Total Employees" value={String(hr?.total_employees ?? 0)}           sub="Active headcount"                                 color="text-violet-400"  bg="bg-violet-500/10" />
              <StatCard icon={Activity}       label="System Status"   value={health?.overall_status ?? "—"}             sub={`${health?.open_incidents ?? 0} open incidents`}  color={health?.overall_status === "Healthy" ? "text-emerald-400" : "text-red-400"} bg={health?.overall_status === "Healthy" ? "bg-emerald-500/10" : "bg-red-500/10"} />
            </div>

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              {/* Sales Pipeline */}
              <div className="rounded-xl border border-[#1f2937] bg-[#070d1a] p-5">
                <h3 className="mb-4 flex items-center gap-2 font-mono text-xs font-semibold uppercase tracking-widest text-slate-400">
                  <DollarSign className="h-3.5 w-3.5 text-emerald-400" /> Sales Pipeline by Stage
                </h3>
                <div className="space-y-3">
                  {Object.entries(pipeline?.pipeline ?? {}).map(([stage, val]) => (
                    <BarRow key={stage} label={stage} value={val} max={maxPipeline} color="bg-emerald-500" />
                  ))}
                </div>
              </div>

              {/* Headcount */}
              <div className="rounded-xl border border-[#1f2937] bg-[#070d1a] p-5">
                <h3 className="mb-4 flex items-center gap-2 font-mono text-xs font-semibold uppercase tracking-widest text-slate-400">
                  <Users className="h-3.5 w-3.5 text-violet-400" /> Headcount by Department
                </h3>
                <div className="space-y-3">
                  {Object.entries(hr?.headcount_by_department ?? {}).map(([dept, count]) => (
                    <BarRow key={dept} label={dept} value={count} max={maxBudget || 1} color="bg-violet-500" />
                  ))}
                </div>
              </div>

              {/* Budget */}
              <div className="rounded-xl border border-[#1f2937] bg-[#070d1a] p-5">
                <h3 className="mb-4 flex items-center gap-2 font-mono text-xs font-semibold uppercase tracking-widest text-slate-400">
                  <TrendingUp className="h-3.5 w-3.5 text-amber-400" /> Budget Overview — {budget?.period}
                </h3>
                <div className="space-y-4">
                  <div>
                    <div className="mb-1 flex justify-between text-xs text-slate-500">
                      <span>Spent</span>
                      <span>{fmt(budget?.total_spent ?? 0)} / {fmt(budget?.total_allocated ?? 0)}</span>
                    </div>
                    <div className="h-3 rounded-full bg-[#1f2937]">
                      <div
                        className="h-3 rounded-full bg-amber-500 transition-all duration-700"
                        style={{ width: `${budget?.utilisation_pct ?? 0}%` }}
                      />
                    </div>
                    <p className="mt-1 text-xs text-slate-500">
                      {fmt(budget?.total_remaining ?? 0)} remaining
                    </p>
                  </div>
                </div>
              </div>

              {/* DevOps */}
              <div className="rounded-xl border border-[#1f2937] bg-[#070d1a] p-5">
                <h3 className="mb-4 flex items-center gap-2 font-mono text-xs font-semibold uppercase tracking-widest text-slate-400">
                  <Cpu className="h-3.5 w-3.5 text-blue-400" /> DevOps Health
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  {[
                    { label: "Deployments",   value: health?.total_deployments,    icon: Globe,          color: "text-blue-400"  },
                    { label: "Healthy",        value: health?.healthy_deployments,  icon: CheckCircle,    color: "text-emerald-400"},
                    { label: "Warnings",       value: health?.warning_deployments,  icon: AlertTriangle,  color: "text-yellow-400"},
                    { label: "Open Tickets",   value: health?.open_tickets,         icon: Clock,          color: "text-slate-400" },
                  ].map(({ label, value, icon: Icon, color }) => (
                    <div key={label} className="rounded-lg bg-[#111827] p-3">
                      <div className="flex items-center gap-2">
                        <Icon className={`h-4 w-4 ${color}`} />
                        <span className="text-xs text-slate-500">{label}</span>
                      </div>
                      <p className="mt-1 text-xl font-bold text-slate-100">{value ?? "—"}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
