"use client";

import { useEffect, useState, useCallback } from "react";
import { authHeaders } from "@/lib/auth";
import AdminGuard from "@/components/AdminGuard";
import BillingDrawer from "@/components/BillingDrawer";
import {
  Building2, Plus, Pencil, Trash2, Users, MessageSquare,
  CheckCircle, XCircle, Clock, RefreshCw, ChevronRight,
  Crown, Zap, Sparkles, Shield, BarChart3, X, Save,
  AlertTriangle, ArrowUpRight, CreditCard,
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

interface Tenant {
  id: string; slug: string; name: string; admin_email: string;
  plan: "free" | "starter" | "pro" | "enterprise";
  status: "active" | "suspended" | "trial";
  max_users: number; max_chat_sessions: number; max_voice_minutes: number;
  settings: Record<string, unknown>; notes?: string;
  trial_ends_at?: string; created_at: string; updated_at: string;
}

interface TenantStats {
  tenant: Tenant;
  usage: {
    users: { total: number; active: number; limit: number; utilisation_pct: number };
    chat_sessions: { total: number; limit: number; utilisation_pct: number };
    messages: { total: number };
    escalations: { total: number };
    knowledge_docs: { total: number };
  };
}

const PLAN_ICONS: Record<string, React.ElementType> = {
  free: Clock, starter: Zap, pro: Crown, enterprise: Sparkles,
};
const PLAN_COLORS: Record<string, string> = {
  free: "text-slate-400 bg-slate-500/10 border-slate-500/20",
  starter: "text-blue-400 bg-blue-500/10 border-blue-500/20",
  pro: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  enterprise: "text-violet-400 bg-violet-500/10 border-violet-500/20",
};
const STATUS_COLORS: Record<string, string> = {
  active: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  suspended: "text-red-400 bg-red-500/10 border-red-500/20",
  trial: "text-amber-400 bg-amber-500/10 border-amber-500/20",
};

const PLANS = ["free", "starter", "pro", "enterprise"];
const PLAN_LIMITS: Record<string, Record<string, number>> = {
  free:       { max_users: 3,   max_chat_sessions: 100,   max_voice_minutes: 10 },
  starter:    { max_users: 10,  max_chat_sessions: 1000,  max_voice_minutes: 60 },
  pro:        { max_users: 50,  max_chat_sessions: 5000,  max_voice_minutes: 300 },
  enterprise: { max_users: 500, max_chat_sessions: 50000, max_voice_minutes: 3000 },
};

function UsageBar({ pct, label }: { pct: number; label: string }) {
  const color = pct >= 90 ? "bg-red-500" : pct >= 70 ? "bg-amber-500" : "bg-emerald-500";
  return (
    <div>
      <div className="flex justify-between text-[10px] text-slate-500 mb-0.5">
        <span>{label}</span><span>{pct.toFixed(0)}%</span>
      </div>
      <div className="h-1 w-full rounded-full bg-[#1f2937]">
        <div className={`h-1 rounded-full ${color} transition-all`} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
    </div>
  );
}

function TenantModal({ tenant, onClose, onSaved }: {
  tenant: Partial<Tenant> | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = !!tenant?.id;
  const [form, setForm] = useState<Record<string, string>>({
    slug: tenant?.slug ?? "",
    name: tenant?.name ?? "",
    admin_email: tenant?.admin_email ?? "",
    plan: tenant?.plan ?? "starter",
    status: tenant?.status ?? "active",
    notes: tenant?.notes ?? "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const limits = PLAN_LIMITS[form.plan] ?? PLAN_LIMITS.starter;

  const handleSubmit = async () => {
    setSaving(true); setError(null);
    try {
      const url = isEdit ? `${API}/api/v1/tenants/${tenant!.slug}` : `${API}/api/v1/tenants`;
      const method = isEdit ? "PATCH" : "POST";
      const r = await fetch(url, {
        method,
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, ...limits }),
      });
      if (!r.ok) {
        const d = await r.json();
        setError(d.detail ?? "Save failed");
      } else {
        onSaved();
        onClose();
      }
    } catch {
      setError("Network error");
    }
    setSaving(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg rounded-2xl border border-[#1f2937] bg-[#0c111d] p-6 shadow-2xl">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <Building2 className="h-4 w-4 text-amber-400" />
            <h2 className="text-sm font-semibold text-slate-200">{isEdit ? `Edit ${tenant?.name}` : "Create New Tenant"}</h2>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300"><X className="h-4 w-4" /></button>
        </div>

        <div className="space-y-3">
          {!isEdit && (
            <div>
              <label className="text-[11px] text-slate-500">Slug (URL identifier) *</label>
              <input value={form.slug} onChange={e => setForm(f => ({ ...f, slug: e.target.value.toLowerCase().replace(/\s/g, "-") }))}
                placeholder="acme-corp"
                className="mt-1 w-full rounded-lg border border-[#1f2937] bg-[#060c16] px-3 py-2 text-sm text-slate-300 placeholder-slate-600 focus:outline-none focus:border-amber-500/50" />
              <p className="mt-0.5 text-[10px] text-slate-600">Lowercase letters, numbers, hyphens only. Cannot be changed later.</p>
            </div>
          )}
          <div>
            <label className="text-[11px] text-slate-500">Company Name *</label>
            <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              placeholder="Acme Corporation"
              className="mt-1 w-full rounded-lg border border-[#1f2937] bg-[#060c16] px-3 py-2 text-sm text-slate-300 placeholder-slate-600 focus:outline-none focus:border-amber-500/50" />
          </div>
          <div>
            <label className="text-[11px] text-slate-500">Admin Email *</label>
            <input type="email" value={form.admin_email} onChange={e => setForm(f => ({ ...f, admin_email: e.target.value }))}
              placeholder="admin@acme.com"
              className="mt-1 w-full rounded-lg border border-[#1f2937] bg-[#060c16] px-3 py-2 text-sm text-slate-300 placeholder-slate-600 focus:outline-none focus:border-amber-500/50" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] text-slate-500">Plan</label>
              <select value={form.plan} onChange={e => setForm(f => ({ ...f, plan: e.target.value }))}
                className="mt-1 w-full rounded-lg border border-[#1f2937] bg-[#060c16] px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-amber-500/50">
                {PLANS.map(p => <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>)}
              </select>
            </div>
            <div>
              <label className="text-[11px] text-slate-500">Status</label>
              <select value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value }))}
                className="mt-1 w-full rounded-lg border border-[#1f2937] bg-[#060c16] px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-amber-500/50">
                <option value="active">Active</option>
                <option value="trial">Trial</option>
                <option value="suspended">Suspended</option>
              </select>
            </div>
          </div>

          {/* Plan limits preview */}
          <div className="rounded-xl border border-[#1f2937] bg-[#060c16] p-3 text-[11px] text-slate-500 space-y-0.5">
            <p className="font-semibold text-slate-400 mb-1">Plan includes:</p>
            <p>{limits.max_users} users · {limits.max_chat_sessions.toLocaleString()} chat sessions · {limits.max_voice_minutes} voice minutes/month</p>
          </div>

          <div>
            <label className="text-[11px] text-slate-500">Notes (internal)</label>
            <textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
              rows={2} placeholder="Optional notes..."
              className="mt-1 w-full rounded-lg border border-[#1f2937] bg-[#060c16] px-3 py-2 text-sm text-slate-300 placeholder-slate-600 focus:outline-none focus:border-amber-500/50 resize-none" />
          </div>
        </div>

        {error && <p className="mt-3 text-xs text-red-400">{error}</p>}

        <div className="mt-5 flex justify-end gap-3">
          <button onClick={onClose} className="rounded-lg border border-[#1f2937] px-4 py-2 text-xs text-slate-400 hover:text-slate-200 transition-all">
            Cancel
          </button>
          <button onClick={handleSubmit} disabled={saving}
            className="flex items-center gap-1.5 rounded-lg bg-amber-500/20 border border-amber-500/30 px-4 py-2 text-xs text-amber-400 hover:bg-amber-500/30 disabled:opacity-50 transition-all">
            <Save className="h-3.5 w-3.5" /> {saving ? "Saving..." : isEdit ? "Save Changes" : "Create Tenant"}
          </button>
        </div>
      </div>
    </div>
  );
}

