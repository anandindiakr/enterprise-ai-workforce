"use client";

/**
 * Tenant Self-Service Portal
 * Visible to any authenticated user — shows their own tenant's dashboard.
 * No admin privileges required.
 */

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Building2, Users, MessageSquare, BookOpen, Mic,
  TrendingUp, Shield, Crown, Zap, Clock, Sparkles,
  RefreshCw, ChevronRight, CheckCircle, AlertTriangle,
  BarChart3, Settings, ArrowUpRight, Plus, HelpCircle,
  Activity, Database, Star,
} from "lucide-react";
import { getUser, authHeaders, isAuthenticated } from "@/lib/auth";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

// ─── Types ────────────────────────────────────────────────────────────────────

interface Tenant {
  id: string;
  slug: string;
  name: string;
  admin_email: string;
  plan: "free" | "starter" | "pro" | "enterprise";
  status: "active" | "suspended" | "trial";
  max_users: number;
  max_chat_sessions: number;
  max_voice_minutes: number;
  trial_ends_at?: string;
  created_at: string;
}

interface UsageStats {
  tenant: Tenant;
  usage: {
    users: { total: number; active: number; limit: number; utilisation_pct: number };
    chat_sessions: { total: number; limit: number; utilisation_pct: number };
    messages: { total: number };
    escalations: { total: number };
    knowledge_docs: { total: number };
  };
}

