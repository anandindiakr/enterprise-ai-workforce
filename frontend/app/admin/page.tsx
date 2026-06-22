"use client";

/**
 * Admin Dashboard — consolidated control panel for platform administrators.
 * Shows system-wide stats, user list, recent escalations, tenants, and
 * quick nav to all admin sections.
 */

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Shield, Users, MessageSquare, AlertTriangle, BookOpen,
  Building2, Activity, ClipboardList, Plug, UserCog,
  RefreshCw, CheckCircle, XCircle, ArrowRight, BarChart3,
  Zap,
} from "lucide-react";
import { getUser, authHeaders, isAuthenticated } from "@/lib/auth";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

// ─── Types ────────────────────────────────────────────────────────────────────

interface SvcStatus { status: string; latency_ms?: number }
interface SystemHealth { status: string; services: Record<string, SvcStatus> }

interface UserRecord {
  id: string; username: string; email: string;
  full_name?: string | null; roles: string[]; is_active: boolean;
}

interface EscRecord {
  id: string; customer_name?: string; department?: string;
  status: string; priority?: string; created_at: string;
}

interface KBStats {
  total: number; indexed: number; vector_count: number; chroma_available: boolean;
}

interface TenantRow {
  id: string; slug: string; name: string; plan: string;
  status: string; max_users: number;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function safeJson<T>(res: Response, fallback: T): Promise<T> {
  try { return await res.json() as T; } catch { return fallback; }
}

function extractList<T>(raw: unknown): T[] {
  if (Array.isArray(raw)) return raw as T[];
  if (raw && typeof raw === "object") {
    const r = raw as Record<string, unknown>;
    for (const k of ["users", "items", "escalations", "tenants", "results"]) {
      if (Array.isArray(r[k])) return r[k] as T[];
    }
  }
  return [];
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function StatCard({
  icon: Icon, label, value, sub, color, onClick,
}: {
  icon: React.ElementType; label: string; value: string | number;
  sub?: string; color: string; onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className={`rounded-xl border border-slate-700 bg-slate-800/60 p-4 flex items-start gap-3 ${onClick ? "cursor-pointer hover:border-slate-500 hover:bg-slate-700/60 transition-all" : ""}`}
    >
      <div className={`p-2 rounded-lg bg-slate-700/60 ${color}`}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-2xl font-bold text-white">{value}</p>
        <p className="text-xs text-slate-400 mt-0.5">{label}</p>
        {sub && <p className="text-xs text-slate-500 mt-0.5">{sub}</p>}
      </div>
      {onClick && <ArrowRight className="h-3.5 w-3.5 text-slate-600 self-center flex-shrink-0" />}
    </div>
  );
}

function SvcRow({ name, svc }: { name: string; svc: SvcStatus }) {
  const ok = svc.status === "ok" || svc.status === "healthy";
  return (
    <div className="flex items-center justify-between py-2 border-b border-slate-700/50 last:border-0">
      <div className="flex items-center gap-2">
        {ok ? <CheckCircle className="h-3.5 w-3.5 text-emerald-400" /> : <XCircle className="h-3.5 w-3.5 text-red-400" />}
        <span className="text-sm text-slate-300 capitalize">{name.replace(/_/g, " ")}</span>
      </div>
      <div className="flex items-center gap-2">
        {svc.latency_ms !== undefined && <span className="text-xs text-slate-500">{svc.latency_ms}ms</span>}
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${ok ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/30" : "text-red-400 bg-red-500/10 border-red-500/30"}`}>
          {svc.status}
        </span>
      </div>
    </div>
  );
}

const QUICK_NAV = [
  { href: "/admin/users",  Icon: UserCog,      label: "User Management",  color: "text-blue-400",    desc: "Create, edit, disable users" },
  { href: "/tenants",      Icon: Building2,    label: "Tenants",          color: "text-violet-400",  desc: "Manage organisations" },
  { href: "/monitoring",   Icon: Activity,     label: "System Monitor",   color: "text-emerald-400", desc: "Service health & metrics" },
  { href: "/audit",        Icon: ClipboardList,label: "Audit Log",        color: "text-amber-400",   desc: "Security & change log" },
  { href: "/integrations", Icon: Plug,         label: "Integrations",     color: "text-cyan-400",    desc: "MCP & API connectors" },
  { href: "/analytics",    Icon: BarChart3,    label: "Analytics",        color: "text-rose-400",    desc: "Usage & performance" },
  { href: "/escalations",  Icon: AlertTriangle,label: "Escalations",      color: "text-orange-400",  desc: "Human handoff queue" },
  { href: "/knowledge",    Icon: BookOpen,     label: "Knowledge Base",   color: "text-teal-400",    desc: "Documents & vectors" },
];

const PLAN_COLOR: Record<string, string> = {
  free: "text-slate-400", starter: "text-blue-400",
  pro: "text-amber-400", enterprise: "text-violet-400",
};

// ─── Main page ─────────────────────────────────────────────────────────────────

export default function AdminDashboardPage() {
  const router = useRouter();
  const user = getUser();

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [escs, setEscs] = useState<EscRecord[]>([]);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [kb, setKb] = useState<KBStats | null>(null);
  const [tenants, setTenants] = useState<TenantRow[]>([]);

  // Guard: admin only
  useEffect(() => {
    if (!isAuthenticated()) { router.push("/login"); return; }
    if (user && !user.roles?.includes("admin")) { router.push("/"); }
  }, [router, user]);

  const load = useCallback(async () => {
    const [uR, eR, hR, kR, tR] = await Promise.allSettled([
      fetch(`${API}/api/v1/users/?limit=100`,      { headers: authHeaders() }),
      fetch(`${API}/api/v1/escalations/?limit=10`, { headers: authHeaders() }),
      fetch(`${API}/api/v1/system/stats`,          { headers: authHeaders() }),
      fetch(`${API}/api/v1/knowledge/stats`,       { headers: authHeaders() }),
      fetch(`${API}/api/v1/tenants/?limit=100`,    { headers: authHeaders() }),
    ]);

    if (uR.status === "fulfilled" && uR.value.ok)
      setUsers(extractList<UserRecord>(await safeJson(uR.value, {})));
    if (eR.status === "fulfilled" && eR.value.ok)
      setEscs(extractList<EscRecord>(await safeJson(eR.value, {})));
    if (hR.status === "fulfilled" && hR.value.ok) {
      const raw = await safeJson<Record<string, unknown>>(hR.value, {});
      // /api/v1/system/stats returns {services:[{name,status,...}],...}
      // Normalise into the {services: Record<string,SvcStatus>} shape
      const svcArray = (raw.services ?? []) as { name: string; status: string; latency_ms?: number; details?: string }[];
      const svcMap: Record<string, SvcStatus> = {};
      for (const s of svcArray) svcMap[s.name] = { status: s.status, latency_ms: s.latency_ms };
      setHealth({ status: raw.status as string ?? "ok", services: svcMap });
    }
    if (kR.status === "fulfilled" && kR.value.ok)
      setKb(await safeJson<KBStats | null>(kR.value, null));
    if (tR.status === "fulfilled" && tR.value.ok)
      setTenants(extractList<TenantRow>(await safeJson(tR.value, {})));
  }, []);

  useEffect(() => {
    load().finally(() => setLoading(false));
  }, [load]);

  const refresh = useCallback(() => {
    setRefreshing(true);
    load().finally(() => setRefreshing(false));
  }, [load]);
  // Derived
  const activeUsers  = users.filter((u) => u.is_active).length;
  const adminCount   = users.filter((u) => u.roles?.includes("admin")).length;
  const openEsc      = escs.filter((e) => e.status === "open" || e.status === "pending").length;
  const allOk        = health ? Object.values(health.services ?? {}).every((s) => s.status === "ok" || s.status === "healthy") : null;

  if (loading) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-slate-700 rounded w-48" />
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[0,1,2,3].map((i) => <div key={i} className="h-24 bg-slate-800 rounded-xl border border-slate-700" />)}
          </div>
          <div className="h-64 bg-slate-800 rounded-xl border border-slate-700" />
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto text-slate-100 space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-red-500/15 border border-red-500/30">
            <Shield className="h-6 w-6 text-red-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Admin Panel</h1>
            <p className="text-sm text-slate-400 mt-0.5">
              Logged in as <span className="text-slate-300 font-medium">{user?.username}</span>
            </p>
          </div>
        </div>
        <button
          onClick={refresh} disabled={refreshing}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-600 bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors text-sm"
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* System health banner */}
      {allOk !== null && (
        <div className={`rounded-xl border p-3 flex items-center gap-3 ${allOk ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-300" : "border-red-500/30 bg-red-500/5 text-red-300"}`}>
          {allOk ? <CheckCircle className="h-5 w-5 flex-shrink-0" /> : <AlertTriangle className="h-5 w-5 flex-shrink-0" />}
          <span className="text-sm font-medium">
            {allOk ? "All systems operational" : "One or more services degraded — check System Monitor"}
          </span>
          <button onClick={() => router.push("/monitoring")} className="ml-auto text-xs underline opacity-70 hover:opacity-100">
            View details
          </button>
        </div>
      )}

      {/* Key metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Users}         label="Total Users"       value={users.length}       sub={`${activeUsers} active · ${adminCount} admins`}                                   color="text-blue-400"   onClick={() => router.push("/admin/users")} />
        <StatCard icon={Building2}     label="Tenants"           value={tenants.length}     sub="registered organisations"                                                         color="text-violet-400" onClick={() => router.push("/tenants")} />
        <StatCard icon={AlertTriangle} label="Open Escalations"  value={openEsc}            sub={`${escs.length} total in queue`}                                                  color="text-amber-400"  onClick={() => router.push("/escalations")} />
        <StatCard icon={BookOpen}      label="KB Documents"      value={kb?.total ?? "—"}   sub={kb ? `${kb.indexed} indexed · ${kb.vector_count} vectors` : "stats unavailable"} color="text-emerald-400" onClick={() => router.push("/knowledge")} />
      </div>

      {/* Users + Health side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Users table */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/60 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
              <Users className="h-4 w-4 text-blue-400" /> Platform Users
            </h2>
            <button onClick={() => router.push("/admin/users")} className="text-xs text-violet-400 hover:text-violet-300 flex items-center gap-1">
              Manage <ArrowRight className="h-3 w-3" />
            </button>
          </div>
          {users.length === 0 ? (
            <p className="text-slate-500 text-sm">No users found</p>
          ) : (
            <>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-slate-500 text-xs">
                    <th className="pb-2 font-medium">Username</th>
                    <th className="pb-2 font-medium">Roles</th>
                    <th className="pb-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/50">
                  {users.slice(0, 8).map((u) => (
                    <tr key={u.id}>
                      <td className="py-2 pr-4">
                        <div className="font-medium text-slate-200 truncate max-w-[120px]">{u.username}</div>
                        {u.full_name && <div className="text-xs text-slate-500 truncate">{u.full_name}</div>}
                      </td>
                      <td className="py-2 pr-4">
                        <div className="flex flex-wrap gap-1">
                          {(u.roles ?? []).map((r) => (
                            <span key={r} className={`rounded-full border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${r === "admin" ? "bg-red-500/15 text-red-400 border-red-500/30" : r === "agent" ? "bg-blue-500/15 text-blue-400 border-blue-500/30" : "bg-slate-700/40 text-slate-400 border-slate-700"}`}>
                              {r}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="py-2">
                        <span className={`flex items-center gap-1 text-xs ${u.is_active ? "text-emerald-400" : "text-slate-500"}`}>
                          <span className={`h-1.5 w-1.5 rounded-full ${u.is_active ? "bg-emerald-400" : "bg-slate-600"}`} />
                          {u.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {users.length > 8 && (
                <p className="text-xs text-slate-500 mt-2 text-right">
                  +{users.length - 8} more —{" "}
                  <button onClick={() => router.push("/admin/users")} className="text-violet-400 hover:underline">view all</button>
                </p>
              )}
            </>
          )}
        </div>

        {/* Service health */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/60 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
              <Activity className="h-4 w-4 text-emerald-400" /> Service Health
            </h2>
            <button onClick={() => router.push("/monitoring")} className="text-xs text-violet-400 hover:text-violet-300 flex items-center gap-1">
              Full monitor <ArrowRight className="h-3 w-3" />
            </button>
          </div>
          {health ? (
            Object.keys(health.services ?? {}).length > 0 ? (
              Object.entries(health.services).map(([name, svc]) => (
                <SvcRow key={name} name={name} svc={svc} />
              ))
            ) : (
              <p className="text-slate-500 text-sm">No service data available</p>
            )
          ) : (
            <div className="flex flex-col items-center justify-center py-8 gap-2">
              <XCircle className="h-8 w-8 text-slate-600" />
              <p className="text-slate-500 text-sm">Health data unavailable</p>
              <button onClick={() => router.push("/monitoring")} className="text-xs text-violet-400 hover:underline">Open System Monitor</button>
            </div>
          )}
        </div>
      </div>

      {/* Recent escalations */}
      <div className="rounded-xl border border-slate-700 bg-slate-800/60 p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-400" /> Recent Escalations
          </h2>
          <button onClick={() => router.push("/escalations")} className="text-xs text-violet-400 hover:text-violet-300 flex items-center gap-1">
            View all <ArrowRight className="h-3 w-3" />
          </button>
        </div>
        {escs.length === 0 ? (
          <p className="text-slate-500 text-sm">No escalations in queue</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-500 text-xs">
                  <th className="pb-2 font-medium">Customer</th>
                  <th className="pb-2 font-medium">Dept</th>
                  <th className="pb-2 font-medium">Priority</th>
                  <th className="pb-2 font-medium">Status</th>
                  <th className="pb-2 font-medium">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/50">
                {escs.slice(0, 6).map((e) => (
                  <tr key={e.id}>
                    <td className="py-2 pr-3 font-medium text-slate-200">{e.customer_name ?? "Unknown"}</td>
                    <td className="py-2 pr-3 text-slate-400 capitalize text-xs">{e.department ?? "—"}</td>
                    <td className="py-2 pr-3">
                      <span className={`text-xs font-medium ${e.priority === "high" ? "text-red-400" : e.priority === "medium" ? "text-amber-400" : "text-slate-400"}`}>
                        {e.priority ?? "normal"}
                      </span>
                    </td>
                    <td className="py-2 pr-3">
                      <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${e.status === "open" ? "bg-amber-500/15 text-amber-400 border-amber-500/30" : e.status === "resolved" ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" : "bg-slate-700/40 text-slate-400 border-slate-700"}`}>
                        {e.status}
                      </span>
                    </td>
                    <td className="py-2 text-slate-500 text-xs">{e.created_at ? new Date(e.created_at).toLocaleDateString() : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Tenants grid */}
      {tenants.length > 0 && (
        <div className="rounded-xl border border-slate-700 bg-slate-800/60 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
              <Building2 className="h-4 w-4 text-violet-400" /> Registered Tenants
            </h2>
            <button onClick={() => router.push("/tenants")} className="text-xs text-violet-400 hover:text-violet-300 flex items-center gap-1">
              Manage <ArrowRight className="h-3 w-3" />
            </button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {tenants.map((t) => (
              <div key={t.id} className="rounded-lg bg-slate-700/40 border border-slate-700 p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-slate-200 text-sm truncate">{t.name}</span>
                  <span className={`text-xs font-semibold uppercase ${PLAN_COLOR[t.plan] ?? "text-slate-400"}`}>{t.plan}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500">{t.slug}</span>
                  <span className={`ml-auto text-xs ${t.status === "active" ? "text-emerald-400" : "text-red-400"}`}>{t.status}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Quick nav */}
      <div>
        <h2 className="text-sm font-semibold text-slate-400 mb-3 flex items-center gap-2">
          <Zap className="h-4 w-4" /> Admin Quick Nav
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {QUICK_NAV.map(({ href, Icon, label, color, desc }) => (
            <button
              key={href} onClick={() => router.push(href)}
              className="flex flex-col items-start gap-2 p-4 rounded-xl border border-slate-700 bg-slate-800/60 hover:border-slate-600 hover:bg-slate-700/60 transition-all text-left group"
            >
              <Icon className={`h-5 w-5 ${color} group-hover:scale-110 transition-transform`} />
              <div>
                <p className="text-sm font-medium text-slate-200">{label}</p>
                <p className="text-xs text-slate-500 mt-0.5">{desc}</p>
              </div>
            </button>
          ))}
        </div>
      </div>

    </div>
  );
}
