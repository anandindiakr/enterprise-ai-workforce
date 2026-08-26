"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Star,
  Headphones,
  ShoppingCart,
  Users,
  DollarSign,
  Cpu,
  Megaphone,
  MessageSquare,
  Mic,
  Activity,
  TrendingUp,
  Clock,
  ArrowUpRight,
  Zap,
} from "lucide-react";

/* ── Data ────────────────────────────────────────────────── */

const AGENTS = [
  {
    id: "reception",
    label: "Receptionist",
    icon: Star,
    colorClass: {
      bg: "bg-amber-500/10",
      text: "text-amber-400",
      border: "border-amber-500/20",
      badge: "bg-amber-500/20 text-amber-300",
    },
    desc: "First contact, routing, visitor management.",
    skills: ["Greet", "Route", "FAQ", "Escalate"],
  },
  {
    id: "customer_care",
    label: "Customer Care",
    icon: Headphones,
    colorClass: {
      bg: "bg-cyan-500/10",
      text: "text-cyan-400",
      border: "border-cyan-500/20",
      badge: "bg-cyan-500/20 text-cyan-300",
    },
    desc: "Support tickets, issue resolution, follow-ups.",
    skills: ["Tickets", "Resolve", "Refunds", "SLA"],
  },
  {
    id: "sales",
    label: "Sales",
    icon: ShoppingCart,
    colorClass: {
      bg: "bg-emerald-500/10",
      text: "text-emerald-400",
      border: "border-emerald-500/20",
      badge: "bg-emerald-500/20 text-emerald-300",
    },
    desc: "Lead qualification, pipeline management, closing.",
    skills: ["Leads", "CRM", "Pipeline", "Quotes"],
  },
  {
    id: "hr",
    label: "Human Resources",
    icon: Users,
    colorClass: {
      bg: "bg-violet-500/10",
      text: "text-violet-400",
      border: "border-violet-500/20",
      badge: "bg-violet-500/20 text-violet-300",
    },
    desc: "Recruitment, onboarding, HR policy, performance.",
    skills: ["Recruit", "Onboard", "Policy", "PTO"],
  },
  {
    id: "finance",
    label: "Finance",
    icon: DollarSign,
    colorClass: {
      bg: "bg-rose-500/10",
      text: "text-rose-400",
      border: "border-rose-500/20",
      badge: "bg-rose-500/20 text-rose-300",
    },
    desc: "Budgets, invoicing, reporting, audit trails.",
    skills: ["Invoices", "Reports", "Budget", "Audit"],
  },
  {
    id: "technology",
    label: "Technology",
    icon: Cpu,
    colorClass: {
      bg: "bg-blue-500/10",
      text: "text-blue-400",
      border: "border-blue-500/20",
      badge: "bg-blue-500/20 text-blue-300",
    },
    desc: "IT support, infrastructure, DevOps automation.",
    skills: ["IT Help", "DevOps", "Infra", "Security"],
  },
  {
    id: "marketing",
    label: "Marketing",
    icon: Megaphone,
    colorClass: {
      bg: "bg-orange-500/10",
      text: "text-orange-400",
      border: "border-orange-500/20",
      badge: "bg-orange-500/20 text-orange-300",
    },
    desc: "Content strategy, campaigns, brand management.",
    skills: ["Content", "Ads", "SEO", "Brand"],
  },
];

const STATS = [
  { label: "Agents Online", value: "7 / 7", icon: Activity, color: "text-emerald-400", sub: "All departments active" },
  { label: "Active Sessions", value: "live", icon: MessageSquare, color: "text-amber-400", sub: "Chat + voice right now" },
  { label: "Avg Response", value: "live", icon: Clock, color: "text-cyan-400", sub: "Measured across conversations" },
  { label: "Workflows Run", value: "live", icon: TrendingUp, color: "text-violet-400", sub: "Orchestrated by Director" },
];

/* ── Component ───────────────────────────────────────────── */