interface KBStats {
  total: number;
  indexed: number;
  complete: number;
  pending: number;
  failed: number;
  vector_count: number;
  chroma_available: boolean;
  agents_have_access: boolean;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const PLAN_META: Record<string, { label: string; color: string; Icon: React.ElementType }> = {
  free:       { label: "Free",       color: "text-slate-400",  Icon: Clock },
  starter:    { label: "Starter",    color: "text-blue-400",   Icon: Zap },
  pro:        { label: "Pro",        color: "text-amber-400",  Icon: Crown },
  enterprise: { label: "Enterprise", color: "text-violet-400", Icon: Sparkles },
};

const STATUS_META: Record<string, { label: string; color: string }> = {
  active:    { label: "Active",    color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30" },
  suspended: { label: "Suspended", color: "text-red-400 bg-red-500/10 border-red-500/30" },
  trial:     { label: "Trial",     color: "text-amber-400 bg-amber-500/10 border-amber-500/30" },
};

const QUICK_LINKS = [
  { label: "Start a Chat",    href: "/chat",       Icon: MessageSquare, color: "text-blue-400" },
  { label: "Voice Console",   href: "/voice",      Icon: Mic,           color: "text-violet-400" },
  { label: "Knowledge Base",  href: "/knowledge",  Icon: BookOpen,      color: "text-emerald-400" },
  { label: "Analytics",       href: "/analytics",  Icon: BarChart3,     color: "text-amber-400" },
  { label: "Settings",        href: "/settings",   Icon: Settings,      color: "text-slate-400" },
  { label: "Escalations",     href: "/escalations",Icon: AlertTriangle, color: "text-red-400" },
];

// ─── Sub-components ───────────────────────────────────────────────────────────

function UsageBar({ pct, label }: { pct: number; label: string }) {
  const color = pct >= 90 ? "bg-red-500" : pct >= 70 ? "bg-amber-500" : "bg-emerald-500";
  return (
    <div>
      <div className="flex justify-between text-xs text-slate-400 mb-1">
        <span>{label}</span>
        <span className={pct >= 90 ? "text-red-400 font-medium" : ""}>{pct.toFixed(0)}%</span>
      </div>
      <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
    </div>
  );
}

function StatCard({
  label, value, sub, Icon, color,
}: {
  label: string; value: string | number; sub?: string; Icon: React.ElementType; color: string;
}) {
  return (
    <div className="rounded-xl border border-slate-700 bg-slate-800/60 p-4 flex items-start gap-3">
      <div className={`p-2 rounded-lg bg-slate-700/60 ${color}`}>
        <Icon className="h-4 w-4" />
      </div>
      <div>
        <p className="text-2xl font-bold text-white">{value}</p>
        <p className="text-xs text-slate-400 mt-0.5">{label}</p>
        {sub && <p className="text-xs text-slate-500 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function PortalPage() {
  const router = useRouter();
  const user = getUser();

  const [stats, setStats] = useState<UsageStats | null>(null);
  const [kbStats, setKbStats] = useState<KBStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const tenantSlug = user?.tenant_id || "default";

  // Redirect if not authenticated
  useEffect(() => {
    if (!isAuthenticated()) router.push("/login");
  }, [router]);

  const fetchStats = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    else setRefreshing(true);
    setError("");
    try {
      const [statsRes, kbRes] = await Promise.all([
        fetch(`${API}/api/v1/tenants/${tenantSlug}/stats`, { headers: authHeaders() }),
        fetch(`${API}/api/v1/knowledge/stats`, { headers: authHeaders() }),
      ]);
      if (!statsRes.ok) throw new Error(`Stats error ${statsRes.status}`);
      const [s, k] = await Promise.all([statsRes.json(), kbRes.ok ? kbRes.json() : null]);
      setStats(s as UsageStats);
      if (k) setKbStats(k as KBStats);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load dashboard");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [tenantSlug]);

  useEffect(() => { fetchStats(); }, [fetchStats]);

  const plan = stats?.tenant.plan ?? "free";
  const pm = PLAN_META[plan] ?? PLAN_META.free;
  const sm = STATUS_META[stats?.tenant.status ?? "active"] ?? STATUS_META.active;

  if (loading) {
    return (
      <div className="p-6 max-w-6xl mx-auto">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-slate-700 rounded w-1/3" />
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-24 bg-slate-800 rounded-xl border border-slate-700" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 max-w-6xl mx-auto">
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-6 text-center">
          <AlertTriangle className="h-8 w-8 text-red-400 mx-auto mb-2" />
          <p className="text-red-300 font-medium">{error}</p>
          <button
            onClick={() => fetchStats()}
            className="mt-4 px-4 py-2 rounded-lg bg-red-600 text-white text-sm hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const u = stats!.usage;
  const t = stats!.tenant;

  const trialDaysLeft = t.trial_ends_at
    ? Math.max(0, Math.ceil((new Date(t.trial_ends_at).getTime() - Date.now()) / 86400000))
    : null;

  return (
    <div className="p-6 max-w-6xl mx-auto text-slate-100 space-y-6">

      {/* ── Header ───────────────────────────────────────────────── */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-violet-500/15 border border-violet-500/30">
            <Building2 className="h-6 w-6 text-violet-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">{t.name}</h1>
            <p className="text-sm text-slate-400 mt-0.5">
              Welcome back, <span className="text-slate-300">{user?.full_name ?? user?.username ?? "User"}</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Status badge */}
          <span className={`px-3 py-1 rounded-full text-xs font-medium border ${sm.color}`}>
            {sm.label}
          </span>

          {/* Plan badge */}
          <span className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border border-slate-600 bg-slate-800 ${pm.color}`}>
            <pm.Icon className="h-3 w-3" />
            {pm.label} Plan
          </span>

          {/* Refresh */}
          <button
            onClick={() => fetchStats(true)}
            disabled={refreshing}
            className="p-2 rounded-lg border border-slate-600 bg-slate-800 text-slate-400 hover:bg-slate-700 transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* ── Trial warning ─────────────────────────────────────────── */}
      {t.status === "trial" && trialDaysLeft !== null && (
        <div className={`rounded-xl border p-4 flex items-center gap-3 ${
          trialDaysLeft <= 3
            ? "bg-red-500/10 border-red-500/30 text-red-300"
            : "bg-amber-500/10 border-amber-500/30 text-amber-300"
        }`}>
          <AlertTriangle className="h-5 w-5 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-medium">
              {trialDaysLeft === 0
                ? "Your trial ends today!"
                : `Trial ends in ${trialDaysLeft} day${trialDaysLeft !== 1 ? "s" : ""}`}
            </p>
            <p className="text-xs opacity-80 mt-0.5">
              Contact your administrator to upgrade your plan.
            </p>
          </div>
        </div>
      )}

      {/* ── Key stats ─────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          Icon={Users}
          color="text-blue-400"
          label="Team Members"
          value={u.users.total}
          sub={`${u.users.active} active · limit ${u.users.limit}`}
        />
        <StatCard
          Icon={MessageSquare}
          color="text-violet-400"
          label="Chat Sessions"
          value={u.chat_sessions.total}
          sub={`${u.messages.total} messages total`}
        />
        <StatCard
          Icon={BookOpen}
          color="text-emerald-400"
          label="Knowledge Docs"
          value={kbStats?.total ?? u.knowledge_docs.total}
          sub={kbStats ? `${kbStats.indexed} indexed · ${kbStats.vector_count} vectors` : ""}
        />
        <StatCard
          Icon={AlertTriangle}
          color="text-amber-400"
          label="Escalations"
          value={u.escalations.total}
          sub="open human handoffs"
        />
      </div>

      {/* ── Usage limits ──────────────────────────────────────────── */}
      <div className="rounded-xl border border-slate-700 bg-slate-800/60 p-5">
        <h2 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
          <Activity className="h-4 w-4 text-violet-400" />
          Plan Usage
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
          <div className="space-y-1">
            <UsageBar pct={u.users.utilisation_pct} label="Users" />
            <p className="text-xs text-slate-500">{u.users.total} / {u.users.limit} seats</p>
          </div>
          <div className="space-y-1">
            <UsageBar pct={u.chat_sessions.utilisation_pct} label="Chat Sessions" />
            <p className="text-xs text-slate-500">{u.chat_sessions.total} / {u.chat_sessions.limit} sessions</p>
          </div>
          <div className="space-y-1">
            {/* Voice minutes bar — not tracked in stats yet, show plan max */}
            <div>
              <div className="flex justify-between text-xs text-slate-400 mb-1">
                <span>Voice Minutes</span>
                <span>{t.max_voice_minutes} min limit</span>
              </div>
              <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                <div className="h-full bg-blue-500 rounded-full w-0" />
              </div>
            </div>
            <p className="text-xs text-slate-500">0 / {t.max_voice_minutes} minutes used</p>
          </div>
        </div>
      </div>

      {/* ── Quick launch ──────────────────────────────────────────── */}
      <div>
        <h2 className="text-sm font-semibold text-slate-400 mb-3 flex items-center gap-2">
          <Zap className="h-4 w-4" /> Quick Launch
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {QUICK_LINKS.map(({ label, href, Icon, color }) => (
            <button
              key={href}
              onClick={() => router.push(href)}
              className="flex flex-col items-center gap-2 p-4 rounded-xl border border-slate-700 bg-slate-800/60 hover:border-slate-600 hover:bg-slate-700/60 transition-all group"
            >
              <Icon className={`h-6 w-6 ${color} group-hover:scale-110 transition-transform`} />
              <span className="text-xs text-slate-400 group-hover:text-slate-200 text-center">{label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* ── Two-column lower section ───────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Knowledge base health */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/60 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
              <Database className="h-4 w-4 text-emerald-400" />
              Knowledge Base Health
            </h2>
            <button
              onClick={() => router.push("/knowledge")}
              className="text-xs text-violet-400 hover:text-violet-300 flex items-center gap-1"
            >
              Manage <ChevronRight className="h-3 w-3" />
            </button>
          </div>

          {kbStats ? (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                {[
                  { label: "Total Docs",   value: kbStats.total,        color: "text-slate-300" },
                  { label: "Indexed",      value: kbStats.indexed,      color: "text-emerald-400" },
                  { label: "Vectorized",   value: kbStats.complete,     color: "text-blue-400" },
                  { label: "Vectors",      value: kbStats.vector_count, color: "text-violet-400" },
                ].map(({ label, value, color }) => (
                  <div key={label} className="rounded-lg bg-slate-700/50 p-3">
                    <p className={`text-xl font-bold ${color}`}>{value}</p>
                    <p className="text-xs text-slate-500">{label}</p>
                  </div>
                ))}
              </div>

              {/* Status indicators */}
              <div className="flex items-center gap-2 flex-wrap">
                <div className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded-full border ${
                  kbStats.chroma_available
                    ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/30"
                    : "text-red-400 bg-red-500/10 border-red-500/30"
                }`}>
                  {kbStats.chroma_available
                    ? <CheckCircle className="h-3 w-3" />
                    : <AlertTriangle className="h-3 w-3" />}
                  Vector DB {kbStats.chroma_available ? "Online" : "Offline"}
                </div>
                <div className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded-full border ${
                  kbStats.agents_have_access
                    ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/30"
                    : "text-amber-400 bg-amber-500/10 border-amber-500/30"
                }`}>
                  {kbStats.agents_have_access
                    ? <CheckCircle className="h-3 w-3" />
                    : <AlertTriangle className="h-3 w-3" />}
                  Agents {kbStats.agents_have_access ? "Have Access" : "No Docs Yet"}
                </div>
                {kbStats.failed > 0 && (
                  <div className="flex items-center gap-1.5 text-xs px-2 py-1 rounded-full border text-red-400 bg-red-500/10 border-red-500/30">
                    <AlertTriangle className="h-3 w-3" />
                    {kbStats.failed} failed
                  </div>
                )}
              </div>

              {!kbStats.agents_have_access && (
                <button
                  onClick={() => router.push("/knowledge")}
                  className="w-full text-sm text-center py-2 rounded-lg border border-violet-500/30 text-violet-400 hover:bg-violet-500/10 transition-colors flex items-center justify-center gap-2"
                >
                  <Plus className="h-4 w-4" /> Upload your first document
                </button>
              )}
            </div>
          ) : (
            <p className="text-slate-500 text-sm">Knowledge base stats unavailable</p>
          )}
        </div>

        {/* Plan details */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/60 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
              <Star className="h-4 w-4 text-amber-400" />
              Your Plan
            </h2>
          </div>

          <div className="flex items-center gap-3 mb-5">
            <div className={`p-3 rounded-xl bg-slate-700/60 ${pm.color}`}>
              <pm.Icon className="h-6 w-6" />
            </div>
            <div>
              <p className={`text-lg font-bold ${pm.color}`}>{pm.label}</p>
              <p className="text-xs text-slate-500">{t.slug} · since {new Date(t.created_at).toLocaleDateString()}</p>
            </div>
          </div>

          <div className="space-y-2 mb-5">
            {[
              { label: "Team seats",       value: t.max_users,           Icon: Users },
              { label: "Chat sessions",    value: t.max_chat_sessions.toLocaleString(), Icon: MessageSquare },
              { label: "Voice minutes",    value: t.max_voice_minutes,   Icon: Mic },
            ].map(({ label, value, Icon }) => (
              <div key={label} className="flex items-center justify-between py-1.5 border-b border-slate-700/50">
                <div className="flex items-center gap-2 text-sm text-slate-400">
                  <Icon className="h-3.5 w-3.5" />
                  {label}
                </div>
                <span className="text-sm font-medium text-slate-200">{value}</span>
              </div>
            ))}
          </div>

          {plan !== "enterprise" && (
            <div className="rounded-lg border border-violet-500/30 bg-violet-500/5 p-3 text-center">
              <p className="text-xs text-violet-300 mb-2">
                Need more capacity? Ask your administrator about upgrading.
              </p>
              <div className="flex items-center justify-center gap-1 text-xs text-violet-400">
                <Shield className="h-3 w-3" />
                Contact: {t.admin_email}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Getting started checklist ──────────────────────────────── */}
      <GettingStartedChecklist
        hasKbDocs={(kbStats?.total ?? 0) > 0}
        hasChatSessions={u.chat_sessions.total > 0}
        hasUsers={u.users.total > 1}
        onNavigate={router.push}
      />
    </div>
  );
}

// ─── Getting Started Checklist ────────────────────────────────────────────────

function GettingStartedChecklist({
  hasKbDocs, hasChatSessions, hasUsers, onNavigate,
}: {
  hasKbDocs: boolean;
  hasChatSessions: boolean;
  hasUsers: boolean;
  onNavigate: (href: string) => void;
}) {
  const steps = [
    {
      id: "kb",
      done: hasKbDocs,
      label: "Upload to Knowledge Base",
      desc: "Give your agents product info, FAQs, and policies so they can answer accurately.",
      href: "/knowledge",
      cta: "Upload Documents",
    },
    {
      id: "chat",
      done: hasChatSessions,
      label: "Start your first chat",
      desc: "Talk to any AI department agent via the chat interface.",
      href: "/chat",
      cta: "Open Chat",
    },
    {
      id: "users",
      done: hasUsers,
      label: "Invite team members",
      desc: "Add your colleagues so they can also interact with the AI workforce.",
      href: "/settings",
      cta: "Manage Users",
    },
  ];

  const completedCount = steps.filter((s) => s.done).length;
  if (completedCount === steps.length) return null;

  return (
    <div className="rounded-xl border border-blue-500/30 bg-blue-500/5 p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-blue-300 flex items-center gap-2">
          <TrendingUp className="h-4 w-4" />
          Getting Started
        </h2>
        <span className="text-xs text-blue-400">
          {completedCount}/{steps.length} complete
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-1.5 bg-blue-900/50 rounded-full mb-5 overflow-hidden">
        <div
          className="h-full bg-blue-500 rounded-full transition-all"
          style={{ width: `${(completedCount / steps.length) * 100}%` }}
        />
      </div>

      <div className="space-y-3">
        {steps.map((step) => (
          <div
            key={step.id}
            className={`flex items-start gap-3 p-3 rounded-lg border transition-colors ${
              step.done
                ? "border-emerald-500/20 bg-emerald-500/5 opacity-60"
                : "border-blue-500/20 bg-blue-500/5 hover:border-blue-500/40"
            }`}
          >
            {step.done ? (
              <CheckCircle className="h-5 w-5 text-emerald-400 flex-shrink-0 mt-0.5" />
            ) : (
              <HelpCircle className="h-5 w-5 text-blue-400 flex-shrink-0 mt-0.5" />
            )}
            <div className="flex-1 min-w-0">
              <p className={`text-sm font-medium ${step.done ? "text-slate-400 line-through" : "text-slate-200"}`}>
                {step.label}
              </p>
              <p className="text-xs text-slate-500 mt-0.5">{step.desc}</p>
            </div>
            {!step.done && (
              <button
                onClick={() => onNavigate(step.href)}
                className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 flex-shrink-0 mt-0.5"
              >
                {step.cta} <ArrowUpRight className="h-3 w-3" />
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