function TenantCard({ tenant, onEdit, onDelete, onViewStats, onBilling }: {
  tenant: Tenant;
  onEdit: () => void;
  onDelete: () => void;
  onViewStats: () => void;
  onBilling: () => void;
}) {
  const PlanIcon = PLAN_ICONS[tenant.plan] ?? Zap;
  const planCls = PLAN_COLORS[tenant.plan] ?? PLAN_COLORS.starter;
  const statusCls = STATUS_COLORS[tenant.status] ?? STATUS_COLORS.active;

  return (
    <div className="rounded-2xl border border-[#1f2937] bg-[#0c111d] p-4 hover:border-[#2d3748] transition-all">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-amber-500/10 border border-amber-500/20">
            <Building2 className="h-3.5 w-3.5 text-amber-400" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-slate-200 truncate">{tenant.name}</p>
            <p className="text-[11px] text-slate-500 font-mono">{tenant.slug}</p>
          </div>
        </div>
        <div className="flex gap-1.5 flex-shrink-0">
          <button onClick={onBilling} title="Billing"
            className="rounded p-1.5 text-slate-500 hover:text-emerald-400 hover:bg-emerald-500/10 transition-all">
            <CreditCard className="h-3.5 w-3.5" />
          </button>
          <button onClick={onViewStats} title="View stats"
            className="rounded p-1.5 text-slate-500 hover:text-blue-400 hover:bg-blue-500/10 transition-all">
            <BarChart3 className="h-3.5 w-3.5" />
          </button>
          <button onClick={onEdit} title="Edit"
            className="rounded p-1.5 text-slate-500 hover:text-amber-400 hover:bg-amber-500/10 transition-all">
            <Pencil className="h-3.5 w-3.5" />
          </button>
          <button onClick={onDelete} title="Suspend"
            className="rounded p-1.5 text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-all">
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div className="flex items-center gap-2 mb-3">
        <span className={`flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${planCls}`}>
          <PlanIcon className="h-2.5 w-2.5" /> {tenant.plan}
        </span>
        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${statusCls}`}>
          {tenant.status}
        </span>
      </div>

      <div className="text-[11px] text-slate-500 space-y-0.5 mb-3">
        <p className="truncate">{tenant.admin_email}</p>
        <p>Up to {tenant.max_users} users · {tenant.max_chat_sessions.toLocaleString()} sessions</p>
      </div>

      <p className="text-[10px] text-slate-600">
        Created {new Date(tenant.created_at).toLocaleDateString()}
      </p>
    </div>
  );
}

function TenantStatsDrawer({ slug, onClose }: { slug: string; onClose: () => void }) {
  const [stats, setStats] = useState<TenantStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/api/v1/tenants/${slug}/stats`, { headers: authHeaders() })
      .then(r => r.ok ? r.json() : null)
      .then(d => { setStats(d); setLoading(false); });
  }, [slug]);

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="flex-1 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="w-full max-w-md bg-[#0c111d] border-l border-[#1f2937] p-6 overflow-y-auto">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-amber-400" />
            <h2 className="text-sm font-semibold text-slate-200">Tenant Usage</h2>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300"><X className="h-4 w-4" /></button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20 text-slate-600">Loading...</div>
        ) : !stats ? (
          <div className="flex items-center justify-center py-20 text-slate-600">No data available</div>
        ) : (
          <div className="space-y-5">
            <div className="rounded-xl border border-[#1f2937] bg-[#060c16] p-4">
              <p className="text-xs font-semibold text-slate-300 mb-1">{stats.tenant.name}</p>
              <p className="text-[11px] text-slate-500">{stats.tenant.admin_email}</p>
              <div className="flex gap-2 mt-2">
                <span className={`rounded-full border px-2 py-0.5 text-[10px] ${PLAN_COLORS[stats.tenant.plan]}`}>
                  {stats.tenant.plan}
                </span>
                <span className={`rounded-full border px-2 py-0.5 text-[10px] ${STATUS_COLORS[stats.tenant.status]}`}>
                  {stats.tenant.status}
                </span>
              </div>
            </div>

            <div className="rounded-xl border border-[#1f2937] bg-[#060c16] p-4 space-y-3">
              <p className="text-[11px] font-semibold text-slate-400">Resource Utilisation</p>
              <UsageBar pct={stats.usage.users.utilisation_pct}
                label={`Users: ${stats.usage.users.total} / ${stats.usage.users.limit}`} />
              <UsageBar pct={stats.usage.chat_sessions.utilisation_pct}
                label={`Chat Sessions: ${stats.usage.chat_sessions.total} / ${stats.usage.chat_sessions.limit}`} />
            </div>

            <div className="grid grid-cols-2 gap-3">
              {[
                { label: "Total Messages", value: stats.usage.messages.total, icon: MessageSquare },
                { label: "Active Users",   value: stats.usage.users.active,   icon: Users },
                { label: "Escalations",    value: stats.usage.escalations.total, icon: AlertTriangle },
                { label: "Knowledge Docs", value: stats.usage.knowledge_docs.total, icon: Shield },
              ].map(({ label, value, icon: Icon }) => (
                <div key={label} className="rounded-xl border border-[#1f2937] bg-[#060c16] p-3">
                  <div className="flex items-center gap-1.5 mb-1">
                    <Icon className="h-3 w-3 text-slate-600" />
                    <p className="text-[10px] text-slate-600">{label}</p>
                  </div>
                  <p className="text-lg font-bold text-slate-200">{value.toLocaleString()}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function TenantsContent() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [modalTenant, setModalTenant] = useState<Partial<Tenant> | null | false>(false);
  const [statsSlug, setStatsSlug] = useState<string | null>(null);
  const [billingTenant, setBillingTenant] = useState<Tenant | null>(null);
  const [search, setSearch] = useState("");
  const [planFilter, setPlanFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  const fetchTenants = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: "100" });
      if (planFilter !== "all") params.set("plan", planFilter);
      if (statusFilter !== "all") params.set("status", statusFilter);
      const r = await fetch(`${API}/api/v1/tenants?${params}`, { headers: authHeaders() });
      if (r.ok) {
        const d = await r.json();
        setTenants(d.tenants ?? []);
        setTotal(d.total ?? 0);
      }
    } catch {}
    setLoading(false);
  }, [planFilter, statusFilter]);

  useEffect(() => { fetchTenants(); }, [fetchTenants]);

  const handleDelete = async (slug: string) => {
    if (!confirm(`Suspend tenant "${slug}"? Users will lose access.`)) return;
    await fetch(`${API}/api/v1/tenants/${slug}`, { method: "DELETE", headers: authHeaders() });
    fetchTenants();
  };

  const filtered = tenants.filter(t =>
    !search || t.name.toLowerCase().includes(search.toLowerCase()) ||
    t.slug.includes(search.toLowerCase()) || t.admin_email.includes(search.toLowerCase())
  );

  const summary = {
    active: tenants.filter(t => t.status === "active").length,
    trial: tenants.filter(t => t.status === "trial").length,
    suspended: tenants.filter(t => t.status === "suspended").length,
    totalUsers: 0, // fetched async per tenant
  };

  return (
    <div className="min-h-screen bg-[#030712] text-slate-300">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#1f2937] px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500/10 border border-amber-500/20">
            <Building2 className="h-4 w-4 text-amber-400" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-slate-200">Tenant Management</h1>
            <p className="text-[11px] text-slate-500">{total} organisations · fully isolated workspaces</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={fetchTenants} disabled={loading}
            className="rounded-xl border border-[#1f2937] p-2 text-slate-500 hover:text-slate-300 disabled:opacity-50 transition-all">
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>
          <button onClick={() => setModalTenant({})}
            className="flex items-center gap-1.5 rounded-xl bg-amber-500/20 border border-amber-500/30 px-3 py-2 text-xs font-medium text-amber-400 hover:bg-amber-500/30 transition-all">
            <Plus className="h-3.5 w-3.5" /> New Tenant
          </button>
        </div>
      </div>

      <div className="p-6 space-y-5">
        {/* Summary cards */}
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: "Active", value: summary.active, color: "text-emerald-400", dot: "bg-emerald-400" },
            { label: "Trial",  value: summary.trial,  color: "text-amber-400",   dot: "bg-amber-400"   },
            { label: "Suspended", value: summary.suspended, color: "text-red-400", dot: "bg-red-400"   },
          ].map(({ label, value, color, dot }) => (
            <div key={label} className="rounded-2xl border border-[#1f2937] bg-[#0c111d] p-4">
              <div className="flex items-center gap-2 mb-1">
                <span className={`h-2 w-2 rounded-full ${dot}`} />
                <p className="text-[11px] text-slate-600 uppercase tracking-wider">{label}</p>
              </div>
              <p className={`text-3xl font-bold ${color}`}>{value}</p>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3 flex-wrap">
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search by name, slug, or email..."
            className="flex-1 min-w-[200px] rounded-xl border border-[#1f2937] bg-[#0c111d] px-3 py-2 text-sm text-slate-300 placeholder-slate-600 focus:outline-none focus:border-amber-500/50" />
          <select value={planFilter} onChange={e => setPlanFilter(e.target.value)}
            className="rounded-xl border border-[#1f2937] bg-[#0c111d] px-3 py-2 text-sm text-slate-400 focus:outline-none focus:border-amber-500/50">
            <option value="all">All Plans</option>
            {PLANS.map(p => <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>)}
          </select>
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
            className="rounded-xl border border-[#1f2937] bg-[#0c111d] px-3 py-2 text-sm text-slate-400 focus:outline-none focus:border-amber-500/50">
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="trial">Trial</option>
            <option value="suspended">Suspended</option>
          </select>
        </div>

        {/* Tenant grid */}
        {loading ? (
          <div className="flex items-center justify-center py-20 text-slate-600">
            <RefreshCw className="h-5 w-5 animate-spin mr-2" /> Loading tenants...
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-slate-600">
            <Building2 className="h-10 w-10 mb-3 opacity-30" />
            <p className="text-sm">No tenants found</p>
            <p className="text-[11px] mt-1">Create your first tenant to get started</p>
            <button onClick={() => setModalTenant({})}
              className="mt-4 flex items-center gap-1.5 rounded-xl bg-amber-500/20 border border-amber-500/30 px-4 py-2 text-sm text-amber-400 hover:bg-amber-500/30 transition-all">
              <Plus className="h-3.5 w-3.5" /> Create Tenant
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map(t => (
              <TenantCard
                key={t.slug} tenant={t}
                onEdit={() => setModalTenant(t)}
                onDelete={() => handleDelete(t.slug)}
                onViewStats={() => setStatsSlug(t.slug)}
                onBilling={() => setBillingTenant(t)}
              />
            ))}
          </div>
        )}

        {/* How multi-tenancy works */}
        <div className="rounded-2xl border border-[#1f2937] bg-[#0c111d] p-5">
          <div className="flex items-center gap-2 mb-3">
            <Shield className="h-4 w-4 text-amber-400" />
            <h2 className="text-xs font-semibold text-slate-300">How Multi-Tenancy Works</h2>
          </div>
          <div className="grid grid-cols-2 gap-3 text-[11px]">
            {[
              { icon: Users, title: "Isolated Users", desc: "Each tenant has its own user accounts. Users from Tenant A cannot see Tenant B's data." },
              { icon: MessageSquare, title: "Isolated Conversations", desc: "Chat and voice sessions are scoped to the tenant. No cross-tenant data leakage." },
              { icon: Shield, title: "Isolated Knowledge Base", desc: "Documents uploaded by one tenant are only visible to agents in that tenant." },
              { icon: BarChart3, title: "Per-Tenant Analytics", desc: "Usage stats, billing counters, and audit logs are all isolated per tenant." },
              { icon: CheckCircle, title: "Independent Auth", desc: "Each tenant admin manages their own users, passwords, and roles independently." },
              { icon: Crown, title: "Plan-Based Limits", desc: "Each tenant is on a plan that enforces user, session, and voice minute limits." },
            ].map(({ icon: Icon, title, desc }) => (
              <div key={title} className="flex gap-2 rounded-xl border border-[#1f2937] p-3">
                <Icon className="h-3.5 w-3.5 text-amber-400 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="font-semibold text-slate-300">{title}</p>
                  <p className="text-slate-600 mt-0.5">{desc}</p>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 rounded-xl border border-blue-500/20 bg-blue-500/5 p-3 text-[11px] text-blue-400">
            <p className="font-semibold mb-1">To add a new customer / tenant:</p>
            <p>1. Click <strong>"New Tenant"</strong> above and fill in their company name, email, and plan.</p>
            <p>2. Go to <strong>Settings → User Management</strong> and create a user with that tenant's slug as their <code>tenant_id</code>.</p>
            <p>3. Share the login URL with them: <code>https://www.algoworkforce.com/login</code></p>
          </div>
        </div>
      </div>

      {/* Modals */}
      {modalTenant !== false && (
        <TenantModal
          tenant={modalTenant || null}
          onClose={() => setModalTenant(false)}
          onSaved={fetchTenants}
        />
      )}
      {statsSlug && <TenantStatsDrawer slug={statsSlug} onClose={() => setStatsSlug(null)} />}
      {billingTenant && (
        <BillingDrawer
          slug={billingTenant.slug}
          tenantName={billingTenant.name}
          onClose={() => setBillingTenant(null)}
        />
      )}
    </div>
  );
}

export default function TenantsPage() {
  return <AdminGuard><TenantsContent /></AdminGuard>;
}