export default function DashboardPage() {
  const [apiStatus, setApiStatus] = useState<"checking" | "online" | "offline">("checking");
  const [live, setLive] = useState<{ sessions: string; avgMs: string; workflows: string }>({
    sessions: "…",
    avgMs: "…",
    workflows: "…",
  });

  useEffect(() => {
    const url = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
    fetch(`${url}/api/v1/health`)
      .then((r) => setApiStatus(r.ok ? "online" : "offline"))
      .catch(() => setApiStatus("offline"));

    // Real usage numbers from system stats (admin endpoint — non-admins keep
    // the dash instead of erroring).
    import("@/lib/auth")
      .then(({ authHeaders }) =>
        fetch(`${url}/api/v1/system/stats`, { headers: authHeaders() })
      )
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!d) return;
        const sessions = (d.active_chat_sessions ?? 0) + (d.active_voice_sessions ?? 0);
        const avgMs =
          typeof d.avg_response_ms === "number" && d.avg_response_ms > 0
            ? `${Math.round(d.avg_response_ms)}ms`
            : "< 1s";
        setLive({
          sessions: String(sessions),
          avgMs,
          workflows: String(d.workflows_run ?? 0),
        });
      })
      .catch(() => {});
  }, []);

  const stats = STATS.map((s) => {
    if (s.label === "Active Sessions") return { ...s, value: live.sessions };
    if (s.label === "Avg Response") return { ...s, value: live.avgMs };
    if (s.label === "Workflows Run") return { ...s, value: live.workflows };
    return s;
  });

  return (
    <div className="px-8 py-8 max-w-screen-2xl">
      {/* ── Header ─────────────────────────────────────────── */}
      <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-2 flex items-center gap-2">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider ${
                apiStatus === "online"
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                  : apiStatus === "offline"
                  ? "border-red-500/30 bg-red-500/10 text-red-400"
                  : "border-slate-700 bg-slate-800/50 text-slate-500"
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  apiStatus === "online" ? "bg-emerald-500 status-pulse" : "bg-slate-500"
                }`}
              />
              API {apiStatus}
            </span>
          </div>
          <h1
            className="text-4xl font-bold tracking-tight text-slate-100"
            style={{ fontFamily: "var(--font-syne)" }}
          >
            AI Workforce
          </h1>
          <p className="mt-1.5 text-sm text-slate-400">
            Enterprise multi-agent platform — 7 departments, real-time voice &amp; chat
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Link
            href="/chat"
            className="flex items-center gap-2 rounded-lg bg-amber-500 px-4 py-2.5 text-sm font-semibold text-black transition-colors hover:bg-amber-400"
          >
            <MessageSquare className="h-4 w-4" />
            New Chat
          </Link>
          <Link
            href="/voice"
            className="flex items-center gap-2 rounded-lg border border-[#374151] bg-[#0c111d] px-4 py-2.5 text-sm font-medium text-slate-200 transition-colors hover:border-[#4b5563] hover:bg-[#111827]"
          >
            <Mic className="h-4 w-4" />
            Voice Call
          </Link>
        </div>
      </div>

      {/* ── Stats row ──────────────────────────────────────── */}
      <div className="mb-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {stats.map((s) => (
          <div
            key={s.label}
            className="rounded-xl border border-[#1f2937] bg-[#0c111d] p-5 transition-colors hover:border-[#2d3f55]"
          >
            <div className="mb-3 flex items-center justify-between">
              <p className="text-[11px] font-mono uppercase tracking-widest text-slate-500">
                {s.label}
              </p>
              <s.icon className={`h-4 w-4 ${s.color}`} />
            </div>
            <p className={`font-mono text-3xl font-bold ${s.color}`}>{s.value}</p>
            <p className="mt-1.5 text-[11px] text-slate-600">{s.sub}</p>
          </div>
        ))}
      </div>

      {/* ── Agent cards ────────────────────────────────────── */}
      <div className="mb-4 flex items-center justify-between">
        <h2
          className="text-[11px] font-mono uppercase tracking-[0.18em] text-slate-500"
        >
          Department Agents
        </h2>
        <span className="flex items-center gap-1.5 text-[11px] text-slate-500">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 status-pulse" />
          7 online
        </span>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
        {AGENTS.map((agent) => {
          const Icon = agent.icon;
          const c = agent.colorClass;
          return (
            <div
              key={agent.id}
              className="group slide-up rounded-xl border border-[#1f2937] bg-[#0c111d] p-5 transition-all hover:border-[#2d3f55] hover:bg-[#0f1624]"
            >
              {/* Card header */}
              <div className="mb-4 flex items-start justify-between">
                <div className={`rounded-lg border p-2.5 ${c.bg} ${c.border}`}>
                  <Icon className={`h-5 w-5 ${c.text}`} />
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 status-pulse" />
                  <span className="font-mono text-[10px] uppercase tracking-wide text-emerald-400">
                    Online
                  </span>
                </div>
              </div>

              {/* Name + desc */}
              <h3 className="mb-1 font-semibold text-slate-100">{agent.label}</h3>
              <p className="mb-4 text-xs leading-relaxed text-slate-500">{agent.desc}</p>

              {/* Skill pills */}
              <div className="mb-4 flex flex-wrap gap-1.5">
                {agent.skills.map((s) => (
                  <span
                    key={s}
                    className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${c.badge}`}
                  >
                    {s}
                  </span>
                ))}
              </div>

              {/* Actions */}
              <div className="flex gap-2">
                <Link
                  href={`/chat?dept=${agent.id}`}
                  className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-[#1f2937] bg-[#111827] py-2 text-xs text-slate-400 transition-all hover:border-[#374151] hover:text-slate-200"
                >
                  <MessageSquare className="h-3 w-3" />
                  Chat
                </Link>
                <Link
                  href={`/voice?dept=${agent.id}`}
                  className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-[#1f2937] bg-[#111827] py-2 text-xs text-slate-400 transition-all hover:border-[#374151] hover:text-slate-200"
                >
                  <Mic className="h-3 w-3" />
                  Voice
                </Link>
              </div>
            </div>
          );
        })}
      </div>

      {/* ── Platform info footer ────────────────────────────── */}
      <div className="mt-10 rounded-xl border border-[#1f2937] bg-[#0c111d] p-5">
        <div className="flex flex-wrap items-center gap-6">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500/10">
              <Zap className="h-4 w-4 text-amber-400" />
            </div>
            <div>
              <p className="text-xs font-semibold text-slate-300">AI Workforce Platform</p>
              <p className="text-[11px] text-slate-500">Enterprise Multi-Agent Orchestration</p>
            </div>
          </div>

          {[
            { label: "AI Capabilities", value: "Chat · Voice · Workflows · Automation" },
            { label: "Integrations",    value: "CRM · HRIS · ERP · DevOps · Analytics" },
            { label: "Security",        value: "RBAC · Audit Logs · Tenant Isolation" },
          ].map((item) => (
            <div key={item.label}>
              <p className="text-[10px] font-mono uppercase tracking-wider text-slate-600">
                {item.label}
              </p>
              <p className="mt-0.5 text-xs text-slate-400">{item.value}</p>
            </div>
          ))}

          <a
            href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080"}/docs`}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto flex items-center gap-1.5 text-xs text-slate-500 transition-colors hover:text-amber-400"
          >
            API Docs
            <ArrowUpRight className="h-3.5 w-3.5" />
          </a>
        </div>
      </div>
    </div>
  );
}
